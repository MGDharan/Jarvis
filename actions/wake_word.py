"""
Wake Word Detection for JARVIS — "Hey JARVIS" hands-free activation.

Tries three backends in order of quality:
  1. openwakeword  — free, no API key, runs on CPU, good accuracy (~150 MB model)
  2. pvporcupine   — commercial (free tier), very low CPU, best accuracy (API key needed)
  3. energy VAD    — pure fallback using only sounddevice + numpy; no external dep needed

The active backend is chosen automatically at startup based on what is installed.
The JarvisLive class creates one WakeWordDetector and calls:
    detector.start(callback)   — begins background listening; calls callback() on wake
    detector.stop()            — graceful stop
    detector.is_active         — True while listening
    detector.backend_name      — name of the active backend

Install options:
    pip install openwakeword                  # best free option
    pip install pvporcupine                   # best accuracy, requires API key

openwakeword model download:
    python -m openwakeword.utils download --model hey_jarvis_v0.1.onnx
    or just call detector.start() — it auto-downloads on first run (~150 MB)

Config keys in config/api_keys.json (all optional):
    "wake_word_backend":    "openwakeword" | "porcupine" | "energy" | "auto"
    "porcupine_access_key": "<your Picovoice access key>"
    "wake_word_sensitivity": 0.5   (0.0 – 1.0, higher = more sensitive)
    "wake_word_enabled":    true   (set false to disable entirely)
"""
from __future__ import annotations

import json
import platform
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

_OS = platform.system()

# ── Config loader ──────────────────────────────────────────────────────────────

def _base_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _load_config() -> dict:
    try:
        return json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
    except Exception:
        return {}


# ── Backend: openwakeword ──────────────────────────────────────────────────────

class _OpenWakeWordBackend:
    """
    Uses the openwakeword library with the bundled hey_jarvis ONNX model.
    Models are downloaded once on first use via openwakeword.utils.download_models().
    """
    NAME = "openwakeword"

    def __init__(self, sensitivity: float = 0.5):
        self._sensitivity = sensitivity

        # Ensure models are present on disk — downloads once (~8 MB total), no-ops if cached
        self._ensure_models()

        from openwakeword.model import Model  # type: ignore
        self._model = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx",
        )
        print(f"[WakeWord] openwakeword loaded (hey_jarvis onnx) — sensitivity={sensitivity}")

    @staticmethod
    def _ensure_models() -> None:
        """Download pretrained models if not already present."""
        import openwakeword, os
        paths = openwakeword.get_pretrained_model_paths()
        if paths and os.path.exists(paths[0]):
            return   # already cached
        try:
            print("[WakeWord] Downloading openwakeword models (one-time, ~8 MB)...")
            from openwakeword.utils import download_models
            download_models()
            print("[WakeWord] Models downloaded.")
        except Exception as e:
            print(f"[WakeWord] Model download failed: {e}")

    def process_chunk(self, audio_chunk: np.ndarray) -> bool:
        """
        Feed 16 kHz mono int16 samples; return True on detection.
        openwakeword.predict() expects float32 in [-1, 1].
        Chunk size should be 1280 samples (80 ms) for optimal latency.
        """
        # Ensure we have the right chunk size for openwakeword
        if len(audio_chunk) != 1280:
            # Pad or trim to exactly 1280 samples
            if len(audio_chunk) < 1280:
                audio_chunk = np.pad(audio_chunk, (0, 1280 - len(audio_chunk)), mode='constant')
            else:
                audio_chunk = audio_chunk[:1280]
        
        # Convert to float32 in range [-1, 1]
        frames = audio_chunk.astype(np.float32) / 32768.0
        
        # Ensure frames are in the correct range
        frames = np.clip(frames, -1.0, 1.0)
        
        try:
            prediction = self._model.predict(frames)
            # prediction is a dict: {"hey_jarvis": float_score}
            for wake_word, score in prediction.items():
                if float(score) >= self._sensitivity:
                    print(f"[WakeWord] '{wake_word}' detected with score {score:.3f}")
                    return True
        except Exception as e:
            print(f"[WakeWord] Prediction error: {e}")
        return False

    @staticmethod
    def is_available() -> bool:
        try:
            import openwakeword  # noqa: F401
            return True
        except ImportError:
            return False


