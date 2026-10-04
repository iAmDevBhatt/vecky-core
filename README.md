# V.E.C.K.Y — Personal AI Desktop Assistant

A voice-first desktop AI assistant for Windows (with partial macOS/Linux support), built around **Google's Gemini Live API** (native audio, real-time speech-to-speech). It has a full-screen animated HUD (PyQt6), can see your screen/webcam, control your computer, browse the web, write and run code, manage files, send messages, track Steam/Epic downloads, and remembers what it learns about you across sessions — plus a phone-pairable remote-control web dashboard.

A real, runnable desktop app that acts as your own personal AI.

---

## Features

- **Real-time voice conversation** — talk naturally, VECKY listens, thinks, and replies with voice (Gemini `gemini-2.5-flash-native-audio-preview-12-2025`, no separate STT/TTS step needed for the main assistant).
- **Vision** — "look at my screen" / "look at the camera" and VECKY analyzes what it sees.
- **Computer control** — open apps, control volume/brightness/window management, take screenshots, type/click/scroll via AI-located screen elements.
- **Browser automation** — drives your *real* Chrome/Edge/Firefox/Brave/Opera/Vivaldi/Safari profile (via Playwright) to search, navigate, fill forms, and click things — cookies and logins included.
- **File intelligence** — drag & drop (or point at) almost any file type (images, PDFs, Office docs, CSV/Excel, JSON, code, audio, video, archives, PPTX) and ask VECKY to summarize, convert, transcribe, fix, translate, OCR, etc.
- **Code helper & dev agent** — write/edit/explain/optimize/run a single file, or have VECKY plan, scaffold, install dependencies for, and iteratively debug an entire multi-file project.
- **Desktop management** — organize/clean the desktop, set wallpaper (local or from a URL), or describe an arbitrary desktop task in natural language (executed in a restricted sandbox).
- **Messaging** — sends WhatsApp/Telegram/Discord/Signal/Instagram/Messenger messages by driving the desktop or web app.
- **Reminders** — schedules real OS-level reminders (Task Scheduler / launchd / cron+at) with a popup + sound notification, independent of VECKY running.
- **Game library management** — lists, installs, and updates Steam/Epic Games titles; can auto-shutdown the PC when a download finishes.
- **Flights & weather** — searches Google Flights (via browser automation + AI parsing) and pulls up weather reports.
- **Persistent memory** — silently remembers identity, preferences, projects, relationships, and plans across restarts, and works it naturally into conversation and startup briefings.
- **Proactive check-ins** — after a period of silence, VECKY may speak up on its own with something timely or useful, based on time of day and what it knows about you.
- **System monitor** — watches CPU/RAM/GPU/temperature and proactively warns you if something is critical.
- **Remote control dashboard** — a local (optionally HTTPS) web app you pair with your phone via QR code; stream your phone's microphone to VECKY, send typed commands, and share files, all AES-256 encrypted end-to-end at the application layer.

---

## Requirements

