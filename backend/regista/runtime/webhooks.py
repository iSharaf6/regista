"""Push key moments to Slack, Microsoft Teams or Discord.

Set REGISTA_WEBHOOK_URL to an incoming-webhook URL. Each post carries both `text` (Slack, Teams) and `content`
(Discord), so one URL format works for all three. Copy is the same verified, grounded copy that goes on air, in
REGISTA_WEBHOOK_LANG (en, es, fr, ar, pt) and REGISTA_WEBHOOK_PERSONA (casual, analyst, new_fan).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from ..agents.templates import Names, narrate
from ..intel.moments import Moment

log = logging.getLogger("regista.webhooks")
DEFAULT_KINDS = "goal,red_card,press_shift,half_time,full_time"


class Webhooks:
    def __init__(self) -> None:
        self.url = os.getenv("REGISTA_WEBHOOK_URL", "").strip()
        self.lang = os.getenv("REGISTA_WEBHOOK_LANG", "en")
        self.persona = os.getenv("REGISTA_WEBHOOK_PERSONA", "casual")
        self.kinds = {k.strip() for k in os.getenv("REGISTA_WEBHOOK_KINDS", DEFAULT_KINDS).split(",") if k.strip()}
        self.sent = 0
        self.failed = 0

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def status(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "language": self.lang, "persona": self.persona, "kinds": sorted(self.kinds),
                "sent": self.sent, "failed": self.failed}

    def wants(self, m: Moment) -> bool:
        return self.enabled and m.kind in self.kinds

    def message(self, m: Moment, names: Names, home: str, away: str, match_name: str) -> dict[str, Any]:
        copy = narrate(m.as_dict(), names, self.lang, self.persona, home, away)
        lines = [f"**{copy['caption']}** · {m.clock}", copy["line"]]
        if copy.get("explainer"):
            lines.append(f"_{copy['explainer']}_")
        lines.append(f"{match_name} · evidence {', '.join(m.evidence[:3]) or m.id} · Regista")
        text = "\n".join(lines)
        return {"text": text, "content": text[:1990], "moment": {"id": m.id, "kind": m.kind, "clock": m.clock}}

    async def post(self, payload: dict[str, Any]) -> None:
        import httpx

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.post(self.url, json=payload)
                if r.status_code < 300:
                    self.sent += 1
                    return
                log.warning("webhook returned %s", r.status_code)
            except Exception as exc:  # noqa: BLE001 - a webhook outage must never touch the broadcast
                log.warning("webhook failed: %s", exc)
            await asyncio.sleep(1.0 + attempt)
        self.failed += 1
