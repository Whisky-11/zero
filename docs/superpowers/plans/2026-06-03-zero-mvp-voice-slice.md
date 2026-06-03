# Zero — MVP Voice Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A working end-to-end Zero: say the wake word → Whisper transcribes → Claude Agent SDK (on Ahmad's subscription) answers with tools + a confirm-gate + persistent memory → Kokoro British voice replies, with a live HUD showing state.

**Architecture:** One always-on Python process (`orchestrator.py`) wiring small single-purpose modules behind clean interfaces (`wake`, `stt`, `voice`, `brain`, `gate`, `memory`, `hud`). The brain is a long-running `ClaudeSDKClient` (warm session, low latency) on the Claude Code subscription; the gate is a `PreToolUse` hook; memory is SQLite exposed to the agent as MCP tools.

**Tech Stack:** Python 3.10 · `claude-agent-sdk` · `openwakeword` (ONNX) · `faster-whisper` (CUDA) · `silero-vad` · `kokoro` (British TTS) · `sounddevice` · `websockets` · `pytest`.

**Key decisions baked in:**
- **Auth/cost:** SDK uses the subscription (no `ANTHROPIC_API_KEY`). Zero asserts the key is unset at startup.
- **Wake word for MVP:** the built-in **`hey_jarvis`** model (works immediately, on-theme). A custom **"Zero"** wake model is a follow-on (Task 11, optional — needs ~1 hr synthetic training). Wake phrase is config-driven so swapping is one line.
- **Voice:** Kokoro `bm_george` (British male), 24 kHz.
- **Paths:** project at `C:\Users\moze1\zero`; home folder stays `moze1`; Zero addresses the user as **"Ahmad"**.

---

## File Structure

```
C:\Users\moze1\zero\
  zero/
    __init__.py
    config.py          # load config.toml → typed Config
    audio.py           # mic InputStream + playback (sounddevice)
    wake.py            # WakeListener: feed frames, emit wake events (openWakeWord)
    stt.py             # Recorder (silero-vad endpoint) + Transcriber (faster-whisper)
    voice.py           # Voice.speak(text) — Kokoro British, sentence streaming
    memory.py          # Store (SQLite) + remember/recall MCP tools + recent-turns
    gate.py            # classify(tool_name, tool_input) -> ALLOW/CONFIRM/DENY + PreToolUse hook
    brain.py           # Brain: ClaudeSDKClient session, Zero persona, hooks, mcp memory
    hud.py             # websocket server + push_state(); serves static HUD page
    orchestrator.py    # the loop: wake→listen→think→speak; barge-in; supervises
    __main__.py        # entrypoint: python -m zero  (and  python -m zero --text)
  ui/
    index.html         # minimal JARVIS HUD (Task 9); full WebGL is Plan 4
  prompts/
    zero.md            # persona system prompt
  tests/
    test_config.py  test_gate.py  test_memory.py  test_stt_smoke.py
    test_voice_smoke.py  test_brain_smoke.py
  config.toml
  requirements.txt
  install.ps1
  README.md
  .gitignore           # (already committed)
```

Each file has one responsibility; `orchestrator` depends only on the module interfaces.

---

## Task 0: Project skeleton, dependencies, config

**Files:**
- Create: `requirements.txt`, `config.toml`, `prompts/zero.md`, `zero/__init__.py`, `zero/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write `requirements.txt`**

```
claude-agent-sdk>=0.1.0
openwakeword>=0.6.0
faster-whisper>=1.0.0
silero-vad>=5.1
kokoro>=0.9.4
soundfile>=0.12
sounddevice>=0.4.6
websockets>=14.0
numpy>=1.26
tomli>=2.0 ; python_version < "3.11"
pytest>=8.0
```

- [ ] **Step 2: Create the venv and install (manual, one-time)**

Run (PowerShell, in `C:\Users\moze1\zero`):
```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cu121   # CUDA torch BEFORE first whisper run
```
Expected: installs succeed. **Gotchas to verify now:** (a) `espeak-ng` MSI installed + on PATH (`espeak-ng --version`) — Kokoro needs it; (b) `nvidia-cudnn-cu12` present for faster-whisper CUDA; if `ctranslate2` errors "not compiled with CUDA", `pip uninstall ctranslate2 && pip install ctranslate2`.

- [ ] **Step 3: Write `config.toml`**

```toml
[wake]
model = "hey_jarvis"      # built-in; swap to "zero" (custom .onnx path) later
threshold = 0.5

[stt]
model = "small"           # tiny|base|small|medium|large-v3
device = "cuda"
compute_type = "float16"
min_silence_ms = 600

[voice]
lang_code = "b"           # British English
voice = "bm_george"
speed = 1.0

[brain]
model = "claude-opus-4-7"
trivial_model = "claude-3-5-haiku-20241022"
user_name = "Ahmad"

[hud]
ws_port = 8765
http_port = 911           # the Porsche reference; HUD page served here

[gate]
# tool_input substrings that force a spoken confirmation
confirm_patterns = ["rm ", "del ", "rmdir", "git push", "git reset --hard", "shutdown", "Remove-Item", "format ", "DROP TABLE", "kill "]
# patterns Zero refuses outright, even if asked
never_patterns = ["rm -rf /", "rm -rf /*", ":(){", "mkfs", "format c:"]
```

- [ ] **Step 4: Write the failing test** (`tests/test_config.py`)

```python
from zero.config import load_config

