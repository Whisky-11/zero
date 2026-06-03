# Zero — Voice-First JARVIS Assistant · Design Spec

- **Date:** 2026-06-03
- **Owner:** Ahmad (Windows box `DESKTOP-JILN2NM`)
- **Status:** Design — awaiting review before implementation planning
- **Location:** `C:\Users\moze1\zero\`

## 1. Goal

A personal, JARVIS-style AI assistant named **Zero** that runs **locally** on Ahmad's always-on Windows PC, driven by **voice**, powered by the **Claude Agent SDK** on Ahmad's Claude Code subscription, with **full long-term memory** and a **JARVIS-style visual UI**. Zero addresses the user as **"Ahmad."**

## 2. Requirements (decided)

| # | Decision |
|---|---|
| Interface | **Voice-first** — wake word, speak, it speaks back |
| Activation | **Always-listening wake word "Zero"** (offline) |
| Capability | **Full agent** (all Claude Code tools) with **spoken confirmation before destructive actions** |
| Character | **JARVIS** — dry-witted, formal-but-warm British butler; addresses user as **"Ahmad"** |
| Voice | **Kokoro British** TTS (`bm_*`) |
| Memory | **Full long-term** — reads existing vault for "about Ahmad" + grows its own (transcripts, learned facts) |
| Brain | **Claude Agent SDK (Python)** from day one, on the Claude Code subscription |
| UI | **JARVIS HUD** — monochrome (black/white/gray), space/cosmic, 911 + aviation precision |

## 3. Non-goals / dropped scope

- **RVC custom voice cloning** — dropped from core (latency + setup cost). Kokoro British is the voice. RVC is an optional future experiment only.
- **`claude -p` phase** — skipped; building directly on the Agent SDK.
- **Renaming the profile folder to `C:\Users\AS`** — rejected (Microsoft-unsupported, high breakage). The account is named "AS"; the home folder stays `C:\Users\moze1`; Zero addresses the user as "Ahmad". All paths remain `C:\Users\moze1\...`.

## 4. Architecture

```
🎙 mic (always on)
  → wake.py    "Zero" wake word        [openWakeWord, offline]
  → stt.py     record + VAD endpoint + transcribe   [faster-whisper, local]
  → brain.py   Claude Agent SDK (persona, tools, memory, gate hook)  [subscription]
        ├─ gate.py    canUseTool → confirm destructive aloud
        └─ memory.py  recall in / capture out (SDK tools)
  → voice.py   Kokoro British, stream sentence-by-sentence
  → 🔊 speaker
        ↕ websocket
  → ui/        JARVIS HUD (state, waveform, live tool/memory feed)
