"""Fan profiles: the input to the Personalise stage."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Mode(StrEnum):
    CASUAL = "casual"
    ANALYST = "analyst"
    PLAYER_CAM = "player_cam"
    NEW_FAN = "new_fan"


SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "ar": "العربية",
    "pt": "Português",
}

FOCUS_METRICS = ("none", "pass_difficulty", "speed", "xg", "pressing", "distance")


class FanProfile(BaseModel):
    id: str = "default"
    mode: Mode = Mode.CASUAL
    language: str = "en"
    favorite_team: str | None = None
    favorite_player: str | None = None
    focus_metric: str = "none"
    spoiler_free: bool = False
    max_cues_per_minute: int = Field(6, ge=1, le=30)

    @property
    def rtl(self) -> bool:
        return self.language in {"ar", "he", "fa", "ur"}