def test_load_config_reads_voice_and_gate():
    cfg = load_config("config.toml")
    assert cfg.voice.voice == "bm_george"
    assert cfg.brain.user_name == "Ahmad"
    assert "rm " in cfg.gate.confirm_patterns
    assert cfg.hud.http_port == 911
```

- [ ] **Step 5: Run it, verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'zero.config'`.

- [ ] **Step 6: Implement `zero/config.py`**

```python
from __future__ import annotations
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class WakeCfg:  model: str; threshold: float
@dataclass
class SttCfg:   model: str; device: str; compute_type: str; min_silence_ms: int
@dataclass
class VoiceCfg: lang_code: str; voice: str; speed: float
@dataclass
class BrainCfg: model: str; trivial_model: str; user_name: str
@dataclass
class HudCfg:   ws_port: int; http_port: int
@dataclass
class GateCfg:  confirm_patterns: list[str]; never_patterns: list[str]

@dataclass
class Config:
    wake: WakeCfg; stt: SttCfg; voice: VoiceCfg
    brain: BrainCfg; hud: HudCfg; gate: GateCfg


def load_config(path: str = "config.toml") -> Config:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return Config(
        wake=WakeCfg(**data["wake"]),
        stt=SttCfg(**data["stt"]),
        voice=VoiceCfg(**data["voice"]),
        brain=BrainCfg(**data["brain"]),
        hud=HudCfg(**data["hud"]),
        gate=GateCfg(**data["gate"]),
    )
```
Also create empty `zero/__init__.py`.

- [ ] **Step 7: Run the test, verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 8: Write `prompts/zero.md`** (the persona)

```markdown
You are Zero — Ahmad's personal AI assistant, in the spirit of JARVIS.

Voice & manner: a calm, dry-witted, formal-but-warm British butler. Concise.
Address the user as "Ahmad". Never ramble; spoken replies should be 1-3 short
sentences unless asked for detail. A little wit is welcome; never sycophantic.

You run locally on Ahmad's Windows PC with full tools (shell, files, web) and
persistent memory. You are spoken aloud, so: no markdown, no code fences, no
emoji, no bullet lists in replies — speak in plain sentences a voice can read.

Before any destructive action (deleting, overwriting, pushing, shutting down,
killing processes) you will be asked to confirm out loud; phrase the
confirmation as a short question naming the consequence.

Use the `recall` tool when a question might depend on something Ahmad told you
before; use `remember` when he tells you something worth keeping.
```

- [ ] **Step 9: Commit**

```bash
git add requirements.txt config.toml prompts/zero.md zero/__init__.py zero/config.py tests/test_config.py
git commit -m "feat: project skeleton, deps, config loader"
```

---

## Task 1: Audio I/O (mic stream + playback)

**Files:**
- Create: `zero/audio.py`
- Test: `tests/test_stt_smoke.py` (smoke; hardware) — created later; here a pure-logic test.

- [ ] **Step 1: Write the failing test** (`tests/test_audio.py`)

```python
import numpy as np
from zero.audio import int16_to_float32

def test_int16_to_float32_scales_to_unit_range():
    x = np.array([-32768, 0, 32767], dtype=np.int16)
    y = int16_to_float32(x)
    assert y.dtype == np.float32
    assert abs(y[0] + 1.0) < 1e-3 and abs(y[1]) < 1e-6 and abs(y[2] - 1.0) < 1e-3
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/test_audio.py -v` → FAIL (no module).

- [ ] **Step 3: Implement `zero/audio.py`**

```python
from __future__ import annotations
import queue
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK = 512          # 32 ms — matches silero-vad chunk size


def int16_to_float32(x: np.ndarray) -> np.ndarray:
    return (x.astype(np.float32) / 32768.0)


class Mic:
    """Always-on 16 kHz mono input. .frames() yields int16 numpy chunks of BLOCK."""
    def __init__(self) -> None:
        self._q: queue.Queue[np.ndarray] = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, blocksize=BLOCK, channels=1,
            dtype="int16", callback=self._cb,
        )

    def _cb(self, indata, frames, time, status) -> None:
        self._q.put(indata[:, 0].copy())

    def start(self) -> None: self._stream.start()
    def stop(self) -> None: self._stream.stop()

    def frames(self):
        while True:
            yield self._q.get()


def play(audio_f32: np.ndarray, samplerate: int = 24000, block: bool = True) -> None:
    sd.play(audio_f32, samplerate=samplerate)
    if block:
        sd.wait()


def stop_playback() -> None:
    sd.stop()
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/test_audio.py -v` → PASS.

- [ ] **Step 5: Manual smoke (hardware)**

Run a 3-second capture and confirm non-silent frames:
```powershell
python -c "from zero.audio import Mic; import itertools, numpy as np; m=Mic(); m.start(); print('peak', max(int(np.abs(f).max()) for f in itertools.islice(m.frames(),50)))"
```
Expected: prints a peak > 0 (speak during it). If 0, fix the mic in Windows sound settings.

- [ ] **Step 6: Commit**

```bash
git add zero/audio.py tests/test_audio.py
git commit -m "feat: mic capture + playback (sounddevice)"
```

