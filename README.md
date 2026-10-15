# AI Workflow Studio — prototype v0.2

React + TypeScript + React Flow, FastAPI, SQLite. Windows-first / local-first.

## Windows startup

1. If installing `python-manager-26.4.msix` fails with `0x80070005`, **do not require MSIX**. Install **classic Python 3.12 x64 executable installer** from https://www.python.org/downloads/release/python-31210/ (Windows installer (64-bit)); check **Add Python to PATH**. Python 3.12.10 is the final full maintenance release with an executable installer in the 3.12 line. A newer 3.13 executable installer is also acceptable. Do not download Windows embeddable ZIP for this project.
2. Install Node.js LTS (includes npm): https://nodejs.org/en/download
3. For Audio Lab install FFmpeg, ensure `ffmpeg` works in a fresh terminal.
4. Unzip project to e.g. `C:\AI_Workflow_Studio` (avoid protected `Program Files` folder).
5. Run `DIAGNOSE_WINDOWS.bat`, then `START_WINDOWS.bat`.
6. Open http://127.0.0.1:5173; backend status http://127.0.0.1:8000/api/health; API docs http://127.0.0.1:8000/docs.

The Windows script creates `.venv`, installs Python requirements and npm packages; first run requires internet. **Do not run installers or application as Administrator unless specifically necessary.**

## What works (prototype)

- Save/load projects in SQLite; vertical studio and editable React Flow graph (edges persist, automatic graph execution is not implemented).
- Model-specific prompts and character profiles; upload and tag character refs as original, approved, rejected or model-specific (backend endpoint).
- OpenAI/OpenAI/PiAPI GPT chat, prompt adaptation and model jobs via documented adapter shapes; manual job status polling and result previews.
- OpenAI/PiAPI **planning agents** (3 sequential LLM calls) available in Agent panel; they do not automatically charge for image/video generation.
- Local Audio Lab uploads and trims authorized samples via FFmpeg, with silence-based clip suggestions.

## Limitations / safety

- **PiAPI Cloudflare 1010** on your network requires PiAPI support. The app does not bypass Cloudflare or spoof User-Agent. Other models/APIs are not proven working until tested with your authorized credentials.
- ElevenLabs and Fish Audio are **planned connectors**, not a working API integration in v0.1. Export WAV for manual use; voice ownership/consent required.
- The world Style Library is editable and saved with each project; real / approved / rejected / model-specific reference uploads are available in Character Vault. These assets are not yet automatically scored for visual continuity.
- Model schemas in `backend/main.py` are an initial *limited allowlist*; verify each against vendor docs before production, especially version changes and paid-generation settings.
- Keys are entered in the app and passed to the **local** backend per request; they are not written to SQLite. Do not expose port 8000 on a public interface. In cloud, use a server-side secrets vault and authentication.
- A project may store externally hosted reference URLs, which are not private. Avoid uploading sensitive reference images to untrusted hosting.

## Deploying to cloud later

Use PostgreSQL instead of SQLite, S3-compatible storage instead of local files, authentication, HTTPS reverse proxy, managed secrets, persistent job worker/queue, webhook verification, budget caps and per-user quotas. Do not expose this prototype as-is.

## Windows DISM / installer problems (independent of Studio)

If Windows 10 (build 19044) reports DISM error 2 at 56.6% while installing Python also reports installer errors 2502 / 2503, do not repeatedly change permissions on system folders. The project does not require Windows Python Manager MSIX. Use the classic Python .exe installer (per-user install). In an elevated Command Prompt, check `DISM /Online /Cleanup-Image /ScanHealth` and `sfc /scannow`; if DISM fails, export relevant messages from `C:\Windows\Logs\DISM\dism.log` and troubleshoot the missing source/file using official Windows repair guidance. Do not modify WinSxS manually. See WINDOWS_REPAIR_NOTES.md.

## Verified in development workspace

- Python module syntax (`py_compile`) — passed.
- FastAPI TestClient: `/api/health`, `/api/diagnostics`, `/api/model-specs`, `/api/projects` — passed.
- TypeScript TSX parsing of App and AgentPanel — passed.
- Complete `npm install` and React production build — **not verified** (dependency fetch timed out).
- Paid external provider calls — **not tested**.
