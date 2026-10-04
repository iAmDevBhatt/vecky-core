# AI.md — Guide for AI coding agents working in this repo

This file exists for AI agents (Claude, Copilot, etc.) editing this codebase. It documents conventions, wiring, and gotchas that aren't obvious from reading a single file in isolation. Read this before adding a tool, touching `main.py`, or making cross-cutting changes.

## What this project is

A Windows-first (partial macOS/Linux) desktop AI assistant. `main.py` holds a persistent **Gemini Live API** session (`models/gemini-2.5-flash-native-audio-preview-12-2025`) that does real-time speech-to-speech: mic audio streams in, model audio streams out, and the model can call **function tools** mid-conversation. Every tool is a Python function in `actions/`. `ui.py` is a PyQt6 HUD that's driven from a background asyncio thread via Qt signals (`VeckyUI` wraps `MainWindow` and exposes a small thread-safe API).

There is also a second, lighter-weight **local mode** (`VeckyLocal` in `main.py`) that talks to a self-hosted Ollama model + a remote Kokoro TTS service instead of Gemini — see the pipelines section below.

There is no git repo, no test suite, no `requirements.txt`/`pyproject.toml`, and no CI in this working copy — don't assume any of those exist or try to run tests.

## Repo map (what lives where)

```
main.py                    Gemini Live session, TOOL_DECLARATIONS, tool dispatch (_execute_tool),
                            audio in/out pipeline, morning briefing, proactive mode, system monitor loop
ui.py                       VeckyUI (public, thread-safe) → MainWindow (PyQt6) → HudCanvas / widgets
actions/*.py                one file per tool; each exposes a single public entry function
core/llm_client.py          Ollama / OpenAI-compatible (LM Studio etc.) chat client — SEPARATE pipeline
core/stt.py, core/tts.py    offline STT (Whisper/Vosk) and TTS (EdgeTTS/Kokoro/ElevenLabs) engines
core/installer.py           dependency installer keyed off an stt_engine/tts_engine config — for that
                            separate pipeline, not called by main.py's Gemini Live path
core/prompt.txt             system prompt injected into the Gemini Live session (persona + tool-routing
                            rules) — read by main.py::_load_system_prompt()
memory/memory_manager.py    load_memory/update_memory/format_memory_for_prompt over memory/long_term.json
memory/config_manager.py    api_keys.json helpers (separate from config/__init__.py — see gotchas)
memory/long_term.json       persisted user memory: identity/preferences/projects/relationships/wishes/notes
dashboard/server.py         FastAPI + WebSocket remote control (phone pairing, mic relay, commands, files)
dashboard/static/*.html     dashboard frontend (vanilla JS + CryptoJS for AES)
config/__init__.py          get_os()/is_windows()/is_mac()/is_linux() helpers, reads config/api_keys.json
config/api_keys.json        created at first run by ui.py's setup overlay (or hand-written for local
                            mode, see below) — runtime state, don't assume its contents, never commit
                            real secrets into it
remote/tts_server.py        FastAPI wrapper around a Kokoro TTS venv — NOT run by this codebase; it's
                            deployed to and runs on a separate machine (see remote/README.md). Kept
                            here only so the code that VeckyLocal's _speak() talks to over HTTP is
                            version-controlled. Edits here have zero effect until redeployed.
```

## Two assistant pipelines exist in this repo, selected by `config/api_keys.json`'s `"assistant_mode"` field

`main.py::main()` reads `assistant_mode` (`_get_assistant_mode()`) and constructs either class:

1. **`"gemini"` (default)** → `VeckyLive`. Gemini Live API does STT + LLM + TTS in one streaming session, plus the full `TOOL_DECLARATIONS` tool-calling system described below.
2. **`"local"`** → `VeckyLocal`. Talks to a self-hosted **Ollama** model (via `core/llm_client.py::get_llm_settings()` for the `llm_url`/`llm_model` config fields) for chat + vision, and a **remote Kokoro TTS HTTP wrapper** (`remote/tts_server.py`, deployed separately — see `remote/README.md`) for spoken replies, fetched over HTTP and played locally via `sounddevice`.

