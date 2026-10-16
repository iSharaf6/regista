"""OpenTelemetry wiring.

With APPLICATIONINSIGHTS_CONNECTION_STRING set, traces and metrics from the
Agent Framework (agent runs, chat calls, tool calls, workflow supersteps)
flow to Azure Monitor / Application Insights. Without it this is a no-op.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("regista.otel")


def setup_observability() -> bool:
    conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn:
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=conn)
        os.environ.setdefault("ENABLE_INSTRUMENTATION", "true")
        try:
            from agent_framework.observability import enable_instrumentation  # type: ignore[attr-defined]

            enable_instrumentation()
        except Exception:  # noqa: BLE001 - older/newer framework versions expose this differently
            pass
        log.info("Azure Monitor OpenTelemetry enabled")
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("observability not enabled: %s", exc)
        return False
