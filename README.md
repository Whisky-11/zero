# Zero

Zero is Ahmad's personal voice assistant — a JARVIS-style agent running locally on Windows. Say the wake word, speak, and Zero answers in a British voice with full tool access (shell, files, web) and persistent memory.

## Quickstart

### Prerequisites

1. **Python 3.10** — Zero's venv targets 3.10.
2. **espeak-ng** — Required by Kokoro TTS. Download the MSI from https://github.com/espeak-ng/espeak-ng/releases and install it. Verify: `espeak-ng --version`.
3. **CUDA GPU** — faster-whisper uses CUDA for transcription. CUDA 12.1 and cuDNN 9 must be installed.
4. **Claude Code subscription** — Zero uses the Claude Code CLI (subscription auth). Do **NOT** set `ANTHROPIC_API_KEY` — Zero asserts this key is unset and will refuse to start if it is set (to avoid accidental per-token billing).

### Install

```powershell
# From C:\Users\moze1\zero
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cu121
python -c "import openwakeword; openwakeword.utils.download_models()"
```

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
  orchestrator.py Wake->listen->think->speak loop; confirm gate; supervises
  __main__.py     Entrypoint: python -m zero  (or  python -m zero --text)
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
| `[hud]` | `http_port` | `911` | The Porsche reference |

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