# ── Backend: Picovoice Porcupine ───────────────────────────────────────────────

class _PorcupineBackend:
    """
    Uses pvporcupine — the most accurate wake-word engine.
    Free tier allows one custom keyword; "jarvis" is a built-in keyword.
    """
    NAME = "porcupine"

    def __init__(self, access_key: str, sensitivity: float = 0.5):
        import pvporcupine  # type: ignore
        self._porcupine = pvporcupine.create(
            access_key=access_key,
            keywords=["jarvis"],
            sensitivities=[sensitivity],
        )
        self._frame_length = self._porcupine.frame_length   # typically 512 samples
        print(f"[WakeWord] Porcupine loaded — frame_length={self._frame_length}")

    @property
    def frame_length(self) -> int:
        return self._frame_length

    def process_chunk(self, audio_chunk: np.ndarray) -> bool:
        """Feed exactly frame_length int16 samples; return True on detection."""
        result = self._porcupine.process(audio_chunk.astype(np.int16))
        return result >= 0   # ≥0 means a keyword was detected (index into keywords list)

    def delete(self) -> None:
        try:
            self._porcupine.delete()
        except Exception:
            pass

    @staticmethod
    def is_available() -> bool:
        try:
            import pvporcupine  # noqa: F401
            return True
        except ImportError:
            return False


# ── Backend: energy VAD (pure fallback) ───────────────────────────────────────

class _EnergyVADBackend:
    """
    Enhanced fallback: triggers on speech-like audio patterns.
    Looks for sustained audio with speech-like characteristics (multiple bursts).
    More selective than basic energy detection but still not keyword-specific.
    """
    NAME = "energy_vad"

    def __init__(self, sensitivity: float = 0.5):
        # Energy threshold: 0 = very sensitive, 1 = hard to trigger
        self._threshold = int((1.0 - sensitivity) * 300) + 150  # Higher base threshold
        self._burst_frames_needed = 6   # Need more sustained audio
        self._burst_count = 0
        self._speech_pattern_count = 0  # Track speech-like patterns
        self._last_high_energy = 0
        print(
            f"[WakeWord] Enhanced Energy VAD active — threshold={self._threshold} RMS\n"
            "           Listens for speech-like patterns (clap 3 times or speak sustained phrase)\n"
            "           Install openwakeword for keyword detection: pip install openwakeword"
        )

    def process_chunk(self, audio_chunk: np.ndarray) -> bool:
        rms = int(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))
        
        if rms > self._threshold:
            self._burst_count += 1
            self._last_high_energy = time.time()
            
            # Look for speech-like patterns: multiple energy bursts
            if self._burst_count >= self._burst_frames_needed:
                self._speech_pattern_count += 1
                self._burst_count = 0  # Reset burst counter
                
                # Require 2 speech patterns within 3 seconds (like "Hey JARVIS")
                if self._speech_pattern_count >= 2:
                    self._speech_pattern_count = 0
                    return True
        else:
            # Gradual decay
            if self._burst_count > 0:
                self._burst_count -= 0.3
            if self._burst_count < 0:
                self._burst_count = 0
                
            # Reset speech pattern if too much silence
            current_time = time.time()
            if current_time - self._last_high_energy > 2.0:
                self._speech_pattern_count = 0
                
        return False

    @staticmethod
    def is_available() -> bool:
        return True


# ── WakeWordDetector ───────────────────────────────────────────────────────────