- **Python 3.11+** (uses `async with ... TaskGroup()` and `except*` — Python 3.11 syntax)
- A **Google Gemini API key** ([Google AI Studio](https://aistudio.google.com/))
- **Windows** is the primary/best-supported target (most OS-specific automation paths are implemented for Windows first, macOS/Linux second). Many features degrade gracefully or are simply unavailable outside Windows.
- A working microphone and speakers.
- `ffmpeg` on your `PATH` for video/audio processing features (trim, compress, transcribe, extract audio/frame).

There is no `requirements.txt`/`pyproject.toml` in this repo — dependencies are pulled from imports across the codebase. See **Dependencies** below.

---

## Installation

```bash
git clone <this-repo>
cd vecky-core
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install PyQt6 pillow psutil sounddevice numpy requests \
    google-genai mss opencv-python send2trash python-pptx \
    youtube-transcript-api ddgs playwright pandas openpyxl \
    python-docx pdfplumber PyPDF2 pydub qrcode[pil] \
    fastapi "uvicorn[standard]" cryptography python-multipart

playwright install chromium

# Windows only — desktop automation / volume / shortcuts / game install dialogs:
pip install pyautogui pyperclip pygetwindow comtypes pycaw win10toast pywinauto wmi pynvml
```

> A best-effort auto-installer exists at `core/installer.py` (`install_for_config`) that installs missing packages for a chosen STT/TTS engine combo, but it belongs to an **alternate local-LLM pipeline** (see [AI.md](AI.md)) and is not invoked by `main.py`'s default startup path today. Install manually as above.

## First run

```bash
python main.py
```

On first launch, a setup overlay appears asking for:
1. Your **Gemini API key**
2. Your **operating system** (auto-detected, but confirm/override)

This writes `config/api_keys.json` (git-ignored — created at runtime, not shipped):

```json
{
    "gemini_api_key": "AIza...",
    "os_system": "windows"
}
```

VECKY then connects to the Gemini Live API and greets you with a short morning briefing (time + live news headlines).

## Configuration reference (`config/api_keys.json`)

| Key | Set by | Meaning |
|---|---|---|
| `gemini_api_key` | Setup overlay | Google Gemini API key — required for `"assistant_mode": "gemini"` |
| `os_system` | Setup overlay | `windows` \| `mac` \| `linux` — drives OS-specific automation branches |
| `camera_index` | Auto (first vision-camera use) | Cached working webcam index, avoids re-probing every call |
| `assistant_mode` | Manual (optional) | `"gemini"` (default) or `"local"` — see **Local mode** below |
| `llm_url`, `llm_model` | Manual, local mode only | Ollama server URL + model name (e.g. `http://<host>:11434`, `gemma3:4b`) |
| `tts_api_url` | Manual, local mode only | URL of the `remote/tts_server.py` Kokoro wrapper (e.g. `http://<host>:8001`) |

---

## Local mode (experimental)

Instead of Gemini Live, VECKY can run against a **self-hosted Ollama model** for chat/vision and a **remote Kokoro TTS service** for spoken replies — no Gemini API key needed. Set `"assistant_mode": "local"` in `config/api_keys.json`.

This is an early, deliberately scoped-down mode:
- **Text input only** — type in the Command Input box; there's no speech-to-text yet.
- **No tool-calling** — it can talk and describe your camera/screen (say something with "camera" or "screen" in it), but it can't open apps, browse, or use any of the other tools Gemini mode has.
- Requires an Ollama server reachable on your network with a vision-capable model pulled (e.g. `gemma3:4b`, `llava:7b`), and the small FastAPI wrapper in `remote/tts_server.py` running next to your Kokoro install (see `remote/README.md` for deployment).

See `AI.md` for the `VeckyLocal` implementation details and what's intentionally left out.

---

## Running

```bash
python main.py
```

- **F4** — mute/unmute the microphone
- **F11** — toggle fullscreen
- **Esc** — interrupt VECKY mid-speech
- Type in the **Command Input** box to send text instead of voice
- Drop a file onto the **File Upload** zone to have VECKY analyze/process it
- Click **Remote Control** to get a QR code / 6-character key for phone pairing (opens the dashboard on `http://<your-LAN-ip>:8000`, or `https://` if you've placed real certs in `config/certs/`)
- Click **Create Desktop Shortcut** for a one-click launcher (no console window, arc-reactor icon)

---

## Architecture

```
main.py            ← entry point: connects to Gemini Live, owns the async
                      audio pipeline (mic in / speaker out), declares every
                      tool (TOOL_DECLARATIONS) and dispatches tool calls to
                      actions/*.py
ui.py               ← PyQt6 HUD window (VeckyUI/MainWindow) — animated
                      "arc reactor" face, system-metric sidebars, activity
                      log, file drop zone, command box, remote-control /
                      setup overlays, live camera view
actions/            ← one module per tool VECKY can call (open apps,
                      browser control, file ops, code generation, desktop
                      automation, messaging, games, flights, weather, …)
core/               ← STT/TTS engines + a local-LLM (Ollama/LM Studio)
                      client — an alternate assistant pipeline, currently
                      not wired into main.py (see AI.md)
memory/             ← persistent JSON long-term memory (identity,
                      preferences, projects, relationships, wishes, notes)
                      + config helpers
dashboard/          ← FastAPI + WebSocket remote-control web app
                      (phone pairing, mic streaming, file sharing)
config/             ← runtime config (api_keys.json, created on first run),
                      TLS certs for the dashboard, app icon
```

Voice loop, in short: mic audio → Gemini Live session (native audio in/out) → when Gemini decides to call a tool, `main.py` runs the matching `actions/*.py` function in a thread executor → the string result is sent back to Gemini as the tool response → Gemini continues speaking. Screen/camera captures are injected as an extra turn right after the tool response, since the Live API can't attach images to function results directly.

---

## Dependencies

Grouped by what they're for (all imported somewhere in the codebase):

- **Core / UI**: `PyQt6`, `pillow`, `psutil`
- **Gemini**: `google-genai`
- **Audio**: `sounddevice`, `numpy`
- **Web search**: `requests`, `ddgs` (or `duckduckgo-search`)
- **Vision / camera**: `mss` (screen capture), `opencv-python` (webcam)
- **Browser automation**: `playwright` (+ `playwright install chromium`)
- **Desktop/computer control**: `pyautogui`, `pyperclip` (Windows/macOS/Linux); `pygetwindow`, `comtypes`, `pycaw`, `win10toast`, `pywinauto`, `wmi`, `pynvml` (Windows only)
- **Files**: `send2trash`, `python-pptx`, `pandas`, `openpyxl`, `python-docx`, `pdfplumber` / `PyPDF2`, `pydub` (+ system `ffmpeg`)
- **YouTube**: `youtube-transcript-api`
- **Remote dashboard**: `fastapi`, `uvicorn[standard]`, `cryptography`, `python-multipart` (optional, needed for file upload), `qrcode[pil]`
- **Game library** (Windows): `pywinauto`, `numpy` (avatar-detection screenshot logic)
- **Alternate local-LLM pipeline** (`core/`, not on the main path): `requests`, plus optionally `faster-whisper`/`vosk` (STT) and `edge-tts`/`kokoro`+`soundfile`/ElevenLabs via `requests` (TTS)

---

## Known limitations

- No automated test suite, CI, or `requirements.txt`/`pyproject.toml` currently in the repo.
- This is not a git repository at the moment — no commit history, `.gitignore`, or `LICENSE`.
- Deep OS integration (volume via `pycaw`, brightness via WMI, game-install dialog automation via `pywinauto`, desktop shortcuts via `win32com`/VBScript) is Windows-first; macOS/Linux equivalents exist for many but not all actions.
- `config/api_keys.json` holds your Gemini API key in plaintext on disk — keep the repo/machine private, and don't commit that file.
- The remote dashboard binds to `0.0.0.0` on your LAN and will try to auto-open a firewall port (with a UAC/sudo prompt) — review `dashboard/server.py::_ensure_network_access` before running on an untrusted network.

## Security notes

- Remote dashboard traffic is protected at the application layer with **AES-256-CBC**, keyed from a one-time 6-character pairing code (QR or manual) — separate from transport-layer HTTPS, which uses a self-signed cert in `config/certs/` if present, falling back to plain HTTP otherwise.
- File and computer-control actions restrict writes/reads to paths under the user's home directory (`_is_safe_path` in `actions/file_controller.py`, `_safe_screenshot_path` in `actions/computer_control.py`).
- Destructive computer actions (`restart`, `shutdown`) require an explicit `confirmed=yes` round-trip before executing.