---

## Task 2: Wake word (openWakeWord, hey_jarvis)

**Files:**
- Create: `zero/wake.py`
- Test: `tests/test_wake.py`

- [ ] **Step 1: One-time model download (manual)**

Run: `python -c "import openwakeword; openwakeword.utils.download_models()"`
Expected: downloads bundled ONNX models incl. `hey_jarvis`.

- [ ] **Step 2: Write the failing test** (`tests/test_wake.py`)

```python
import numpy as np
from zero.wake import WakeListener

def test_silence_does_not_trigger():
    w = WakeListener(model="hey_jarvis", threshold=0.5)
    triggered = False
    for _ in range(20):
        if w.feed(np.zeros(1280, dtype=np.int16)):
            triggered = True
    assert triggered is False
```

- [ ] **Step 3: Run, verify fail** → `pytest tests/test_wake.py -v` → FAIL (no module).

- [ ] **Step 4: Implement `zero/wake.py`**

```python
from __future__ import annotations
import numpy as np
from openwakeword.model import Model


class WakeListener:
    """Feed int16 audio; returns True on the frame the wake word is detected."""
    def __init__(self, model: str = "hey_jarvis", threshold: float = 0.5) -> None:
        self._key = model
        self._threshold = threshold
        # built-in models load by default; a custom path also works via wakeword_models=[...]
        self._model = Model(inference_framework="onnx")

    def feed(self, frame_int16: np.ndarray) -> bool:
        self._model.predict(frame_int16)
        score = float(self._model.prediction_buffer[self._key][-1])
        if score >= self._threshold:
            self._model.reset()
            return True
        return False
```

- [ ] **Step 5: Run, verify pass** → PASS.

- [ ] **Step 6: Manual smoke (hardware)**

```powershell
python -c "from zero.audio import Mic; from zero.wake import WakeListener; m=Mic(); m.start(); w=WakeListener(); print('say: hey jarvis'); [print('WAKE') for f in m.frames() if w.feed(f)]"
```
Expected: prints `WAKE` when you say "hey jarvis". Ctrl-C to stop. (openWakeWord wants 1280-sample frames; the Mic yields 512 — Step 7 reconciles.)

- [ ] **Step 7: Reconcile block size** — buffer 512-sample mic frames into 1280 before `feed`. Add to `wake.py`:

```python
class FrameBuffer:
    """Accumulate small chunks into fixed-size frames."""
    def __init__(self, size: int = 1280) -> None:
        self._size = size; self._buf = np.empty(0, dtype=np.int16)
    def push(self, chunk: np.ndarray):
        self._buf = np.concatenate([self._buf, chunk])
        while len(self._buf) >= self._size:
            out, self._buf = self._buf[:self._size], self._buf[self._size:]
            yield out
```

- [ ] **Step 8: Commit**

```bash
git add zero/wake.py tests/test_wake.py
git commit -m "feat: wake-word listener (openWakeWord hey_jarvis) + frame buffer"
```

---

## Task 3: STT — endpointing (silero-vad) + transcription (faster-whisper)

**Files:**
- Create: `zero/stt.py`
- Test: `tests/test_stt.py`, `tests/test_stt_smoke.py`

- [ ] **Step 1: Write the failing test** (`tests/test_stt.py`) — pure VAD-collection logic

```python
import numpy as np
from zero.stt import Recorder

def test_recorder_collects_between_start_and_end(monkeypatch):
    r = Recorder(min_silence_ms=300)
    # stub the vad to emit start, then audio, then end
    seq = [{"start": 0}, None, None, {"end": 1}]
    monkeypatch.setattr(r, "_vad_step", lambda chunk: seq.pop(0) if seq else None)
    out = None
    for _ in range(4):
        out = r.feed(np.zeros(512, dtype=np.int16))
        if out is not None:
            break
    assert out is not None and out.dtype == np.float32
```

- [ ] **Step 2: Run, verify fail** → FAIL (no module).

- [ ] **Step 3: Implement `zero/stt.py`**

```python
from __future__ import annotations
import numpy as np
from silero_vad import load_silero_vad, VADIterator
from faster_whisper import WhisperModel
from zero.audio import int16_to_float32


class Recorder:
    """Feed 512-sample int16 chunks AFTER wake. Returns the float32 utterance on end-of-speech, else None."""
    def __init__(self, min_silence_ms: int = 600) -> None:
        self._vad = VADIterator(load_silero_vad(), threshold=0.5,
                                sampling_rate=16000, min_silence_duration_ms=min_silence_ms)
        self._collecting = False
        self._buf: list[np.ndarray] = []

    def _vad_step(self, chunk_f32: np.ndarray):
        return self._vad(chunk_f32)

    def reset(self) -> None:
        self._vad.reset_states(); self._collecting = False; self._buf = []

    def feed(self, chunk_int16: np.ndarray):
        f32 = int16_to_float32(chunk_int16)
        evt = self._vad_step(f32)
        if evt and "start" in evt:
            self._collecting = True; self._buf = []
        if self._collecting:
            self._buf.append(f32)
        if evt and "end" in evt and self._collecting:
            self._collecting = False
            return np.concatenate(self._buf).astype(np.float32) if self._buf else None
        return None


class Transcriber:
    def __init__(self, model: str, device: str, compute_type: str) -> None:
        self._model = WhisperModel(model, device=device, compute_type=compute_type)

    def transcribe(self, audio_f32: np.ndarray) -> str:
        segments, _ = self._model.transcribe(
            audio_f32, language="en", beam_size=5, condition_on_previous_text=False)
        return " ".join(s.text.strip() for s in segments).strip()
```

