from __future__ import annotations
import asyncio, threading, os, re
from pathlib import Path
from claude_agent_sdk import (ClaudeSDKClient, ClaudeAgentOptions,
                              AssistantMessage, TextBlock, HookMatcher)
from zero.memory import build_memory_mcp
from zero.gate import build_pretooluse_hook
from zero.profile import build_user_profile


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
        user_profile = build_user_profile()
        if user_profile:
            system_prompt = persona + "\n\n## About Ahmad (from memory)\n" + user_profile
        else:
            system_prompt = persona
        memory_mcp = build_memory_mcp(store)
        hook = build_pretooluse_hook(cfg, confirm_aloud)
        self._options = ClaudeAgentOptions(
            system_prompt=system_prompt,
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

        # Dedicated event loop running in a background daemon thread.
        # All async work (including client open/query/receive) runs on this loop,
        # so the warm client is never bound to a short-lived asyncio.run() loop.
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()

    async def _ensure(self):
        if not self._open:
            await self._client.__aenter__(); self._open = True
            self._active_model = self._cfg.brain.model

    def _pick_model(self, prompt: str) -> str:
        """Three tiers, cheapest that fits: Opus when the request needs depth
        (escalate_on), Haiku for ultra-short chit-chat/acks (trivial_on or
        <= trivial_max_words), else Sonnet (the daily driver)."""
        b = self._cfg.brain
        p = prompt.lower()
        if any(t in p for t in (getattr(b, "escalate_on", []) or [])):
            return b.opus_model
        pn = re.sub(r"[^\w\s]", "", p).strip()           # drop punctuation
        trivial = getattr(b, "trivial_on", []) or []
        maxw = getattr(b, "trivial_max_words", 2)
        if pn and (pn in trivial or (len(pn.split()) <= maxw)):
            return getattr(b, "trivial_model", b.model)
        return b.model

    async def _ask(self, prompt: str) -> str:
        """Coroutine that runs on self._loop — ensure client, route model, query, collect text."""
        await self._ensure()
        # route this turn: switch the warm client's model only when it changes
        want = self._pick_model(prompt)
        if want != getattr(self, "_active_model", None):
            try:
                res = self._client.set_model(want)
                if hasattr(res, "__await__"):
                    await res
                self._active_model = want
            except Exception:
                pass  # fall back to whatever model the client already has
        full = []
        await self._client.query(prompt)
        async for message in self._client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        full.append(block.text)
                        if self._on_text:
                            self._on_text(block.text)
        return "".join(full).strip()

    def ask(self, prompt: str) -> str:
        """Synchronous public API — schedules _ask on the dedicated loop and waits."""
        fut = asyncio.run_coroutine_threadsafe(self._ask(prompt), self._loop)
        return fut.result()

    def interrupt(self) -> None:
        """Abort the in-flight turn (barge-in) — ends receive_response so ask() returns."""
        try:
            asyncio.run_coroutine_threadsafe(self._client.interrupt(), self._loop)
        except Exception:
            pass

    async def _aclose(self):
        if self._open:
            await self._client.__aexit__(None, None, None); self._open = False

    def aclose(self):
        """Schedule async teardown on the dedicated loop (fire-and-forget is fine)."""
        asyncio.run_coroutine_threadsafe(self._aclose(), self._loop)
