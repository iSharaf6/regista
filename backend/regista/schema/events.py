"""Synthetic match feed contract (v1).

Events carry only what a real optical-tracking + eventing feed would observe:
positions, outcomes, body part, ball speed and a pressure flag. Everything
interpretive (xG, pass difficulty, line-breaking, win probability) is computed
downstream by the Interpret stage, never baked into the feed.

Coordinates are metres on a 105 x 68 pitch. The home team attacks towards
x = 105 for the whole match (no side switch, to keep overlays stable).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0


class EventType(StrEnum):
    KICK_OFF = "kick_off"
    PASS = "pass"
    CARRY = "carry"
    DRIBBLE = "dribble"
    PRESSURE = "pressure"
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    CLEARANCE = "clearance"
    SHOT = "shot"
    GOAL = "goal"
    SAVE = "save"
    FOUL = "foul"
    CARD = "card"
    CORNER = "corner"
    FREE_KICK = "free_kick"
    THROW_IN = "throw_in"
    GOAL_KICK = "goal_kick"
    OFFSIDE = "offside"
    SUBSTITUTION = "substitution"
    POSSESSION_CHANGE = "possession_change"
    HALF_TIME = "half_time"
    SECOND_HALF = "second_half"
    FULL_TIME = "full_time"


class PlayerInfo(BaseModel):
    id: str
    name: str
    short_name: str
    number: int
    position: str
    nationality: str
    age: int
    starting: bool = True
    top_speed_kmh: float


class TeamInfo(BaseModel):
    id: str
    name: str
    short_name: str
    abbr: str
    primary: str
    secondary: str
    formation: str
    style: str
    players: list[PlayerInfo]


class MatchInfo(BaseModel):
    v: Literal[1] = 1
    match_id: str
    competition: str
    venue: str
    kickoff_utc: str
    referee: str
    weather: str
    seed: int
    home: TeamInfo
    away: TeamInfo
    pitch: tuple[float, float] = (PITCH_LENGTH, PITCH_WIDTH)
    frame_hz: int = 5
    # roster order of the 22 (+subs) entities in Frame.p
    roster: list[str] = Field(default_factory=list)


class MatchEvent(BaseModel):
    v: Literal[1] = 1
    id: str
    match_id: str
    seq: int
    t: float = Field(description="Seconds since first-half kick-off (feed clock).")
    period: int
    minute: int
    second: int
    clock: str = Field(description='Broadcast clock, e.g. "45+2\'"')
    type: EventType
    team: str | None = None
    player: str | None = None
    x: float | None = None
    y: float | None = None
    end_x: float | None = None
    end_y: float | None = None
    outcome: str | None = None
    receiver: str | None = None
    under_pressure: bool = False
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    related: list[str] = Field(default_factory=list)


class Frame(BaseModel):
    """5 Hz tracking-lite frame. p is ordered by MatchInfo.roster; None = off pitch."""

    t: float
    b: tuple[float, float, float]
    p: list[tuple[float, float] | None]