- [ ] **Step 4: Run, verify pass** → PASS.

- [ ] **Step 5: Smoke test transcription** (`tests/test_stt_smoke.py`, GPU; marked manual)

```python
import numpy as np, pytest
from zero.stt import Transcriber

@pytest.mark.manual
def test_transcriber_runs_on_silence():
    t = Transcriber("small", "cuda", "float16")
    out = t.transcribe(np.zeros(16000, dtype=np.float32))  # 1s silence
    assert isinstance(out, str)   # empty or near-empty, but no crash → CUDA OK
```
Run: `pytest tests/test_stt_smoke.py -v -m manual`
Expected: PASS (proves CUDA + model load). If it errors on CUDA, fix per Task 0 Step 2 gotchas.

- [ ] **Step 6: Commit**

```bash
git add zero/stt.py tests/test_stt.py tests/test_stt_smoke.py
git commit -m "feat: STT — silero-vad endpointing + faster-whisper transcription"
```

---

## Task 4: Voice (Kokoro British, sentence streaming)

**Files:**
- Create: `zero/voice.py`
- Test: `tests/test_voice.py`, `tests/test_voice_smoke.py`

- [ ] **Step 1: Write the failing test** (`tests/test_voice.py`) — sentence splitter

```python
from zero.voice import split_sentences

def test_split_sentences():
    assert split_sentences("Hello, Ahmad. All systems online! Ready?") == \
        ["Hello, Ahmad.", "All systems online!", "Ready?"]
```

- [ ] **Step 2: Run, verify fail** → FAIL.

- [ ] **Step 3: Implement `zero/voice.py`**

```python
from __future__ import annotations
import re
import numpy as np
from kokoro import KPipeline
from zero import audio

_SENT = re.compile(r".+?(?:[.!?](?:\s|$)|$)", re.S)

def split_sentences(text: str) -> list[str]:
    return [m.group().strip() for m in _SENT.finditer(text.strip()) if m.group().strip()]


class Voice:
    def __init__(self, lang_code: str = "b", voice: str = "bm_george", speed: float = 1.0) -> None:
        self._pipe = KPipeline(lang_code=lang_code)
        self._voice = voice; self._speed = speed

    def _synth(self, text: str) -> np.ndarray:
        chunks = [a for _, _, a in self._pipe(text, voice=self._voice, speed=self._speed)]
        return np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(1, np.float32)

    def speak(self, text: str) -> None:
        """Speak sentence-by-sentence so long replies start fast."""
        for sentence in split_sentences(text):
            audio.play(self._synth(sentence), samplerate=24000, block=True)
```

- [ ] **Step 4: Run, verify pass** → PASS.

- [ ] **Step 5: Smoke (hardware/espeak)** (`tests/test_voice_smoke.py`)

```python
import pytest
from zero.voice import Voice

@pytest.mark.manual
def test_voice_speaks():
    Voice().speak("Good evening, Ahmad. Zero online.")
```
Run: `pytest tests/test_voice_smoke.py -v -m manual`
Expected: you HEAR a British voice. If phonemizer/espeak error → install espeak-ng MSI (Task 0).

- [ ] **Step 6: Commit**

```bash
git add zero/voice.py tests/test_voice.py tests/test_voice_smoke.py
git commit -m "feat: Kokoro British voice with sentence streaming"
```

---

## Task 5: Memory (SQLite store + remember/recall MCP tools)

**Files:**
- Create: `zero/memory.py`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Write the failing test** (`tests/test_memory.py`)

```python
from zero.memory import Store

def test_remember_then_recall(tmp_path):
    s = Store(str(tmp_path / "z.db"))
    s.remember("Ahmad's flight is Tuesday 9am", source="explicit")
    hits = s.recall("when is my flight")
    assert any("Tuesday" in h for h in hits)

def test_log_and_recent(tmp_path):
    s = Store(str(tmp_path / "z.db"))
    s.log_turn("user", "hello"); s.log_turn("assistant", "Good evening, Ahmad.")
    recent = s.recent_turns(limit=2)
    assert recent[-1] == ("assistant", "Good evening, Ahmad.")
```

- [ ] **Step 2: Run, verify fail** → FAIL.

- [ ] **Step 3: Implement `zero/memory.py`** (MVP recall = keyword/substring + recency; semantic embedding is Plan 2)

