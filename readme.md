# 🤖 JARVIS (MARK LI) — Advanced AI Assistant & Autonomous Voice Agent

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Tests](https://img.shields.io/badge/unit%20tests-50%20passed-brightgreen.svg)]()
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

An autonomous, multi-modal personal AI assistant capable of real-time voice conversations, vision, system automation, autonomous phone calls over WhatsApp Desktop, drone control, and local offline intelligence.

---

## 🌟 Key Highlights

- **🎙️ Real-Time 2-Way WhatsApp Voice Bridge**: Automatically calls contacts on WhatsApp Desktop, captures remote voice via WASAPI loopback, detects speech via adaptive VAD, transcribes via CUDA-accelerated aster-whisper, generates contextual responses via Ollama (llama3.2), and speaks back into the call using EdgeTTS and Virtual Audio Cable with self-echo cancellation.
- **🧠 Hybrid Intelligence**: Works seamlessly with Google Gemini Live API for cloud multimodal streaming, or completely offline with local LLMs (Ollama llama3.2, llama3.1, qwen, gemma).
- **🚀 GPU-Accelerated Speech Processing**: Native CUDA support on NVIDIA GPUs (e.g. RTX 3050+) for ultra-fast Whisper speech-to-text with automatic graceful CPU fallback (int8).
- **🚁 Drone Flight Control Plugin**: Autonomous physical and simulated drone control for KY-UFO drones with automatic calibration and countdown sequence.
- **🖥️ Desktop & OS Automation**: Full control over windows, system volume, browser navigation, YouTube, files, apps, and hardware telemetry.
- **🧩 Zero-Code Plugin Engine**: Drop any .py file into plugins/ and JARVIS dynamically registers the skill on launch with crash isolation.
- **⏰ Scheduled Routines**: Weekday morning weather and calendar briefings persist in `config/routines.json` and can run through Gemini or Ollama.
- **📱 Remote Controls**: The dashboard can enable/disable plugins, run routines, and send commands while Gemini is offline.
- **👁️ Screen Awareness**: Ask “What am I looking at?” to send the current screen to the vision session for analysis.

---

## 📋 System Prerequisites

| Component | Minimum Requirement | Recommended |
|---|---|---|
| **Operating System** | Windows 10/11 (64-bit) | Windows 11 (64-bit) |
| **Python** | Python 3.11 | Python 3.11 |
| **GPU (Optional)** | CPU supported | NVIDIA GPU (CUDA 11/12) for fast Whisper STT |
| **Virtual Audio** | Required for WhatsApp Voice Bridge | [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) |
| **Local LLM** | Ollama | [Ollama](https://ollama.com/) with llama3.2 |

---

## 🛠️ Step-by-Step Setup Guide

### 1. Clone the Repository

`powershell
git clone https://github.com/deestudio028-droid/jarvis.git
cd jarvis
`

### 2. Set Up a Python Virtual Environment

`powershell
python -m venv venv
.\venv\Scripts\activate
`

### 3. Install Dependencies

Install all required packages including UI, audio, speech, and Windows automation libraries:

`powershell
pip install -r requirements.txt
`

> **Note for PyTorch with CUDA**: If you want GPU acceleration for Whisper on NVIDIA hardware, ensure PyTorch with CUDA is installed:
> `powershell
> pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
> `

### 4. Configure Application Settings

Copy the example configuration file and add your credentials:

`powershell
Copy-Item config\api_keys.json.example config\api_keys.json
`

Edit config/api_keys.json:
`json
{
    "gemini_api_key": "YOUR_GEMINI_API_KEY",
    "os_system": "windows",
    "camera_index": 0,
    "llm_provider": "ollama",
    "llm_model": "llama3.2",
    "llm_url": "http://localhost:11434",
    "plugins_enabled": {
        "whatsapp_monitor": true,
        "whatsapp_voice_bridge": true
    },
    "assistant_name": "JARVIS",
    "user_name": "Sir",
    "ui_color": "#00d4ff"
}
`

### 5. Install and Start Ollama (for Local Intelligence)

1. Download and install Ollama from [https://ollama.com](https://ollama.com).
2. Pull the configured model:
   `powershell
   ollama pull llama3.2
   `
3. Start the Ollama server:
   `powershell
   ollama serve
   `

When Gemini Live is unavailable, dashboard and text commands automatically use the configured Ollama model. The default routine is weekdays at 08:00 for Istanbul; edit `config/routines.json` or use the dashboard controls to change it. Calendar events are read from Outlook when available.

### 6. Setup VB-Audio Virtual Cable (for WhatsApp Voice Bridge)

To enable two-way AI voice calls through WhatsApp:
1. Download and install **VB-Audio Virtual Cable** from [https://vb-audio.com/Cable/](https://vb-audio.com/Cable/).
2. Open **WhatsApp Desktop** -> **Settings** -> **Audio & Video**:
   - Set **Microphone** to: CABLE Output (VB-Audio Virtual Cable)
   - Set **Speakers** to: Default System Speaker (Headphones / Speakers)

---

## 🚀 Running the Assistant

### Launching the Full JARVIS HUD Interface
Starts the futuristic PyQt6 HUD with visual waveforms, telemetry, camera feed, and Gemini Live streaming:

`powershell
python main.py
`

### Launching the Autonomous WhatsApp Voice Bridge
Initiates an autonomous 2-way AI phone conversation with a specific contact:

`powershell
python live_test_bridge.py "<contact_name>" --debug-audio
`
*Example:*
`powershell
python live_test_bridge.py "My World" --debug-audio
`

**Conversation Flow:**
`	ext
WhatsApp Call Initiated
       ↓
Remote Person Answers
       ↓
WASAPI Loopback Captures Audio
       ↓
Adaptive VAD Detects Speech
       ↓
Whisper Transcribes Speech (CUDA)
       ↓
Ollama (llama3.2) Generates Concise Response
       ↓
EdgeTTS Speaks Response into Virtual Audio Cable
       ↓
Remote Person Hears JARVIS in Real Time
       ↓
(Acoustic Cooldown & Self-Hearing Discard)
       ↓
Next Turn Repeats Continuously
`

---

## 🧪 Testing and Verification

Run the automated test suite (50 unit tests covering call logic, audio loopback recovery, VAD adaptation, and LLM 404 resilience):

`powershell
python -m unittest discover tests
`

To run a standalone audio backend and loopback diagnostic:
`powershell
python -c "from live_test_bridge import diagnostic_audio_test; diagnostic_audio_test()"
`

To run an Ollama readiness and LLM streaming diagnostic:
`powershell
python -c "from core.llm_client import check_llm_readiness; check_llm_readiness()"
`

---

## 📁 Repository Structure

`	ext
jarvis/
├── main.py                          # Main entry point & Gemini Live loop
├── ui.py                            # Futuristic PyQt6 interface & HUD
├── setup.py                         # First-time configuration wizard
├── live_test_bridge.py              # WhatsApp 2-way live conversation bridge runner
├── requirements.txt                 # Project dependencies
├── core/
│   ├── llm_client.py                # Ollama & OpenAI API streaming client
│   ├── stt.py                       # Faster-Whisper (CUDA) & Vosk offline STT
│   ├── tts.py                       # EdgeTTS & local TTS player with device routing
│   └── plugin_loader.py             # Dynamic plugin discovery & crash isolation
├── plugins/
│   ├── whatsapp_voice_bridge.py     # 2-way audio call state machine & VAD
│   ├── whatsapp_desktop_call.py     # WhatsApp Desktop UIA / keyboard automation
│   ├── whatsapp_monitor.py          # Notification monitoring
│   └── ky_ufo_drone.py              # Drone flight control plugin
├── tests/
│   ├── test_whatsapp_voice_bridge.py # 50 unit tests for bridge and audio safety
│   ├── test_whatsapp_desktop_call.py # Tests for UI automation
│   └── test_ky_ufo_drone.py         # Tests for drone telemetry & commands
└── config/
    └── api_keys.json.example        # Configuration template
`

---

## ⚠️ License

Personal and non-commercial educational use. Licensed under **[Creative Commons BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**.
