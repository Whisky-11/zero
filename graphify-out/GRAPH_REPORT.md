# Graph Report - zero  (2026-07-20)

## Corpus Check
- 36 files · ~15,964 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 320 nodes · 389 edges · 22 communities (21 shown, 1 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 46 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c4005fee`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 19|Community 19]]

## God Nodes (most connected - your core abstractions)
1. `Orchestrator` - 19 edges
2. `Zero — MVP Voice Slice Implementation Plan` - 15 edges
3. `Store` - 13 edges
4. `load_config()` - 12 edges
5. `Brain` - 11 edges
6. `Zero — Voice-First JARVIS Assistant · Design Spec` - 11 edges
7. `Mic` - 10 edges
8. `5. Components` - 10 edges
9. `HudApiHandler` - 9 edges
10. `Hud` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Server` --uses--> `HudApiHandler`  [INFERRED]
  serve-hud.py → zero/hud_api.py
- `test_voice_speaks()` --calls--> `Voice`  [INFERRED]
  tests/test_voice_smoke.py → zero/voice.py
- `test_build_user_profile_contains_ahmad()` --calls--> `build_user_profile()`  [INFERRED]
  tests/test_profile.py → zero/profile.py
- `test_brain_answers_on_subscription()` --calls--> `load_config()`  [INFERRED]
  tests/test_brain_smoke.py → zero/config.py
- `test_brain_answers_on_subscription()` --calls--> `Brain`  [INFERRED]
  tests/test_brain_smoke.py → zero/brain.py

## Communities (22 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (48): code:block1 (C:\Users\moze1\zero\), code:python (from __future__ import annotations), code:powershell (python -c "from zero.audio import Mic; import itertools, num), code:bash (git add zero/audio.py tests/test_audio.py), code:python (import numpy as np), code:python (from __future__ import annotations), code:powershell (python -c "from zero.audio import Mic; from zero.wake import), code:python (class FrameBuffer:) (+40 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (12): test_transcriber_runs_on_silence(), test_recorder_collects_between_start_and_end(), main(), Orchestrator, One wake opens a conversation: keep listening for follow-ups (no wake         wo, Capture one utterance. Flushes stale audio first so it hears *fresh*         spe, Watch the mic for the wake word while Zero is busy (thinking/speaking)., Feed 512-sample int16 chunks AFTER wake. Returns the float32 utterance on end-of (+4 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (14): test_two_turns_same_session(), test_brain_answers_on_subscription(), Prove recall works by meaning, not keywords.      Stores two facts with zero wor, test_log_and_recent(), test_remember_then_recall(), test_semantic_recall_no_word_overlap(), build_memory_mcp(), _cosine() (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (24): ANTHROPIC_API_KEY — must be unset, Autostart at logon, code:powershell (# From C:\Users\moze1\zero), code:bash (brew install python@3.10 espeak-ng portaudio), code:powershell (# Confirm ANTHROPIC_API_KEY is NOT set), code:powershell (.\.venv\Scripts\python.exe -m zero --text), code:powershell (powershell -File C:\Users\moze1\zero\install.ps1), code:powershell (Start-ScheduledTask StartZero) (+16 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (8): SimpleHTTPRequestHandler, HudApiHandler, _list_files(), hud_api.py — read-only HTTP handler for the Zero HUD.  Serves the static HUD fro, # NOTE: deliberately NO Access-Control-Allow-Origin. The HUD page is served, _read_file(), Hud, Server

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (21): 10. Open questions / future, 1. Goal, 2. Requirements (decided), 3. Non-goals / dropped scope, 4. Architecture, 5. Components, 6. Data flow (one turn), 7. Resilience (+13 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (16): Tests for zero.profile.build_user_profile()., Profile should be non-trivial but not bloated (≤ 400 words)., build_user_profile() must return '' rather than raising when vault absent., test_build_user_profile_contains_ahmad(), test_build_user_profile_is_reasonably_sized(), test_build_user_profile_missing_vault(), build_user_profile(), _find_memory_dir() (+8 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (10): RuntimeError, Brain, Schedule async teardown on the dedicated loop (fire-and-forget is fine)., Three tiers, cheapest that fits: Opus when the request needs depth         (esca, Coroutine that runs on self._loop — ensure client, route model, query, collect t, Synchronous public API — schedules _ask on the dedicated loop and waits., Abort the in-flight turn (barge-in) — ends receive_response so ask() returns., SubscriptionKeyError (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (9): test_int16_to_float32_scales_to_unit_range(), int16_to_float32(), Mic, play(), play_interruptible(), Always-on 16 kHz mono input. .frames() yields int16 numpy chunks of BLOCK., Drop buffered audio captured while we weren't actively listening         (the co, Play audio but abort early if stop_event is set (barge-in).      Polls the event (+1 more)

### Community 9 - "Community 9"
Cohesion: 0.18
Nodes (6): test_voice_speaks(), test_split_sentences(), Speak sentence-by-sentence so long replies start fast. Abortable mid-way, Interrupt any in-progress speech immediately (barge-in)., split_sentences(), Voice

### Community 10 - "Community 10"
Cohesion: 0.26
Nodes (12): inbox_spoken_text(), _main(), _mark_spoken(), os_bridge — Zero's window into the Force AI OS.  The OS (force-ai-foundation) wr, A spoken-ready string for the inbox (or a calm all-clear)., A one/two-sentence spoken summary of subsystem health., Return the summaries of unspoken inbox items. If drain, mark them spoken., Rewrite zero-inbox.ndjson with every item marked spoken (atomic-ish). (+4 more)

### Community 11 - "Community 11"
Cohesion: 0.31
Nodes (9): test_load_config_reads_voice_and_gate(), BrainCfg, Config, GateCfg, HudCfg, load_config(), SttCfg, VoiceCfg (+1 more)

### Community 12 - "Community 12"
Cohesion: 0.31
Nodes (7): _inbox(), _status(), test_inbox_drain_marks_spoken(), test_inbox_returns_unspoken_only(), test_inbox_spoken_text_all_clear(), test_status_all_green(), test_status_flags_failing()

### Community 13 - "Community 13"
Cohesion: 0.36
Nodes (7): c(), test_catastrophic_is_denied(), test_destructive_needs_confirm(), test_reads_are_allowed(), test_unknown_mutating_defaults_confirm(), classify(), _text()

### Community 14 - "Community 14"
Cohesion: 0.28
Nodes (5): test_custom_onnx_model_loads_and_keys(), test_silence_does_not_trigger(), Clear the rolling buffer (e.g. before a fresh barge-in watch so audio         fr, Feed int16 audio; returns True on the frame the wake word is detected.      `mod, WakeListener

### Community 15 - "Community 15"
Cohesion: 0.25
Nodes (8): code:block2 (claude-agent-sdk>=0.1.0), code:powershell (py -3.10 -m venv .venv), code:toml ([wake]), code:python (from zero.config import load_config), code:python (from __future__ import annotations), code:markdown (You are Zero — Ahmad's personal AI assistant, in the spirit ), code:bash (git add requirements.txt config.toml prompts/zero.md zero/__), Task 0: Project skeleton, dependencies, config

### Community 16 - "Community 16"
Cohesion: 0.29
Nodes (6): Current state, Done, Goal, Handoff — zero, In progress, Left to do

### Community 17 - "Community 17"
Cohesion: 0.4
Nodes (5): code:python (from zero.gate import classify, ALLOW, CONFIRM, DENY), code:python (from __future__ import annotations), code:python (def build_pretooluse_hook(cfg, confirm_aloud):), code:bash (git add zero/gate.py tests/test_gate.py), Task 6: Safety gate (classifier + PreToolUse hook)

## Knowledge Gaps
- **123 isolated node(s):** `Tests for zero.profile.build_user_profile().`, `Profile should be non-trivial but not bloated (≤ 400 words).`, `build_user_profile() must return '' rather than raising when vault absent.`, `Prove recall works by meaning, not keywords.      Stores two facts with zero wor`, `Thin wrapper around sentence-transformers; loaded on first use.` (+118 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Orchestrator` connect `Community 1` to `Community 2`, `Community 4`, `Community 7`, `Community 8`, `Community 9`, `Community 14`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Why does `Brain` connect `Community 7` to `Community 1`, `Community 2`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Why does `Hud` connect `Community 4` to `Community 1`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `Orchestrator` (e.g. with `Mic` and `WakeListener`) actually correct?**
  _`Orchestrator` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Store` (e.g. with `Orchestrator` and `test_brain_answers_on_subscription()`) actually correct?**
  _`Store` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `load_config()` (e.g. with `test_brain_answers_on_subscription()` and `test_load_config_reads_voice_and_gate()`) actually correct?**
  _`load_config()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Brain` (e.g. with `Orchestrator` and `test_brain_answers_on_subscription()`) actually correct?**
  _`Brain` has 4 INFERRED edges - model-reasoned connections that need verification._