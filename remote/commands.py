"""
remote/commands.py — Structured command router and AI orchestrator integration.
"""
from __future__ import annotations

import asyncio
import base64
import re
import tempfile
from pathlib import Path
from typing import Any

from remote.auth import device_auth_manager
from remote.file_service import remote_file_service, FileSecurityError
from remote.system_service import remote_system_service
from remote.notifications import notification_manager
from remote.audit_log import audit_logger

# Fallback LLM client
try:
    from core.llm_client import call_llm
    _LLM_CLIENT_OK = True
except ImportError:
    _LLM_CLIENT_OK = False

try:
    import edge_tts
    _EDGE_TTS_OK = True
except ImportError:
    _EDGE_TTS_OK = False

try:
    import pyttsx3 as _pyttsx3
    _PYTTSX3_OK = True
except ImportError:
    _PYTTSX3_OK = False


def _pyttsx3_speech_b64(text: str) -> str:
    """Offline Windows TTS via pyttsx3 — returns JSON envelope {fmt, data} as a string."""
    import json
    try:
        engine = _pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 1.0)
        voices = engine.getProperty("voices")
        for v in voices:
            if "zira" in v.name.lower() or "david" in v.name.lower():
                engine.setProperty("voice", v.id)
                break

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        engine.save_to_file(text, str(tmp_path))
        engine.runAndWait()
        engine.stop()

        raw = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)
        if not raw:
            return ""
        data_b64 = base64.b64encode(raw).decode("ascii")
        # Return a JSON envelope so the Android client knows the MIME type
        return json.dumps({"fmt": "wav", "data": data_b64})
    except Exception as e:
        print(f"[SpeechGen] pyttsx3 fallback failed: {e}")
        return ""



async def _generate_speech_b64(text: Any) -> str:
    """
    Generates speech audio in base64 for native playback on Android.

    Priority:
      1. EdgeTTS  (Microsoft cloud TTS — best quality, needs internet)
      2. pyttsx3  (Windows offline TTS — no internet required)
      3. Empty string (silent fallback — JARVIS text response still displayed)
    """
    if not text:
        return ""

    str_text = text if isinstance(text, str) else str(text)
    clean_text = re.sub(r"[*_`#\[\]]", "", str_text).strip()[:500]
    if not clean_text:
        return ""

    # 1. Try EdgeTTS (cloud)
    if _EDGE_TTS_OK:
        try:
            communicate = edge_tts.Communicate(clean_text, voice="en-US-GuyNeural")
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            await communicate.save(str(tmp_path))
            audio_b64 = base64.b64encode(tmp_path.read_bytes()).decode("ascii")
            tmp_path.unlink(missing_ok=True)
            return audio_b64
        except Exception as e:
            print(f"[SpeechGen] EdgeTTS unavailable ({type(e).__name__}: {e}) — trying offline fallback.")

    # 2. Offline fallback: pyttsx3 (Windows built-in TTS — always available)
    if _PYTTSX3_OK:
        print("[SpeechGen] Using pyttsx3 offline TTS.")
        result = await asyncio.to_thread(_pyttsx3_speech_b64, clean_text)
        if result:
            return result

    # 3. Silent fallback — text response still delivered to Android
    print("[SpeechGen] No TTS engine available — audio skipped.")
    return ""

