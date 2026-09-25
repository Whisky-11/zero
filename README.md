# Zero

Zero is Ahmad's personal voice assistant — a JARVIS-style agent running locally. Say the wake word, speak, and Zero answers in a British voice with full tool access (shell, files, web) and persistent memory.

Runs on **Windows** (CUDA/NVIDIA) and **macOS** (CPU/MPS, no CUDA required).

## Quickstart

### Windows setup

#### Prerequisites

1. **Python 3.10** — Zero's venv targets 3.10.
2. **espeak-ng** — Required by Kokoro TTS. Download the MSI from https://github.com/espeak-ng/espeak-ng/releases and install it. Verify: `espeak-ng --version`.
3. **CUDA GPU** — faster-whisper uses CUDA for transcription. CUDA 12.1 and cuDNN 9 must be installed.
4. **Claude Code subscription** — Zero uses the Claude Code CLI (subscription auth). Do **NOT** set `ANTHROPIC_API_KEY` — Zero asserts this key is unset and will refuse to start if it is set (to avoid accidental per-token billing).

#### Install

```powershell
# From C:\Users\moze1\zero
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cu121
python -c "import openwakeword; openwakeword.utils.download_models()"
```

### macOS setup

```bash
brew install python@3.10 espeak-ng portaudio
cd zero && python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install torch torchaudio          # plain (CPU/MPS) build, no CUDA index on Mac
python -c "import openwakeword; openwakeword.utils.download_models()"
python -m zero                         # say "hey jarvis" (or "hey zero" if you copied the model)
bash install.sh                        # optional: autostart via LaunchAgent
```

#### Zero.app — menu bar, HUD window, Mac control (recommended on macOS)

From a fresh clone, one command does everything — Homebrew deps, the venv, all
models (so the first wake doesn't stall), tests, then builds and opens the app:

```bash
bash macos/setup.sh             # or --no-app to stop after venv + models
```

It is safe to re-run. The pieces on their own: `python -m zero.prefetch` (download
models), `bash macos/install-app.sh` (build ~/Applications/Zero.app, retire the old
LaunchAgent, add to Login Items, open).

Zero now lives in the **menu bar**: `…` loading → `◯` idle → `◉` listening → `◌` thinking → `◍` speaking (`⊘` = mic muted).
The menu has **Talk** (push-to-talk, also **⌥Space** from any app), **Type to Zero…**, **Mute microphone**,
**Stop speaking**, **Open HUD** (native window with a type box, push-to-talk, mute and on-screen confirmations),
**Open at login** and **Quit**.

Grant these to **Zero** once. The menu bar's **Permissions** item shows ✓/✗ for each (it
updates live) and clicking one triggers the system prompt and opens the right Settings pane;
Zero also notifies you at launch if something is missing:

| Permission | Why |
|---|---|
| Microphone | hearing you |
| Accessibility | clicking, typing, key presses, reading buttons, the ⌥Space hotkey |
| Screen Recording | screenshots (quit + reopen Zero after granting) |
| Automation | asked per app the first time Zero scripts it (Music, Mail, Safari…) |

How it works: `Zero.app` contains only a small signed native launcher (`macos/launcher.c`) that runs this
repo's `.venv` Python as its child, so macOS attributes every permission to Zero and **code changes need no
rebuild** — just Quit and reopen. Rebuild (`bash macos/build-app.sh ~/Applications`) only if you move the repo
or change the launcher. Ad-hoc signing means a rebuild may re-ask for permissions; set
`ZERO_SIGN_ID="Apple Development: …"` to sign with a real certificate and keep them. The installer retires the
old LaunchAgent (`install.sh`) so two Zeros never fight over the mic.

**What Zero can do on the Mac** (the `mac` tools, `zero/mac.py`): screenshot the screen; list windows and the
clickable elements of the front window; press buttons by name; click / scroll / type / key combos; open,
focus and quit apps; open URLs, files and folders; run AppleScript/JXA and Shortcuts; clipboard, volume and
notifications. Try: *"open Safari and search flights to Dubai"*, *"play my Focus playlist in Music"*,
*"what's on my screen?"*, *"run my Morning shortcut"*.

**Safety** (`zero/gate.py`, `[mac]` + `[gate]` in `config.toml`): looking is always allowed. Clicks and
typing are allowed in ordinary apps but need a **spoken (or on-screen) yes** in `sensitive_apps` (Mail,
Messages, Terminal, password managers, System Settings…) or everywhere with `confirm_input = true`.
AppleScript, Shortcuts, quitting apps and opening executables always confirm; shelling out to `osascript`,
`sudo`, `killall`, `launchctl`, `defaults write`… confirms too, so the shell is no way around the gate.
Requests typed in the HUD are confirmed in the HUD (or a native dialog when no HUD is open).

**Action log**: every tool Zero tries — and whether it was allowed, confirmed, declined or
denied — is appended to `data/audit.ndjson` (rotates at 5 MB) and shown live in the HUD
transcript (`→ press "Send" in Mail  CONFIRMED`).

**macOS notes:**
- STT runs on **CPU** (no CUDA), so it is slower. Consider setting `[stt] model = "tiny"` or `"base"` in `config.toml` for speed.
- Do **NOT** set `ANTHROPIC_API_KEY` — Zero uses the Claude Code subscription; a set key causes startup failure.
- The custom `hey_zero.onnx` wake model is gitignored. A fresh clone wakes on **"hey jarvis"** until you copy the model into `zero/models/`.
- `[stt] device = "auto"` (the default) auto-selects CUDA on Windows/NVIDIA and CPU on Mac — no manual change needed.