```python
from __future__ import annotations
import sqlite3, time
from pathlib import Path


class Store:
    def __init__(self, path: str = "data/zero.db") -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(
            "CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, ts REAL, text TEXT, source TEXT);"
            "CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, ts REAL, role TEXT, text TEXT);")
        self._db.commit()

    def remember(self, text: str, source: str = "explicit") -> None:
        self._db.execute("INSERT INTO memories(ts,text,source) VALUES(?,?,?)", (time.time(), text, source))
        self._db.commit()

    def recall(self, query: str, limit: int = 5) -> list[str]:
        # MVP: score by overlap of query words; Plan 2 replaces with embeddings.
        words = [w.lower() for w in query.split() if len(w) > 2]
        rows = self._db.execute("SELECT text FROM memories ORDER BY ts DESC").fetchall()
        scored = []
        for (text,) in rows:
            lt = text.lower()
            scored.append((sum(w in lt for w in words), text))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for s, t in scored if s > 0][:limit]

    def log_turn(self, role: str, text: str) -> None:
        self._db.execute("INSERT INTO messages(ts,role,text) VALUES(?,?,?)", (time.time(), role, text))
        self._db.commit()

    def recent_turns(self, limit: int = 6) -> list[tuple[str, str]]:
        rows = self._db.execute("SELECT role,text FROM messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return list(reversed(rows))
```

- [ ] **Step 4: Run, verify pass** → PASS.

- [ ] **Step 5: Add the MCP tool server** (append to `zero/memory.py`)

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

def build_memory_mcp(store: "Store"):
    @tool("remember", "Store a durable fact Ahmad told you", {"fact": str})
    async def remember(args):
        store.remember(args["fact"], source="explicit")
        return {"content": [{"type": "text", "text": f"Noted: {args['fact']}"}]}

    @tool("recall", "Recall facts relevant to a query", {"query": str})
    async def recall(args):
        hits = store.recall(args["query"])
        return {"content": [{"type": "text", "text": "\n".join(hits) or "Nothing relevant remembered."}]}

    return create_sdk_mcp_server(name="memory", version="1.0.0", tools=[remember, recall])
```

- [ ] **Step 6: Commit**

```bash
git add zero/memory.py tests/test_memory.py
git commit -m "feat: SQLite memory store + remember/recall MCP tools"
```

---

## Task 6: Safety gate (classifier + PreToolUse hook)

**Files:**
- Create: `zero/gate.py`
- Test: `tests/test_gate.py`

- [ ] **Step 1: Write the failing test** (`tests/test_gate.py`) — the safety-critical table

```python
from zero.gate import classify, ALLOW, CONFIRM, DENY

CONFIRM_P = ["rm ", "git push", "Remove-Item", "shutdown"]
NEVER_P = ["rm -rf /", ":(){", "mkfs"]

def c(tool, inp): return classify(tool, inp, CONFIRM_P, NEVER_P)

def test_reads_are_allowed():
    assert c("Read", {"file_path": "x"}) == ALLOW
    assert c("Bash", {"command": "ls -la"}) == ALLOW
    assert c("Bash", {"command": "git status"}) == ALLOW

def test_destructive_needs_confirm():
    assert c("Bash", {"command": "rm old.log"}) == CONFIRM
    assert c("Bash", {"command": "git push origin main"}) == CONFIRM
    assert c("Write", {"file_path": "C:/x"}) == CONFIRM   # any Write mutates

def test_catastrophic_is_denied():
    assert c("Bash", {"command": "rm -rf /"}) == DENY

def test_unknown_mutating_defaults_confirm():
    assert c("SomeNewTool", {"x": 1}) == CONFIRM
```

- [ ] **Step 2: Run, verify fail** → FAIL.

- [ ] **Step 3: Implement `zero/gate.py`**

```python
from __future__ import annotations

ALLOW, CONFIRM, DENY = "allow", "confirm", "deny"

# tools that never mutate → always allow
_SAFE_TOOLS = {"Read", "Glob", "Grep", "WebFetch", "WebSearch",
               "mcp__memory__recall"}
# tools that always mutate → at least confirm
_MUTATING_TOOLS = {"Write", "Edit"}


def _text(tool_input: dict) -> str:
    return " ".join(str(v) for v in tool_input.values())


def classify(tool_name: str, tool_input: dict,
             confirm_patterns: list[str], never_patterns: list[str]) -> str:
    blob = _text(tool_input)
    if any(p in blob for p in never_patterns):
        return DENY
    if tool_name in _SAFE_TOOLS:
        return ALLOW
    if tool_name == "Bash":
        if any(p in blob for p in confirm_patterns):
            return CONFIRM
        return ALLOW            # non-mutating shell (ls, cat, git status, etc.)
    if tool_name in _MUTATING_TOOLS:
        return CONFIRM
    if tool_name.startswith("mcp__memory__remember"):
        return ALLOW            # storing a fact is harmless
    return CONFIRM              # unknown/other → conservative
```

- [ ] **Step 4: Run, verify pass** → PASS.

- [ ] **Step 5: Add the PreToolUse hook factory** (append to `zero/gate.py`)

```python
def build_pretooluse_hook(cfg, confirm_aloud):
    """confirm_aloud(question:str)->bool : speak the question, listen for yes/no."""
    async def hook(input_data, tool_use_id, context):
        if input_data.get("hook_event_name") != "PreToolUse":
            return {}
        decision = classify(input_data["tool_name"], input_data.get("tool_input", {}),
                            cfg.gate.confirm_patterns, cfg.gate.never_patterns)
        if decision == ALLOW:
            return {}
        if decision == DENY:
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                    "permissionDecision": "deny", "permissionDecisionReason": "Refused: catastrophic action."}}
        # CONFIRM → ask Ahmad out loud
        summary = _text(input_data.get("tool_input", {}))[:160]
        ok = confirm_aloud(f"This will run: {summary}. Shall I proceed, Ahmad?")
        if ok:
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny", "permissionDecisionReason": "Ahmad declined."}}
    return hook