**`VeckyLocal` is intentionally minimal** — built as a fast first pass, not feature parity with Gemini mode:
- **No STT / voice input.** Input is text only, via the existing Command Input box (`ui.on_text_command`). Wiring up mic capture + Whisper/Vosk (`core/stt.py`, still unused) is the natural next step if asked.
- **No tool-calling.** None of `TOOL_DECLARATIONS` / `_execute_tool()` apply in local mode — it can talk and do vision, nothing else. Camera/screen vision is triggered by a dumb keyword match (`VeckyLocal._VISION_CAMERA_WORDS` / `_VISION_SCREEN_WORDS`) against the user's text, not real tool-calling, because the currently-pulled Ollama models don't reliably declare tool-calling support. If asked to add tools to local mode, that keyword hack should probably be replaced with Ollama's native `tools` param (see `call_llm()` in `core/llm_client.py`, which already supports it) on a model that actually supports function calling (e.g. qwen2.5, llama3.1) — check what's pulled on the Ollama host before assuming it'll work.
- `core/stt.py` and `core/tts.py` (the EdgeTTS/Kokoro-in-process/ElevenLabs engines) are **still unused** — `VeckyLocal` talks to Kokoro over HTTP via `remote/tts_server.py` instead of importing the `kokoro` package directly, so nothing local needs `torch`/`transformers` installed. `core/installer.py` is also still unused by either pipeline.

If asked to "make STT/TTS configurable" or "add Ollama support" going forward, this local-mode groundwork already exists — extend `VeckyLocal` rather than assuming you're starting from scratch.

## How the tool-calling system works

1. **Declare** the tool's JSON schema in `main.py::TOOL_DECLARATIONS` (a list of dicts with `name`, `description`, `parameters` in Gemini's function-declaration format).
2. **Dispatch** it in `main.py::VeckyLive._execute_tool()` — a long `if name == "...":` / `elif` chain. Each branch calls `loop.run_in_executor(None, lambda: some_action(parameters=args, player=self.ui))` and stores the string result in `result`. Blocking/sync action code always runs via `run_in_executor`, never awaited directly, since almost nothing in `actions/` is async (the one exception: `browser_control`, which manages its own internal asyncio loop, and `screen_processor`, which owns a separate Gemini Live session).
3. The function's return value is wrapped in `types.FunctionResponse(id=fc.id, name=name, response={"result": result})` and sent back to the model.

### Adding a new tool — checklist

1. Create `actions/my_tool.py` with a public function matching this signature convention:
   ```python
   def my_tool(parameters: dict, response=None, player=None, session_memory=None) -> str:
       ...
       return "Human-readable result string."
   ```
   (`response` and `session_memory` are vestigial params kept for signature consistency across modules — most implementations ignore them. `player` is the live `VeckyUI` instance — use `player.write_log(...)` to post to the on-screen activity log, and `player.show_content(title, text)` if you want to show a larger result in the collapsible content panel.)
2. Add an entry to `TOOL_DECLARATIONS` in `main.py` describing the tool and its parameters (Gemini `OBJECT`/`STRING`/`INTEGER`/`BOOLEAN`/`ARRAY` schema types).
3. Import the function at the top of `main.py` alongside the other `actions.*` imports.
4. Add an `elif name == "my_tool":` branch in `_execute_tool()` following the existing pattern (`run_in_executor` + fallback default message).
5. If the tool needs to *speak* mid-execution (e.g. progress updates like `dev_agent`/`code_helper`/`game_updater`/`flight_finder`/`youtube_video` do), accept an optional `speak=None` parameter and call `self.speak(...)` is passed through from `main.py` as `speak=self.speak` — check those modules for the pattern.
6. Keep the description in `core/prompt.txt` in sync if the tool changes cross-tool routing rules (e.g. "use X tool for Y, not Z tool").

## Conventions repeated across `actions/*.py` — reuse, don't reinvent