```

**Design principle:** small modules behind clean interfaces. `orchestrator.py` depends only on the `Brain`, `Voice`, `Wake`, `STT` interfaces; `gate` sits between brain and tool execution; `memory` is the only module touching Zero's store + the vault. Swapping a component (e.g. Kokoro→RVC later) touches nothing else.

## 5. Components

### `wake.py`
Always-on mic capture; fires a `wake` event when it detects "Zero". openWakeWord (offline, free). Tunable sensitivity in config. On wake → emits a soft chime + hands the stream to `stt`.

### `stt.py`
After wake, records the utterance, endpoints on silence (VAD), transcribes via faster-whisper (local, GPU). Returns text. Empty/garbage/no-speech-within-timeout → silently return to sleep (handles false wakes).

### `brain.py` — the agent (Claude Agent SDK, Python)
- Long-running SDK session on Ahmad's **Claude Code subscription** (not API billing).
- **Persona** from `prompts/zero.md`: dry-witted, formal-but-warm British butler; concise; addresses user as **"Ahmad"**; the "about Ahmad" profile (from memory) injected at startup.
- **Tools:** full Claude Code toolset (bash, file read/write, web) + Ahmad's MCP servers + Zero's custom memory tools (`remember`/`recall`/`forget`).
- **Streaming** output → `voice` speaks sentence-by-sentence as Zero thinks (key for responsiveness). (SDK streams message/block-level; we chunk to sentences for TTS.)
- All tool calls pass through the SDK **`PreToolUse` hook** (`gate`) before execution.

**Auth & cost (verified on this machine 2026-06-03):** The Agent SDK runs on Ahmad's **Claude Code subscription** — it inherits the `claude login` session (CLI v2.1.161 present, logged in; **no `ANTHROPIC_API_KEY` set**). Credential precedence: if `ANTHROPIC_API_KEY` were ever set it would silently switch Zero to **paid per-token** — so Zero **asserts `ANTHROPIC_API_KEY` is unset at startup and warns if not**. Caveat: the plan's Agent-SDK use draws from a **monthly credit**; heavy 24/7 use can exhaust it and overflow to per-token rates. Efficiency measures (designed in): call the brain only on real commands (not every wake), keep context lean via memory recall, route trivial turns to a cheaper model, and the gate caps runaway tool loops.

### `voice.py`
`speak(text)` in Kokoro British (`bm_george`/`bm_lewis`). Streams: synth + play per sentence as the brain emits them. Barge-in: if the user speaks while Zero talks, stop and listen. TTS failure → beep + text log, never crash.

### `memory.py` — full long-term memory
- **Store:** SQLite `data/zero.db` — `messages` (turn transcripts) + `memories` (durable facts: text, tags, source=explicit|auto, embedding).
- **Knows you:** at startup reads the existing vault (`MEMORY.md` + key user/feedback files) → distills a compact "about Ahmad" profile into the system prompt. (Read-only; Zero's memory stays separate from the dev vault unless a fact is explicitly promoted.)
- **Recall (per turn):** top-k *relevant* memories (semantic search via a small local embedding model) + last few turns, injected into the brain.
- **Capture:** explicit ("Zero, remember that…" → stored + confirmed); automatic (conservative end-of-session extraction of durable facts); transcripts always logged.
- Exposed to the agent as **SDK custom tools** so Zero manages memory naturally.

### `gate.py` — safety gate
- Built on the SDK **`canUseTool`** permission hook (pre-execution).
- **Auto-allow:** reads, web, status checks, `recall`, non-mutating bash (`ls`, `git status`, `cat`).
- **Confirm aloud:** delete/overwrite, `git push`/`reset --hard`, shutdown/kill-process, mass edits, external publishing, or any **unknown mutating** tool (conservative default). Zero speaks the action and listens for a spoken yes/no (reuses STT; timeout/unclear → deny).
- **Hard never-list:** catastrophic patterns (`rm -rf /`-class, credential exfiltration) refused even if asked.
- Every decision **logged** (asked → answer → allow/deny) — audit trail. Allow/confirm/never lists live in `config.toml`.

### `ui/` — JARVIS HUD
- Local web app at **`http://127.0.0.1:911`** (the Porsche 911 — verified free + not in a Windows reserved range; fallback `9911`), bound to loopback only, rendered fullscreen or always-on-top.
- **Aesthetic (Ahmad's taste):** monochrome **black/white/gray**, **space/cosmic** void + subtle starfield, sleek instrument precision of a **Porsche 911 gauge cluster / aviation HUD**; one restrained accent glow.
- **Central reactive core** — glowing ring/orb that pulses with mic + Zero's voice; **state** label (Idle · Listening · Thinking · Speaking); live **waveform**.
- **Live "how it works" rail:** streams what Zero is doing in real time — tool calls, files touched, memories recalled, confirm-gate prompts. Watch it think and act.
- **Tech:** Canvas/WebGL (three.js) visuals, driven by the orchestrator over a local **websocket**.

### `orchestrator.py`
The always-on process. Wires wake→listen→think→speak; barge-in; per-turn memory recall/capture; pushes state to the UI websocket; supervised loop (catch+log any module error, keep running); structured logging.

### `config.toml` + `install.ps1`
Config: voice, wake sensitivity, model, persona path, tool allow/confirm/never lists, UI options. `install.ps1`: registers `StartZero` logon task (`pythonw`, `RestartCount`), single-instance, first-run model downloads.

## 6. Data flow (one turn)

1. Mic stream → `wake` detects "Zero" → chime, UI → *Listening*.
2. `stt` records → VAD endpoint → transcript (or silent re-sleep on false wake).
3. `orchestrator` asks `memory.recall(text)` → injects relevant memories + recent turns.
4. `brain` (SDK) thinks/acts; each tool call → `gate.canUseTool` → auto-allow OR Zero asks aloud + waits for yes/no. UI streams tools/memory live.
5. Brain streams reply → `voice` speaks sentence-by-sentence (British). UI → *Speaking*; barge-in interrupts.
6. `memory` logs the turn; explicit "remember…" stored now, auto-facts at session end. → *Idle*.

## 7. Resilience

Always-on, so it must never die: mic loss → backoff + recover; brain/STT/TTS error → graceful spoken fallback + log; subscription-not-authed → clear log to re-auth; confirm-gate timeout → deny; supervised loop survives any module exception; task auto-restarts the process. **Logs + db are size-capped + rotated** so Zero never fills C: (per the FiveM/disk incident).

## 8. MVP (vertical slice)

Say "Zero" → chime → speak → Whisper → Agent SDK answers (tools + memory recall) → British voice reply; confirm-gate stops one destructive action; "Zero, remember that…" persists and recalls next session; HUD shows state + live tool feed; runs as the `StartZero` logon task. Everything after (auto-capture tuning, barge-in polish, richer HUD) is iteration.

## 9. Testing

- `gate` — thorough unit table (allow / confirm / never), safety-critical.
- `brain`, `memory` — headless (feed text, assert tools used / right facts recalled).
- `stt`/`voice` — wav→transcript, phrase→audio.
- `wake` — recorded "Zero" clips vs noise (false-accept/reject).
- **`--text` mode** — type instead of speak; exercises brain→memory→gate with no mic/TTS for fast dev.

## 10. Open questions / future

- RVC custom voice clone (optional later).
- Telegram as a secondary remote interface (existing bot infra).
- Promoting select Zero memories into the cross-machine vault (opt-in).