```

- [ ] **Step 6: Commit**

```bash
git add zero/gate.py tests/test_gate.py
git commit -m "feat: safety gate — classifier + spoken-confirm PreToolUse hook"
```

---

## Task 7: Brain (ClaudeSDKClient session on the subscription)

**Files:**
- Create: `zero/brain.py`
- Test: `tests/test_brain_smoke.py`

- [ ] **Step 1: Write the failing smoke test** (`tests/test_brain_smoke.py`)

```python
import asyncio, pytest
from zero.config import load_config
from zero.memory import Store
from zero.brain import Brain

@pytest.mark.manual
def test_brain_answers_on_subscription(tmp_path):
    cfg = load_config("config.toml")
    brain = Brain(cfg, Store(str(tmp_path / "z.db")), confirm_aloud=lambda q: True)
    reply = asyncio.run(brain.ask_text("Say exactly: systems online"))
    assert "systems online" in reply.lower()
```

- [ ] **Step 2: Run, verify fail** → FAIL (no module). (Also proves the manual marker runs.)

- [ ] **Step 3: Implement `zero/brain.py`**

```python
from __future__ import annotations
import os
from pathlib import Path
from claude_agent_sdk import (ClaudeSDKClient, ClaudeAgentOptions,
                              AssistantMessage, TextBlock, HookMatcher)
from zero.memory import build_memory_mcp
from zero.gate import build_pretooluse_hook


class SubscriptionKeyError(RuntimeError):
    pass


class Brain:
    def __init__(self, cfg, store, confirm_aloud, on_text=None) -> None:
        if os.environ.get("ANTHROPIC_API_KEY"):
            raise SubscriptionKeyError(
                "ANTHROPIC_API_KEY is set — Zero would bill per token. Unset it to use the subscription.")
        self._cfg = cfg
        self._on_text = on_text          # callback(sentence) for streaming TTS
        persona = Path("prompts/zero.md").read_text(encoding="utf-8")
        memory_mcp = build_memory_mcp(store)
        hook = build_pretooluse_hook(cfg, confirm_aloud)
        self._options = ClaudeAgentOptions(
            system_prompt=persona,
            model=cfg.brain.model,
            mcp_servers={"memory": memory_mcp},
            allowed_tools=["Read", "Glob", "Grep", "Bash", "Write", "Edit",
                           "WebSearch", "WebFetch",
                           "mcp__memory__remember", "mcp__memory__recall"],
            permission_mode="default",
            hooks={"PreToolUse": [HookMatcher(matcher="*", hooks=[hook])]},
        )
        self._client = ClaudeSDKClient(options=self._options)
        self._open = False

    async def _ensure(self):
        if not self._open:
            await self._client.__aenter__(); self._open = True

    async def ask_text(self, prompt: str) -> str:
        """Send a turn; return the full reply (and stream sentences via on_text)."""
        await self._ensure()
        await self._client.query(prompt)
        full = []
        async for message in self._client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        full.append(block.text)
                        if self._on_text:
                            self._on_text(block.text)
        return "".join(full).strip()

    async def aclose(self):
        if self._open:
            await self._client.__aexit__(None, None, None); self._open = False
```

- [ ] **Step 4: Run the smoke test, verify it passes**

Run: `pytest tests/test_brain_smoke.py -v -m manual`
Expected: PASS — proves the SDK answers **on the subscription** (no API key). If it raises `SubscriptionKeyError`, `Remove-Item env:ANTHROPIC_API_KEY` and retry. If it can't auth, run `claude` once to confirm login.

- [ ] **Step 5: Commit**

```bash
git add zero/brain.py tests/test_brain_smoke.py
git commit -m "feat: Brain — ClaudeSDKClient on subscription, persona + memory + gate"
```

---

## Task 8: HUD websocket server

**Files:**
- Create: `zero/hud.py`, `ui/index.html`
- Test: `tests/test_hud.py`

- [ ] **Step 1: Write the failing test** (`tests/test_hud.py`)

```python
from zero.hud import Hud

def test_push_state_is_safe_with_no_clients():
    hud = Hud(ws_port=0, http_port=0)
    hud.push_state({"status": "idle"})   # must not raise when nobody connected
```

- [ ] **Step 2: Run, verify fail** → FAIL.

- [ ] **Step 3: Implement `zero/hud.py`**

```python
from __future__ import annotations
import asyncio, json, threading
from websockets.asyncio.server import broadcast, serve

class Hud:
    def __init__(self, ws_port: int = 8765, http_port: int = 911) -> None:
        self._ws_port = ws_port; self._clients = set(); self._loop = None

    async def _handler(self, ws):
        self._clients.add(ws)
        try:
            await ws.send(json.dumps({"status": "connected"}))
            async for _ in ws:
                pass
        finally:
            self._clients.discard(ws)

    async def _serve(self):
        async with serve(self._handler, "localhost", self._ws_port):
            await asyncio.Future()

    def start(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=lambda: (asyncio.set_event_loop(self._loop),
                                         self._loop.run_until_complete(self._serve())),
                         daemon=True).start()

    def push_state(self, state: dict) -> None:
        if self._loop and self._clients:
            msg = json.dumps(state)
            self._loop.call_soon_threadsafe(lambda: broadcast(self._clients, msg))