- **Base dir resolution**, copy-pasted near-verbatim in almost every action file:
  ```python
  def _base_dir() -> Path:
      if getattr(sys, "frozen", False):
          return Path(sys.executable).parent
      return Path(__file__).resolve().parent.parent
  ```
  This supports a future PyInstaller-frozen build. Any new module reading `config/api_keys.json` should follow the same pattern (or import `config.get_config()` / `config.get_os()` from `config/__init__.py` instead of hand-rolling it — several files do the latter, e.g. `flight_finder.py`, `game_updater.py`, `youtube_video.py`).
- **Gemini key loading** is duplicated per-file (`_get_api_key()` reading `config/api_keys.json → gemini_api_key`) rather than centralized. `memory/config_manager.py::get_gemini_key()` exists and does the same thing but most `actions/*.py` don't use it — be aware there are effectively three near-identical implementations of "read the API key" in this repo (`config/__init__.py::get_config()`, `memory/config_manager.py::load_api_keys()`, and per-file `_get_api_key()` helpers).
- **OS branching**: `platform.system()` → `"Windows" | "Darwin" | "Linux"`, usually normalized to a local `_OS` constant, or via `config.is_windows()/is_mac()/is_linux()`. Follow whichever pattern the file you're editing already uses.
- **Hidden subprocess windows on Windows**: every `subprocess.run`/`Popen` on Windows should pass `creationflags=subprocess.CREATE_NO_WINDOW` (commonly aliased as `_WIN_HIDE` or `_CNW` dict, spread with `**_WIN_HIDE`). `main.py` even monkey-patches `subprocess.Popen` globally at import time to force this — see the top of `main.py` — so this is largely redundant now but the per-call flags are still present in older files; keep the pattern when adding new subprocess calls for consistency.
- **Optional imports guarded with `try/except ImportError`** and a `_FOO = True/False` flag (e.g. `pyautogui`, `pyperclip`, `send2trash`, `cv2`, `mss`) — the tool functions then check the flag and return a friendly "X is not installed. Run: pip install X" string instead of crashing. Follow this pattern for any new optional dependency.
- **Gemini text-generation calls** (as opposed to the Live session) go through a tiny ad-hoc wrapper class defined inline in several files:
  ```python
  def _get_model(model_name="gemini-2.5-flash"):
      from google import genai
      _c = genai.Client(api_key=_get_api_key())
      class _W:
          def generate_content(self, contents):
              return _c.models.generate_content(model=model_name, contents=contents)
      return _W()
  ```
  This isn't shared — it's redefined per-file (`code_helper.py`, `dev_agent.py`). New code needing one-shot Gemini generation should probably just call `genai.Client(...).models.generate_content(...)` directly rather than adding yet another copy of this wrapper.

## Safety boundaries already in place — respect them

- `actions/file_controller.py` and `actions/computer_control.py` restrict file operations to paths under `Path.home()` via `_is_safe_path()` / `_safe_screenshot_path()`. Don't add file-write paths that bypass this without a good reason.
- `actions/file_controller.py::delete_file()` refuses to delete protected top-level folders (Desktop, Downloads, Documents, Pictures, Music, Videos, home) and uses `send2trash` (recoverable) rather than permanent deletion.
- `actions/desktop.py`'s AI-generated "arbitrary desktop task" code path (`_ask_gemini_for_desktop_action` + `_execute_generated_code`) runs LLM-generated code in a hand-built sandbox with a restricted `__builtins__` and module set (no `subprocess`, no `exec`/`eval`, no delete operations, no arbitrary imports). If you touch this, keep the sandbox at least as restrictive.
- `actions/computer_settings.py` gates `restart`/`shutdown` behind `_DANGEROUS_ACTIONS`, requiring the model to re-call with `confirmed=yes` — don't remove this confirmation round-trip.
- The dashboard (`dashboard/server.py`) authenticates every non-login endpoint via a bearer token minted from a one-time pairing key, and encrypts command/text payloads with AES-256-CBC derived from that same key (`_derive_key`/`_decrypt_cbc`). If extending the dashboard API, keep new endpoints behind the same `_auth(req)` check other endpoints use.

## `core/prompt.txt` — the system prompt

