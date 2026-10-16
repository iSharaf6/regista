"""Chat clients for the agent graph.

`make_chat_client` returns a Microsoft Agent Framework chat client for the
configured provider. The offline client implements the same interface by
dispatching structured task payloads to the deterministic engine, so the
agents, workflow, verifier loop and telemetry are identical with or without
a cloud model.
"""

from __future__ import annotations

import json
from typing import Any

from agent_framework import BaseChatClient, ChatResponse, Content, Message

from .config import LLMConfig
from .insight import deterministic_insight
from .templates import PERSONAS, Names, narrate


def parse_json(text: str) -> Any:
    """Tolerant JSON extraction from model output (handles ```json fences and chatter)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):] if "{" in t else t
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(t[start:end + 1])


class OfflineChatClient(BaseChatClient):
    """Deterministic 'model' that serves Regista task payloads with no network."""

    OTEL_PROVIDER_NAME = "regista.offline"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    async def _respond(self, messages: list[Message]) -> ChatResponse:
        payload = {}
        for msg in reversed(messages):
            if msg.role == "user" and msg.text:
                try:
                    payload = parse_json(msg.text)
                except ValueError:
                    payload = {"task": "echo", "text": msg.text}
                break
        out = self.run_task(payload)
        return ChatResponse(messages=[Message("assistant", [Content.from_text(json.dumps(out, ensure_ascii=False))])],
                            model="regista-offline")

    @staticmethod
    def run_task(payload: dict[str, Any]) -> Any:
        task = payload.get("task")
        names = Names(payload.get("names", {}).get("players", {}), payload.get("names", {}).get("teams", {}))
        if task == "analyze":
            return deterministic_insight(payload["moment"], names)
        if task in {"narrate", "localize"}:
            m = payload["moment"]
            lang = payload.get("language", "en")
            return {p: narrate(m, names, lang, p, payload["home"], payload["away"]) for p in PERSONAS}
        if task == "recap":
            from .recap import offline_recap

            return offline_recap(payload)
        return {"text": payload.get("text", "")}

    def _inner_get_response(self, *, messages: Any, stream: bool, options: Any, **kwargs: Any) -> Any:
        if stream:
            raise NotImplementedError("offline client does not stream")
        return self._respond(list(messages))


def make_chat_client(cfg: LLMConfig) -> Any:
    if cfg.provider == "foundry":
        from agent_framework.foundry import FoundryChatClient
        from azure.identity.aio import DefaultAzureCredential

        return FoundryChatClient(project_endpoint=cfg.endpoint, model=cfg.model, credential=DefaultAzureCredential())
    if cfg.provider == "azure_openai":
        import os

        from agent_framework.openai import OpenAIChatCompletionClient

        key = os.getenv("AZURE_OPENAI_API_KEY")
        if key:
            return OpenAIChatCompletionClient(model=cfg.model, azure_endpoint=cfg.endpoint, api_key=key,
                                              api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"))
        from azure.identity.aio import DefaultAzureCredential

        return OpenAIChatCompletionClient(model=cfg.model, azure_endpoint=cfg.endpoint, credential=DefaultAzureCredential(),
                                          api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"))
    if cfg.provider == "openai":
        import os

        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(model=cfg.model, api_key=os.environ["OPENAI_API_KEY"], base_url=cfg.endpoint)
    return OfflineChatClient()