```

- [ ] **Step 4: Run, verify pass** → PASS.

- [ ] **Step 5: Minimal HUD page** (`ui/index.html`) — monochrome placeholder; full WebGL is Plan 4

```html
<!doctype html><meta charset=utf-8><title>ZERO</title>
<style>
 body{margin:0;background:#000;color:#e8e8e8;font:14px/1.5 'Segoe UI',sans-serif;
      height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;letter-spacing:.05em}
 #core{width:160px;height:160px;border-radius:50%;border:1px solid #555;
       box-shadow:0 0 40px #fff2,inset 0 0 30px #fff1;transition:.3s;margin-bottom:24px}
 .listening #core{box-shadow:0 0 70px #fff5,inset 0 0 40px #fff3;border-color:#bbb}
 .thinking #core{animation:pulse 1.2s infinite}
 @keyframes pulse{50%{box-shadow:0 0 90px #fff7}}
 #status{text-transform:uppercase;color:#888}#rail{margin-top:18px;color:#666;font-size:12px;max-width:60ch}
</style>
<div id=wrap><div id=core></div><div id=status>idle</div><div id=rail></div></div>
<script>
 const ws=new WebSocket("ws://localhost:8765");
 ws.onmessage=e=>{const s=JSON.parse(e.data);
   document.getElementById('wrap').className=s.status||'';
   document.getElementById('status').textContent=s.status||'idle';
   if(s.activity)document.getElementById('rail').textContent=s.activity;};
</script>
```

- [ ] **Step 6: Commit**

```bash
git add zero/hud.py ui/index.html tests/test_hud.py
git commit -m "feat: HUD websocket server + minimal monochrome page"
```

---

## Task 9: Orchestrator (wire the loop) + entrypoint

**Files:**
- Create: `zero/orchestrator.py`, `zero/__main__.py`
- Test: manual end-to-end

- [ ] **Step 1: Implement `zero/orchestrator.py`**

```python
from __future__ import annotations
import asyncio, threading, queue, numpy as np
from zero.config import load_config
from zero.audio import Mic
from zero.wake import WakeListener, FrameBuffer
from zero.stt import Recorder, Transcriber
from zero.voice import Voice
from zero.memory import Store
from zero.brain import Brain
from zero.hud import Hud


class Orchestrator:
    def __init__(self) -> None:
        self.cfg = load_config("config.toml")
        self.hud = Hud(self.cfg.hud.ws_port, self.cfg.hud.http_port); self.hud.start()
        self.mic = Mic()
        self.wake = WakeListener(self.cfg.wake.model, self.cfg.wake.threshold)
        self.fb = FrameBuffer(1280)
        self.rec = Recorder(self.cfg.stt.min_silence_ms)
        self.stt = Transcriber(self.cfg.stt.model, self.cfg.stt.device, self.cfg.stt.compute_type)
        self.voice = Voice(self.cfg.voice.lang_code, self.cfg.voice.voice, self.cfg.voice.speed)
        self.store = Store()
        self._answer_q: queue.Queue[str] = queue.Queue()
        self.brain = Brain(self.cfg, self.store,
                           confirm_aloud=self._confirm_aloud,
                           on_text=lambda t: self.voice.speak(t))

    def _state(self, status, activity=""):
        self.hud.push_state({"status": status, "activity": activity})

    def _confirm_aloud(self, question: str) -> bool:
        self._state("speaking", question); self.voice.speak(question)
        text = self._listen_once().lower()
        return any(w in text for w in ("yes", "do it", "proceed", "go ahead", "confirm"))

    def _listen_once(self) -> str:
        self.rec.reset()
        for chunk in self.mic.frames():
            utter = self.rec.feed(chunk)
            if utter is not None:
                return self.stt.transcribe(utter)
        return ""

    def run(self) -> None:
        self.mic.start(); self._state("idle")
        for chunk in self.mic.frames():
            for frame in self.fb.push(chunk):
                if self.wake.feed(frame):
                    self._handle_turn()
                    self._state("idle")

    def _handle_turn(self) -> None:
        self._state("listening")
        text = self._listen_once()
        if not text:
            self._state("idle"); return
        self.store.log_turn("user", text)
        self._state("thinking", text)
        try:
            reply = asyncio.run(self.brain.ask_text(text))
        except Exception as e:
            self.voice.speak("Apologies, Ahmad, I hit an error."); self._state("idle"); return
        self.store.log_turn("assistant", reply)
```

(Note: `on_text` already streams each block to TTS; `ask_text`'s return is logged. If double-speak occurs, speak only via `on_text` and skip a final speak — verified in Step 3.)

- [ ] **Step 2: Implement `zero/__main__.py`**

```python
import sys
from zero.orchestrator import Orchestrator

def main():
    orch = Orchestrator()
    if "--text" in sys.argv:        # dev mode: type instead of speak
        import asyncio
        while True:
            t = input("you> ").strip()
            if t in ("exit", "quit"): break
            print("zero>", asyncio.run(orch.brain.ask_text(t)))
    else:
        orch.run()

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Manual end-to-end (the MVP gate)**

Run (no API key in env): `python -m zero`
- Open `http://localhost:911` won't serve yet (Task 10 adds the static server) — for now open `ui/index.html` directly in a browser to see the HUD react.
- Say "hey jarvis" → core brightens (listening) → speak "what time is it" → Zero replies in British voice; HUD shows thinking→speaking.
- Say "hey jarvis" → "delete the file test.txt" (create one first) → Zero asks to confirm; say "yes" → it proceeds; say "no" → it declines.
- Say "hey jarvis" → "remember that my favourite car is the Porsche 911" → later, new turn → "what's my favourite car" → recalls it.
Expected: all four behaviours work. Fix double-speak if heard (Step 1 note).

- [ ] **Step 4: Commit**

```bash
git add zero/orchestrator.py zero/__main__.py
git commit -m "feat: orchestrator loop + entrypoint (voice + --text dev mode)"
```

---

## Task 10: Static HUD serving + autostart (install.ps1)

**Files:**
- Modify: `zero/hud.py` (serve `ui/` over http on port 911)
- Create: `install.ps1`, `README.md`

- [ ] **Step 1: Serve the HUD page on port 911** — add to `zero/hud.py` `start()`: a stdlib `http.server` thread rooted at `ui/`, bound `127.0.0.1:http_port`. (ThreadingHTTPServer + SimpleHTTPRequestHandler with `directory="ui"`.)

```python
import functools, http.server, socketserver
def _serve_http(self, port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory="ui")
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
```
Call `self._serve_http(http_port)` in `start()`. Now `http://localhost:911` shows the HUD.

- [ ] **Step 2: Write `install.ps1`** — register the logon task (mirrors `StartWSLDashboard`)

```powershell
$py  = "C:\Users\moze1\zero\.venv\Scripts\pythonw.exe"
$dir = "C:\Users\moze1\zero"
$a = New-ScheduledTaskAction -Execute $py -Argument "-m zero" -WorkingDirectory $dir
$t = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
       -StartWhenAvailable -Hidden -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
       -ExecutionTimeLimit ([TimeSpan]::Zero)
$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "StartZero" -Action $a -Trigger $t -Settings $s -Principal $p -Force
Write-Host "StartZero registered. Ensure ANTHROPIC_API_KEY is NOT set so Zero uses the subscription."
```

- [ ] **Step 3: Write `README.md`** — quickstart: venv, espeak-ng, `python -m zero`, `python -m zero --text`, `install.ps1`, the `ANTHROPIC_API_KEY`-must-be-unset note, HUD at `localhost:911`, logs/db locations.

- [ ] **Step 4: Manual verify autostart**

Run: `powershell -File install.ps1` then `Start-ScheduledTask StartZero`; confirm Zero is listening (say "hey jarvis") and `http://localhost:911` shows the HUD.

- [ ] **Step 5: Commit**

```bash
git add zero/hud.py install.ps1 README.md
git commit -m "feat: serve HUD on :911 + StartZero logon task"
```

---

## Task 11 (optional, follow-on): custom "Zero" wake word

Not required for the MVP. openWakeWord has no built-in "Zero" model; train one (~1 hr, 100% synthetic TTS, no recording) via the official Colab notebook → `zero.onnx`. Drop it in `zero/models/zero.onnx`, set `config.toml [wake] model = "zero"`, and load via `Model(wakeword_models=["zero/models/zero.onnx"], inference_framework="onnx")`. Flag to Ahmad if he wants the MVP itself to wake on "Zero" rather than "hey jarvis".

---

## Self-Review

**Spec coverage:** wake ✓(T2) · STT ✓(T3) · brain/Agent SDK on subscription ✓(T7) · confirm-gate + never-list ✓(T6) · Kokoro British ✓(T4) · memory (knows-you profile deferred to Plan 2; remember/recall ✓ T5) · HUD ✓(T8/T10, full WebGL=Plan 4) · resilience (per-turn try/except ✓ T9; full supervision polished in Plan 3) · `--text` dev mode ✓(T9) · autostart ✓(T10) · port 911 ✓(T10) · addresses "Ahmad" ✓(prompt T0). **Deferred-by-design (own plans):** semantic recall + auto-capture + vault profile (Plan 2); barge-in + full supervision + audit log (Plan 3); WebGL HUD (Plan 4); custom "Zero" wake (T11).

**Placeholder scan:** none — every step has real code/commands.

**Type consistency:** `Brain.ask_text`, `Store.remember/recall/log_turn/recent_turns`, `classify(...)->ALLOW/CONFIRM/DENY`, `Hud.push_state`, `Mic.frames`, `Recorder.feed`, `Voice.speak`, `WakeListener.feed`/`FrameBuffer.push` are used consistently across tasks.

**Known watch-items for the implementer:** (1) double-speak between `on_text` streaming and the logged return — resolve in T9 Step 3 by speaking only via `on_text`. (2) `ask_text` uses `asyncio.run` per turn but `Brain` holds a persistent client — if the event-loop-per-turn conflicts with the warm client, switch the orchestrator to a single long-lived asyncio loop (note in T9). (3) faster-whisper CUDA/cuDNN versions (T0).
