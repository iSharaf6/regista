"""Model provider selection.

REGISTA_LLM picks the provider; everything else is optional:

  offline       deterministic, no network (default) - judges can run it anywhere
  foundry       Microsoft Foundry project      FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL (Entra ID auth)
  azure_openai  Azure OpenAI deployment        AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, [AZURE_OPENAI_API_KEY]
  openai        any OpenAI-compatible API      OPENAI_API_KEY, [OPENAI_BASE_URL], [OPENAI_MODEL]
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LLMConfig:
    provider: str = "offline"
    model: str = "regista-offline"
    endpoint: str | None = None
    timeout_s: float = 20.0  # gpt-4.1-mini calls spike past 15 s at busy hours; the fast lane airs meanwhile
    max_attempts: int = 2
    breaker_threshold: int = 3
    breaker_cooldown_s: float = 45.0

    @property
    def is_offline(self) -> bool:
        return self.provider == "offline"


def load_config() -> LLMConfig:
    provider = os.getenv("REGISTA_LLM", "offline").strip().lower()
    timeout = float(os.getenv("REGISTA_LLM_TIMEOUT", "20"))
    if provider == "foundry":
        return LLMConfig("foundry", os.getenv("FOUNDRY_MODEL", "gpt-4.1-mini"), os.getenv("FOUNDRY_PROJECT_ENDPOINT"), timeout)
    if provider == "azure_openai":
        return LLMConfig("azure_openai", os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"), os.getenv("AZURE_OPENAI_ENDPOINT"), timeout)
    if provider == "openai":
        return LLMConfig("openai", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), os.getenv("OPENAI_BASE_URL"), timeout)
    return LLMConfig(timeout_s=timeout)
