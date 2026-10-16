"""Agent telemetry, circuit breaking and fault injection.

Every agent step emits a span (who, how long, which model, outcome). The
Control Room renders these live; the same numbers back the latency and
reliability claims in the README. When OpenTelemetry is configured, spans
are mirrored to it as well (see runtime/observability.py).
"""

from __future__ import annotations

import time
import uuid
from collections import Counter, defaultdict, deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from statistics import median
from typing import Any


@dataclass
class Span:
    agent: str
    status: str  # ok | error | timeout | fallback | rejected | skipped | retry
    ms: float
    model: str = "deterministic"
    job: str = ""
    moment_id: str | None = None
    attempt: int = 1
    detail: str = ""
    t_match: float = 0.0
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    wall: float = field(default_factory=time.time)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ms"] = round(self.ms, 1)
        return d


class CircuitBreaker:
    """Opens after N consecutive model failures; half-opens after a cooldown to probe recovery."""

    def __init__(self, threshold: int = 3, cooldown_s: float = 45.0):
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self.failures = 0
        self.state = "closed"
        self.opened_at = 0.0
        self.trips = 0

    def allow(self) -> bool:
        if self.state == "open" and time.monotonic() - self.opened_at >= self.cooldown_s:
            self.state = "half_open"
        return self.state != "open"

    def success(self) -> None:
        self.failures = 0
        self.state = "closed"

    def failure(self) -> None:
        self.failures += 1
        if self.state == "half_open" or self.failures >= self.threshold:
            if self.state != "open":
                self.trips += 1
            self.state = "open"
            self.opened_at = time.monotonic()

    def as_dict(self) -> dict[str, Any]:
        remaining = max(0.0, self.cooldown_s - (time.monotonic() - self.opened_at)) if self.state == "open" else 0.0
        return {"state": self.state, "consecutive_failures": self.failures, "trips": self.trips,
                "reopens_in_s": round(remaining, 1)}


class Telemetry:
    def __init__(self) -> None:
        self.spans: deque[Span] = deque(maxlen=600)
        self.counters: Counter[str] = Counter()
        self.latency: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=200))
        self.listeners: list[Callable[[Span], None]] = []
        self.chaos_fail_rate = 0.0
        self.chaos_latency_ms = 0.0

    def record(self, span: Span) -> Span:
        self.spans.append(span)
        self.counters[f"{span.agent}.{span.status}"] += 1
        self.counters[f"status.{span.status}"] += 1
        if span.status in {"ok", "fallback", "rejected"}:
            self.latency[span.agent].append(span.ms)
        for fn in list(self.listeners):
            try:
                fn(span)
            except Exception:  # noqa: BLE001 - a broken listener must never break the pipeline
                pass
        return span

    def summary(self) -> dict[str, Any]:
        agents = {}
        for name, lat in self.latency.items():
            vals = sorted(lat)
            agents[name] = {
                "calls": sum(v for k, v in self.counters.items() if k.startswith(f"{name}.")),
                "p50_ms": round(median(vals), 1) if vals else None,
                "p95_ms": round(vals[int(0.95 * (len(vals) - 1))], 1) if vals else None,
                "errors": self.counters.get(f"{name}.error", 0) + self.counters.get(f"{name}.timeout", 0),
                "fallbacks": self.counters.get(f"{name}.fallback", 0),
                "rejections": self.counters.get(f"{name}.rejected", 0),
            }
        return {
            "agents": agents,
            "totals": {k.split(".", 1)[1]: v for k, v in self.counters.items() if k.startswith("status.")},
            "chaos": {"fail_rate": self.chaos_fail_rate, "latency_ms": self.chaos_latency_ms},
        }
