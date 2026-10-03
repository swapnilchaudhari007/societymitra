"""Nebius Token Factory client with tiered NVIDIA Nemotron routing.

Token Factory exposes an OpenAI-compatible API. We keep three tiers:
  - nano  : fast, cheap calls (intent triage, language detection, short summaries)
  - super : everyday drafting (notices, complaint replies, WhatsApp messages)
  - ultra : heavy reasoning (bye-law rulings, disputes, multi-step plans)

Model IDs are resolved at startup from /v1/models so the app keeps working when
Nebius renames or versions a model. Override with env vars if you want to pin.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

import httpx

BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")

# Preferred model IDs + fuzzy fallbacks used during discovery.
TIERS = {
    "nano": {
        "env": "MITRA_MODEL_NANO",
        "default": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
        "match": ["nemotron-3-nano", "nemotron-nano", "nano"],
    },
    "super": {
        "env": "MITRA_MODEL_SUPER",
        "default": "nvidia/nemotron-3-super-120b-a12b",
        "match": ["nemotron-3-super", "nemotron-super", "super"],
    },
    "ultra": {
        "env": "MITRA_MODEL_ULTRA",
        "default": "nvidia/Nemotron-3-Ultra-550b-a55b",
        "match": ["nemotron-3-ultra", "nemotron-ultra", "ultra"],
    },
}


@dataclass
class Trace:
    """One model call, shown in the UI's 'How Mitra thought' panel."""
    step: str
    tier: str
    model: str
    ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class LLMResult:
    text: str
    trace: Trace


@dataclass
class TokenFactory:
    api_key: str | None = field(default_factory=lambda: os.getenv("NEBIUS_API_KEY"))
    models: dict = field(default_factory=dict)
    timeout: float = 120.0

    def __post_init__(self):
        for tier, cfg in TIERS.items():
            self.models[tier] = os.getenv(cfg["env"]) or cfg["default"]

    @property
    def live(self) -> bool:
        return bool(self.api_key)

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def discover(self) -> dict:
        """Map each tier to a real NVIDIA model ID available on this account."""
        if not self.live:
            return self.models
        try:
            r = httpx.get(f"{BASE_URL}/models", headers=self._headers(), timeout=20)
            r.raise_for_status()
            ids = [m["id"] for m in r.json().get("data", [])]
        except Exception:
            return self.models
        nvidia = [i for i in ids if "nemotron" in i.lower()]
        for tier, cfg in TIERS.items():
            if os.getenv(cfg["env"]) or self.models[tier] in ids:
                continue
            for needle in cfg["match"]:
                hit = next((i for i in nvidia if needle in i.lower()), None)
                if hit:
                    self.models[tier] = hit
                    break
        return self.models

    def chat(self, tier: str, messages: list[dict], step: str, *,
             temperature: float = 0.3, max_tokens: int = 1200,
             json_mode: bool = False) -> LLMResult:
        model = self.models[tier]
        t0 = time.time()
        if not self.live:
            from .offline import offline_reply
            text = offline_reply(step, messages)
            return LLMResult(text, Trace(step, tier, model + " (offline)", int((time.time() - t0) * 1000)))

        body = {"model": model, "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = httpx.post(f"{BASE_URL}/chat/completions", headers=self._headers(),
                       json=body, timeout=self.timeout)
        if r.status_code >= 400 and json_mode:
            # Some models reject response_format; retry without it.
            body.pop("response_format", None)
            r = httpx.post(f"{BASE_URL}/chat/completions", headers=self._headers(),
                           json=body, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        msg = data["choices"][0]["message"]
        text = strip_reasoning(msg.get("content") or "")
        usage = data.get("usage") or {}
        return LLMResult(text, Trace(step, tier, model, int((time.time() - t0) * 1000),
                                     usage.get("prompt_tokens", 0),
                                     usage.get("completion_tokens", 0)))


def strip_reasoning(text: str) -> str:
    """Nemotron reasoning models may emit <think>...</think>; users don't need it."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return text.strip()


def parse_json(text: str, default: dict) -> dict:
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return default
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return default