class RemoteCommandRouter:
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator

    def set_orchestrator(self, orchestrator) -> None:
        self.orchestrator = orchestrator

    async def handle_command(
        self,
        command_payload: dict[str, Any],
        device_id: str,
        client_ip: str = "127.0.0.1"
    ) -> dict[str, Any]:
        """
        Validates and executes a structured remote command.
        """
        request_id = command_payload.get("request_id", "unknown")
        cmd_type = command_payload.get("type", "command")
        command = command_payload.get("command", "")
        args = command_payload.get("arguments", {})

        audit_logger.log_event(
            "COMMAND_RECEIVED",
            f"Command '{command}' from {device_id}",
            device_id=device_id,
            client_ip=client_ip,
            metadata={"request_id": request_id}
        )

        try:
            # ── 1. Voice / Text Natural Language Assistant Query ─────────────
            if command in ("voice_query", "text_query", "ask"):
                return await self._handle_query(request_id, args, device_id, client_ip)

            # ── 2. File Search ───────────────────────────────────────────────
            elif command == "search_files":
                query = args.get("query", "")
                file_type = args.get("file_type", "")
                results = remote_file_service.search_files(query=query, file_type=file_type)
                return {
                    "request_id": request_id,
                    "status": "success",
                    "command": command,
                    "message": f"Found {len(results)} item(s) matching '{query}'.",
                    "results": results,
                }

            # ── 3. Prepare File Transfer ─────────────────────────────────────
            elif command == "prepare_transfer":
                target_path = args.get("target_path", "")
                ext_filter = args.get("file_extension_filter", "")
                try:
                    prep = remote_file_service.prepare_transfer(target_path, ext_filter, device_id=device_id)
                    return {
                        "request_id": request_id,
                        "status": "success",
                        "command": command,
                        "message": (
                            f"I found {prep['file_count']} file(s) totaling {prep['total_mb']} MB. "
                            "Ready to transfer."
                        ),
                        "transfer": prep,
                    }
                except (FileSecurityError, ValueError, FileNotFoundError) as e:
                    return {
                        "request_id": request_id,
                        "status": "error",
                        "command": command,
                        "message": str(e),
                    }

            # ── 4. System Status & Hardware Telemetry ────────────────────────
            elif command == "system_status":
                telemetry = remote_system_service.get_telemetry()
                cpu = telemetry["cpu_percent"]
                ram = telemetry["ram_percent"]
                gpu_load = telemetry["gpu"].get("load_percent", -1)
                bat = telemetry["battery"].get("percent", 100)

                gpu_str = f", GPU is {gpu_load:.0f}%" if gpu_load >= 0 else ""
                summary = f"CPU is {cpu:.0f}%, RAM is {ram:.0f}%{gpu_str}, and battery is {bat:.0f}%."

                return {
                    "request_id": request_id,
                    "status": "success",
                    "command": command,
                    "message": summary,
                    "telemetry": telemetry,
                }

            # ── 5. Open / Launch Approved Application ────────────────────────
            elif command == "open_app":
                app_name = args.get("app_name", "")
                res = remote_system_service.launch_application(app_name, device_id=device_id)
                return {
                    "request_id": request_id,
                    "status": res["status"],
                    "command": command,
                    "message": res["message"],
                }

            # ── 6. High-Risk Confirmation Challenge ──────────────────────────
            elif command == "request_shutdown":
                chal = remote_system_service.create_dangerous_challenge(action="shutdown", device_id=device_id)
                return {
                    "request_id": request_id,
                    "status": "confirmation_required",
                    "command": command,
                    "message": chal["message"],
                    "challenge": chal,
                }

            elif command == "confirm_action":
                chal_id = args.get("challenge_id", "")
                res = remote_system_service.verify_and_execute_challenge(chal_id, device_id=device_id)
                return {
                    "request_id": request_id,
                    "status": res["status"],
                    "command": command,
                    "message": res["message"],
                }

            # ── 7. Sentry Mode Control ───────────────────────────────────────
            elif command == "sentry_status":
                status_msg = "Sentry mode is disarmed."
                is_active = False
                if self.orchestrator and hasattr(self.orchestrator, "_plugin_registry"):
                    if self.orchestrator._plugin_registry.has("sentry_mode"):
                        try:
                            status_msg = self.orchestrator._plugin_registry.run(
                                "sentry_mode", {"action": "status"}
                            )
                            is_active = "ACTIVE" in status_msg
                        except Exception:
                            pass
                return {
                    "request_id": request_id,
                    "status": "success",
                    "command": command,
                    "message": status_msg,
                    "is_active": is_active,
                }

            elif command == "sentry_toggle":
                action = args.get("action", "arm")  # arm | disarm
                res = f"Sentry mode set to {action}."
                if self.orchestrator and hasattr(self.orchestrator, "_plugin_registry"):
                    if self.orchestrator._plugin_registry.has("sentry_mode"):
                        try:
                            res = self.orchestrator._plugin_registry.run(
                                "sentry_mode", {"action": action}
                            )
                        except Exception as e:
                            res = f"Sentry error: {e}"
                return {
                    "request_id": request_id,
                    "status": "success",
                    "command": command,
                    "message": res,
                }

            # ── 8. Notification History ──────────────────────────────────────
            elif command == "get_notifications":
                notifs = notification_manager.get_history(limit=50)
                return {
                    "request_id": request_id,
                    "status": "success",
                    "command": command,
                    "notifications": notifs,
                }

            else:
                return {
                    "request_id": request_id,
                    "status": "error",
                    "command": command,
                    "message": f"Unknown remote command: '{command}'",
                }

        except Exception as e:
            audit_logger.log_event(
                "COMMAND_FAILED",
                f"Error running '{command}': {e}",
                device_id=device_id,
                level="ERROR"
            )
            return {
                "request_id": request_id,
                "status": "error",
                "command": command,
                "message": f"Execution error: {e}",
            }

    async def _handle_query(
        self,
        request_id: str,
        args: dict[str, Any],
        device_id: str,
        client_ip: str
    ) -> dict[str, Any]:
        """
        Parses and handles conversational voice/text queries using either
        direct intent matching or the existing JARVIS brain (Gemini / Ollama).
        """
        query = args.get("query", "").strip()
        include_audio = args.get("include_audio", True)

        if not query:
            return {
                "request_id": request_id,
                "status": "error",
                "message": "Empty query provided.",
            }

        lower = query.lower()

        # Direct intent 1: CPU / RAM / System usage
        if any(k in lower for k in ("cpu", "ram", "gpu", "battery", "system status", "telemetry", "how is the computer", "how is the lab")):
            telemetry = remote_system_service.get_telemetry()
            cpu = telemetry["cpu_percent"]
            ram = telemetry["ram_percent"]
            gpu_load = telemetry["gpu"].get("load_percent", -1)
            bat = telemetry["battery"].get("percent", 100)

            gpu_str = f", GPU is {gpu_load:.0f}%" if gpu_load >= 0 else ""
            answer = f"CPU is {cpu:.0f}%, RAM is {ram:.0f}%{gpu_str}, and battery is {bat:.0f}%."

            audio_b64 = await _generate_speech_b64(answer) if include_audio else ""
            return {
                "request_id": request_id,
                "status": "success",
                "message": answer,
                "audio_b64": audio_b64,
                "telemetry": telemetry,
            }

        # Direct intent 2: Find / Search files
        m_find = re.search(r"(?:find|search for|locate)\s+(?:the\s+)?([a-zA-Z0-9_\-.\s]+?)(?:\s+folder|\s+file|$)", lower)
        if m_find and not any(k in lower for k in ("chrome", "app", "code")):
            target = m_find.group(1).strip()
            results = remote_file_service.search_files(query=target, max_results=5)
            if results:
                first = results[0]
                answer = f"I found {first['name']} in {first['path']}."
            else:
                answer = f"I could not find '{target}' in your allowed directories."

            audio_b64 = await _generate_speech_b64(answer) if include_audio else ""
            return {
                "request_id": request_id,
                "status": "success",
                "message": answer,
                "audio_b64": audio_b64,
                "results": results,
            }

        # Direct intent 3: Send / Transfer files
        if "send" in lower and any(k in lower for k in ("pdf", "file", "doc", "code", "zip")):
            ext = "pdf" if "pdf" in lower else ""
            # Search recent folders or last search
            results = remote_file_service.search_files(query="", file_type=ext, max_results=20)
            if results:
                first_dir = str(Path(results[0]["path"]).parent)
                try:
                    prep = remote_file_service.prepare_transfer(first_dir, ext, device_id=device_id)
                    answer = f"I found {prep['file_count']} {ext.upper() or 'file'}s totaling {prep['total_mb']} MB. Would you like me to transfer them?"
                    audio_b64 = await _generate_speech_b64(answer) if include_audio else ""
                    return {
                        "request_id": request_id,
                        "status": "success",
                        "message": answer,
                        "audio_b64": audio_b64,
                        "transfer": prep,
                    }
                except Exception as e:
                    pass

        # Direct intent 4: Open application
        m_open = re.search(r"(?:open|launch|start)\s+([a-zA-Z0-9_\s]+)", lower)
        if m_open and not any(k in lower for k in ("ml project", "file", "folder")):
            app_req = m_open.group(1).strip()
            res = remote_system_service.launch_application(app_req, device_id=device_id)
            answer = res["message"]
            audio_b64 = await _generate_speech_b64(answer) if include_audio else ""
            return {
                "request_id": request_id,
                "status": res["status"],
                "message": answer,
                "audio_b64": audio_b64,
            }

        # Direct intent 5: Shutdown
        if "shut down" in lower or "shutdown" in lower or "power off" in lower:
            chal = remote_system_service.create_dangerous_challenge(action="shutdown", device_id=device_id)
            answer = chal["message"]
            audio_b64 = await _generate_speech_b64(answer) if include_audio else ""
            return {
                "request_id": request_id,
                "status": "confirmation_required",
                "message": answer,
                "audio_b64": audio_b64,
                "challenge": chal,
            }

        # Fallback: Forward to JARVIS AI Brain (Ollama / Gemini)
        answer = "I processed your request, sir."
        if _LLM_CLIENT_OK:
            try:
                system_prompt = (
                    "You are JARVIS, personal AI assistant for Tony Stark's lab. "
                    "You are answering remotely from the user's Android phone. "
                    "Be concise (1 to 2 sentences max), direct, and confident."
                )
                raw_res = await asyncio.to_thread(
                    call_llm,
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query},
                    ]
                )
                if isinstance(raw_res, dict):
                    answer = raw_res.get("content", "") or "Understood, sir."
                elif isinstance(raw_res, str):
                    answer = raw_res
                else:
                    answer = str(raw_res)
            except Exception as e:
                print(f"[CommandRouter] LLM call error: {e}")
                answer = f"I received your request: '{query}'."

        audio_b64 = await _generate_speech_b64(answer) if include_audio else ""
        return {
            "request_id": request_id,
            "status": "success",
            "message": answer,
            "audio_b64": audio_b64,
        }

remote_command_router = RemoteCommandRouter()
