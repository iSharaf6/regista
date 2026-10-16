"""Graphics Cue Protocol (GCP) v1.

A cue is a timed, machine-readable instruction for an overlay renderer. It is
anchored to the match clock (not wall time) so a rendering partner can sync it
frame-accurately to the feed, and it carries its own provenance so every
on-screen claim can be audited back to the events that justify it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class CueKind(StrEnum):
    SCORE_BUG = "score_bug"
    PLAYER_TAG = "player_tag"
    SPEED_FLASH = "speed_flash"
    PASS_CARD = "pass_card"
    SHOT_CARD = "shot_card"
    MOMENT = "moment"
    MOMENTUM = "momentum"
    STAT_COMPARE = "stat_compare"
    MILESTONE = "milestone"
    TACTICAL = "tactical"
    COMMENTARY = "commentary"
    RECAP = "recap"
    PLAYER_FOCUS = "player_focus"


class CueSlot(StrEnum):
    LOWER_THIRD = "lower_third"
    UPPER_LEFT = "upper_left"
    UPPER_RIGHT = "upper_right"
    SIDE_PANEL = "side_panel"
    FOLLOW = "follow"  # pinned to a tracked player or the ball
    TICKER = "ticker"


class Provenance(BaseModel):
    agent: str
    model: str = "deterministic"
    verified: bool = False
    fallback: bool = False
    latency_ms: float = 0.0
    attempts: int = 1


class Cue(BaseModel):
    v: Literal[1] = 1
    id: str
    match_id: str
    kind: CueKind
    slot: CueSlot
    t_in: float = Field(description="Match-clock seconds when the cue should appear.")
    t_out: float = Field(description="Match-clock seconds when the cue should clear.")
    priority: int = Field(50, ge=0, le=100)
    locale: str = "en"
    audience: str = "all"
    title: str = ""
    body: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list, description="Event ids that justify this cue.")
    follow: str | None = Field(None, description="Player id to pin to when slot == follow.")
    moment_id: str | None = None
    provenance: Provenance
