from __future__ import annotations
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class WakeCfg:  model: str; threshold: float
@dataclass
class SttCfg:
    model: str; device: str; compute_type: str; min_silence_ms: int
    # Hallucination gate (2026-07-11): Whisper invents text from ambient noise /
    # music, which the follow-up loop then treats as a command. Discard segments
    # whose no_speech_prob is above / avg_logprob below these bounds.
    no_speech_max: float = 0.6
    logprob_min: float = -1.0
@dataclass
class VoiceCfg: lang_code: str; voice: str; speed: float
@dataclass
class BrainCfg:
    model: str; trivial_model: str; user_name: str
    opus_model: str = "claude-opus-4-8"
    escalate_on: list[str] = field(default_factory=list)
    trivial_on: list[str] = field(default_factory=list)
    trivial_max_words: int = 2
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
