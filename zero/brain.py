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