### Run (interactive voice mode)

```powershell
# Confirm ANTHROPIC_API_KEY is NOT set
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue

cd C:\Users\moze1\zero
.\.venv\Scripts\python.exe -m zero
```

Say **"hey jarvis"** to wake Zero, then speak your request.

### Run (text dev mode — no microphone needed)

```powershell
.\.venv\Scripts\python.exe -m zero --text
```

Type at the `you>` prompt; Zero replies in text (no TTS).

### HUD

Open `http://localhost:911` in a browser after starting Zero. The HUD shows the current state (idle / listening / thinking / speaking) and the last activity. The WebSocket server runs on port 8765.

### Autostart at logon

Run once (as Administrator if needed):

```powershell
powershell -File C:\Users\moze1\zero\install.ps1
```

This registers a `StartZero` scheduled task that launches Zero at logon using `pythonw.exe` (no console window). To start it immediately without logging out:

```powershell
Start-ScheduledTask StartZero
```

To remove the task:

```powershell
Unregister-ScheduledTask -TaskName StartZero -Confirm:$false
```

## File layout

```
zero/
  config.py       load config.toml -> typed Config
  audio.py        Mic capture + playback (sounddevice, 16 kHz)
  wake.py         WakeListener (openWakeWord hey_jarvis) + FrameBuffer
  stt.py          Recorder (silero-vad endpoint) + Transcriber (faster-whisper CUDA)
  voice.py        Voice.speak() — Kokoro bm_george British, sentence streaming
  memory.py       SQLite store + remember/recall MCP tools
  gate.py         classify(tool, input) -> ALLOW/CONFIRM/DENY + PreToolUse hook
  brain.py        Brain — ClaudeSDKClient on subscription, persona + memory + gate
  hud.py          WebSocket server (8765) + HTTP server (911, serves ui/)
  orchestrator.py Wake->listen->think->speak loop; confirm gate; push-to-talk, mute, typed turns
  mac.py          Mac control MCP tools: screen, mouse, keyboard, apps, AppleScript, Shortcuts
  app.py          macOS menu-bar app + global hotkey  (python -m zero --app)
  window.py       native HUD window via pywebview     (python -m zero --window)
  paths.py        repo-relative paths (the app may start from any directory)
  permissions.py  check/request Mic, Accessibility, Screen Recording (python -m zero.permissions)
  audit.py        data/audit.ndjson — every tool decision
  prefetch.py     download all models up front (python -m zero.prefetch)
  __main__.py     Entrypoint: python -m zero  (or --text / --app / --window)
macos/
  launcher.c      Zero.app's executable: runs .venv python as a child, fixes PATH, restarts on crash
  Info.plist      bundle id com.ahmad.zero, menu-bar only, privacy prompt strings
  build-app.sh    build + sign Zero.app;  install-app.sh  install, login item, open
  setup.sh        fresh clone → running Zero.app in one command
ui/
  index.html      Minimal JARVIS HUD (monochrome; full WebGL is Plan 4)
prompts/
  zero.md         Zero persona system prompt
config.toml       All tuneable parameters
data/
  zero.db         SQLite memory + conversation log (auto-created on first run)
```

## Configuration

Edit `config.toml` to tune Zero's behaviour:

| Section | Key | Default | Notes |
|---------|-----|---------|-------|
| `[wake]` | `model` | `hey_jarvis` | Swap to custom `zero.onnx` (Task 11) |
| `[wake]` | `threshold` | `0.5` | Raise to reduce false triggers |
| `[stt]` | `model` | `small` | `tiny`/`base`/`small`/`medium`/`large-v3` |
| `[brain]` | `model` | `claude-opus-4-7` | Main model for complex requests |
| `[brain]` | `trivial_model` | `claude-3-5-haiku-20241022` | Fast model (wired in Plan 2) |
| `[hud]` | `http_port` | `9911` | The Porsche reference (>1024 so macOS allows it) |
| `[mac]` | `confirm_input` | `false` | `true` = every click/keystroke needs a yes |
| `[mac]` | `sensitive_apps` | Mail, Messages, Terminal… | clicks/typing here always confirm |
| `[app]` | `hotkey` | `alt+space` | push-to-talk from anywhere (needs Accessibility) |
| `[app]` | `window_on_top` | `false` | keep the HUD window above others |

## ANTHROPIC_API_KEY — must be unset

Zero uses the Claude Code subscription (not direct API billing). If `ANTHROPIC_API_KEY` is present in the environment, Zero will raise `SubscriptionKeyError` at startup and refuse to run. This is intentional — it prevents accidental per-token charges.

To check: `$env:ANTHROPIC_API_KEY` should be empty or unset.

## Running tests

```powershell
# Fast tests (no hardware, no network)
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Hardware/subscription smoke tests (mic, GPU, Claude)
.\.venv\Scripts\python.exe -m pytest tests/ -v -m manual
```

## What's next (follow-on plans)

- **Plan 2:** Semantic recall (embeddings), auto-capture memory from conversation, vault profile sync.
- **Plan 3:** Barge-in (interrupt speaking), full supervision/audit log, resilience polish.
- **Plan 4:** Full WebGL HUD (the real JARVIS look).
- **Task 11 (optional):** Custom "Zero" wake word (~1 hr synthetic training via openWakeWord Colab).