This is the actual persona/behavior spec sent to Gemini as `system_instruction` (see `main.py::_build_config()`, which concatenates: current date/time context + `format_memory_for_prompt(memory)` + this file's contents). It encodes tool-routing rules (e.g. "use `computer_settings` for all single OS actions," "call `screen_process` only once per request," language-mirroring rules, and the `[SYSTEM_ALERT]` / `[STARTUP_BRIEFING]` / `[PROACTIVE_CHECK]` sentinel-prefix conventions that other parts of the code use to inject non-user turns into the conversation). If you add a tool whose usage could be ambiguous relative to existing tools, add a routing rule here.

## Sentinel-prefixed injected turns

Several places send a synthetic user-role turn into the Live session to get the model to say something without it being literal user speech, using a `[TAG]` prefix the model is instructed (in `prompt.txt`) to never read aloud:
- `[SYSTEM_ALERT]` — from `SystemMonitor.check()` (CPU/RAM/GPU/temp thresholds), sent every ~10s from `_run_system_monitor()`.
- `[PROACTIVE_CHECK]` — from `ProactiveEngine.build_prompt()`, sent when the user's been silent long enough (`_run_proactive_mode()`).
- `[STARTUP_BRIEFING]` — mentioned in the prompt but the actual startup code (`_send_startup_briefing`/`_briefing_news_phase`) sends plain instructional text, not this literal tag; check `main.py` before assuming the tag is used verbatim.
- `[VISION_ACTIVE]` — returned as the tool-response text for `screen_process`, telling the model to say a filler sentence while the real image is prepared for the next turn (`_pending_vision` mechanism in `main.py`).
- `[FILE_UPLOADED]` — sent from `ui.py::_on_file_selected()` when a file is dropped, so the model can acknowledge it without a real user utterance.

If you add a new "inject a system-ish turn" mechanism, follow this same bracket-tag convention and document it in `prompt.txt` so the model knows not to vocalize the tag.

## Memory system

`memory/long_term.json` has exactly six top-level categories: `identity`, `preferences`, `projects`, `relationships`, `wishes`, `notes`. Each leaf is `{"value": ..., "updated": "YYYY-MM-DD"}`. Writes go through `update_memory()` (called from the `save_memory` tool in `main.py`, which is handled specially in `_execute_tool` — it returns immediately with `"silent": True` and never speaks). The store self-trims oldest-updated entries once it exceeds `MEMORY_MAX_CHARS` (2200 chars serialized). Don't add new top-level categories without updating `_empty_memory()`, `format_memory_for_prompt()`, and the `save_memory` tool's `category` enum description in `main.py`.

## UI threading model

`ui.py`'s `MainWindow` runs on the Qt main thread; `main.py`'s Gemini session runs on a background thread's asyncio loop. All cross-thread UI updates go through Qt signals defined on `MainWindow` (`_log_sig`, `_state_sig`, `_content_sig`, `_reconfig_sig`, `_camera_sig`, `_cam_stream_sig`, `_cam_frame_sig`) and the public `VeckyUI` wrapper class emits them via thread-safe `.emit()` calls — never call `MainWindow` widget methods directly from a non-Qt thread; go through the `VeckyUI` public methods (`write_log`, `set_state`, `show_content`, `prompt_reconfig`, `show_camera_frame`, `start_camera_stream`, `stop_camera_stream`) instead.

## Things that look like bugs/inconsistencies but may be intentional — verify before "fixing"

- `core/llm_client.py` **is** used now (by `VeckyLocal`, local mode). `stt.py`/`tts.py`/`installer.py` are still unused by either pipeline — don't delete them assuming dead code; they're likely next up for local-mode voice input.
- Three overlapping "read the Gemini API key" implementations exist (see above) — consolidating them is a reasonable refactor if asked, but check every caller (many files) before doing so.
- `dashboard/server.py` runs two uvicorn servers when HTTPS is enabled (`PORT` and `PORT+1`, both HTTPS) — this is intentional, to support both an app-served URL and a manually-typed `IP:PORT+1` URL that Chrome would otherwise HTTPS-upgrade and fail against a plain-HTTP server.
- Some action modules mix Turkish comments/log strings with English (`browser_control.py`, `desktop.py`, `game_updater.py`) — this reflects original authorship, not a translation bug; don't "fix" unless asked.