class WakeWordDetector:
    """
    Listens continuously on the default microphone in a background thread.
    Calls the registered callback when the wake phrase is detected.

    Usage:
        detector = WakeWordDetector()
        detector.start(lambda: print("Wake word detected!"))
        ...
        detector.stop()
    """

    def __init__(self):
        self._cfg          = _load_config()
        self._enabled      = bool(self._cfg.get("wake_word_enabled", True))
        self._sensitivity  = float(self._cfg.get("wake_word_sensitivity", 0.5))
        self._backend_pref = str(self._cfg.get("wake_word_backend", "auto")).lower()
        self._porcupine_key= str(self._cfg.get("porcupine_access_key", ""))

        self._backend       = None
        self._backend_name  = "none"
        self._callback: Optional[Callable] = None
        self._stop_event    = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active        = False

        # Cooldown: don't fire more than once every N seconds
        self._cooldown_sec  = 5.0
        self._last_fire     = 0.0

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def backend_name(self) -> str:
        return self._backend_name

    def start(self, callback: Callable) -> bool:
        """
        Start listening.  callback() is called on each wake-word detection.
        Returns True if started, False if disabled or already running.
        """
        if not self._enabled:
            print("[WakeWord] Disabled in config (wake_word_enabled=false).")
            return False
        if self._active:
            return True

        self._callback   = callback
        self._stop_event.clear()

        # Build backend
        try:
            self._backend = self._pick_backend()
        except Exception as e:
            print(f"[WakeWord] ⚠️ Backend init failed: {e}")
            self._backend = None

        if not self._backend:
            print("[WakeWord] No wake word backend available. Wake word disabled.")
            return False

        self._thread = threading.Thread(
            target=self._listen_loop,
            name="WakeWordDetector",
            daemon=True,
        )
        self._thread.start()
        self._active = True
        return True

    def stop(self) -> None:
        """Stop listening and release resources."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._active = False
        if hasattr(self._backend, "delete"):
            try:
                self._backend.delete()
            except Exception:
                pass
        self._backend = None
        print("[WakeWord] Stopped.")

    # ── Backend selection ──────────────────────────────────────────────────────

    def _pick_backend(self):
        pref = self._backend_pref

        if pref == "porcupine":
            return self._init_porcupine()
        if pref == "openwakeword":
            return self._init_openwakeword()
        if pref == "energy":
            self._backend_name = _EnergyVADBackend.NAME
            return _EnergyVADBackend(self._sensitivity)

        # Auto: pick best available keyword detector
        if _PorcupineBackend.is_available() and self._porcupine_key:
            return self._init_porcupine()
        if _OpenWakeWordBackend.is_available():
            return self._init_openwakeword()
        return None

    def _init_porcupine(self):
        if not self._porcupine_key:
            raise RuntimeError(
                "Porcupine requires an access key. "
                "Set 'porcupine_access_key' in config/api_keys.json. "
                "Get a free key at https://console.picovoice.ai/"
            )
        b = _PorcupineBackend(self._porcupine_key, self._sensitivity)
        self._backend_name = _PorcupineBackend.NAME
        return b

    def _init_openwakeword(self):
        b = _OpenWakeWordBackend(self._sensitivity)
        self._backend_name = _OpenWakeWordBackend.NAME
        return b

    # ── Listening loop ─────────────────────────────────────────────────────────

    def _listen_loop(self) -> None:
        """
        Reads audio from the default input device using a persistent InputStream
        and feeds it to the backend.
        """
        import sounddevice as sd

        SAMPLE_RATE = 16_000

        if isinstance(self._backend, _PorcupineBackend):
            frame_size = self._backend.frame_length
        else:
            frame_size = 1280 if isinstance(self._backend, _OpenWakeWordBackend) else (SAMPLE_RATE // 2)

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=frame_size,
            ) as stream:
                while not self._stop_event.is_set():
                    try:
                        chunk, overflow = stream.read(frame_size)
                        if self._stop_event.is_set():
                            break

                        chunk_flat = chunk.flatten()
                        detected = self._backend.process_chunk(chunk_flat)
                        if detected:
                            now = time.monotonic()
                            if (now - self._last_fire) >= self._cooldown_sec:
                                self._last_fire = now
                                print("[WakeWord] 🎤 Wake word detected!")
                                if self._callback:
                                    try:
                                        self._callback()
                                    except Exception as e:
                                        print(f"[WakeWord] Callback error: {e}")
                    except Exception as e:
                        if self._stop_event.is_set():
                            break
                        time.sleep(0.1)
        except Exception as e:
            print(f"[WakeWord] Stream open error: {e}")
        self._active = False


# ── Convenience factory ────────────────────────────────────────────────────────

def create_detector() -> WakeWordDetector:
    """Create and return a WakeWordDetector configured from api_keys.json."""
    return WakeWordDetector()
