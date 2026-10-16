"""Match-intelligence tools.

One implementation, three consumers: the Pundit agent (as Agent Framework
function tools), the MCP server (so GitHub Copilot, Foundry agents or any
MCP client can interrogate the live match) and the REST API.
"""

from __future__ import annotations

import unicodedata
from typing import Annotated, Any, Protocol

from agent_framework import tool

from ..intel.moments import Moment
from ..intel.signals import control_chaos, ppda, rhythm, shape_series
from ..intel.state import MatchState


class MatchContext(Protocol):
    state: MatchState
    moments: list[Moment]


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c)).strip()


class MatchTools:
    def __init__(self, ctx: MatchContext):
        self.ctx = ctx

    @property
    def st(self) -> MatchState:
        return self.ctx.state

    # ------------------------------------------------------------------ resolution
    def resolve_team(self, team: str | None) -> str | None:
        if not team:
            return None
        q = _norm(team)
        for tid in (self.st.home, self.st.away):
            if q in {_norm(tid), _norm(self.st.names[tid]), _norm(self.st.short[tid])} or q in _norm(self.st.names[tid]):
                return tid
        return None

    def resolve_player(self, player: str | None) -> str | None:
        if not player:
            return None
        q = _norm(player)
        best = None
        for pid, p in self.st.players.items():
            names = {_norm(pid), _norm(p.info.name), _norm(p.info.short_name)}
            if q in names:
                return pid
            if any(q in n for n in names) or any(part in q.split() for part in _norm(p.info.short_name).split()):
                best = best or pid
        return best

    def mentioned_players(self, text: str) -> list[str]:
        q = f" {_norm(text)} "
        return [pid for pid, p in self.st.players.items() if f" {_norm(p.info.short_name)} " in q
                or _norm(p.info.name) in q]

    # ------------------------------------------------------------------ tools
    def match_status(self) -> dict[str, Any]:
        s = self.st.snapshot()
        return {k: s[k] for k in ("clock", "status", "score", "win_probability", "momentum")} | {
            "home": self.st.names[self.st.home], "away": self.st.names[self.st.away]}

    def team_stats(self, team: str) -> dict[str, Any]:
        tid = self.resolve_team(team)
        if not tid:
            return {"error": f"unknown team {team!r}", "teams": [self.st.names[self.st.home], self.st.names[self.st.away]]}
        return self.st.team_view(tid)

    def player_stats(self, player: str) -> dict[str, Any]:
        pid = self.resolve_player(player)
        if not pid:
            return {"error": f"unknown player {player!r}"}
        return self.st.player_view(pid)

    def top_players(self, metric: str = "rating", n: int = 5, team: str | None = None) -> list[dict[str, Any]]:
        tid = self.resolve_team(team) if team else None
        rows = self.st.top_players(metric, max(1, min(n, 11)), tid)
        keep = ("name", "team", "position", "rating", metric, "goals", "assists", "xg", "distance_km", "top_speed_kmh")
        return [{k: r.get(k) for k in keep if k in r} for r in rows]

    def key_moments(self, kind: str = "any", limit: int = 6, min_importance: int = 40) -> list[dict[str, Any]]:
        ms = [m for m in self.ctx.moments if m.importance >= min_importance and (kind in {"any", ""} or m.kind == kind)]
        ms = sorted(ms, key=lambda m: -m.importance)[: max(1, min(limit, 20))]
        return [{"id": m.id, "clock": m.clock, "kind": m.kind, "headline": m.headline, "importance": m.importance,
                 "team": m.team} for m in sorted(ms, key=lambda m: m.t)]

    def explain_moment(self, moment_id: str) -> dict[str, Any]:
        for m in self.ctx.moments:
            if m.id == moment_id:
                return m.as_dict()
        return {"error": f"no moment {moment_id!r}"}

    def tactical_picture(self) -> dict[str, Any]:
        st = self.st
        idx = st.match_minute()
        out: dict[str, Any] = {"clock": st.clock, "control_chaos": control_chaos(st, idx), "rhythm": rhythm(st, idx), "teams": {}}
        for tid in (st.home, st.away):
            near, line = shape_series(st, tid, idx)
            recent_near = [v for v in near[-6:] if v == v]
            recent_line = [v for v in line[-6:] if v == v]
            out["teams"][st.names[tid]] = {
                "ppda_last_10": ppda(st, tid, idx, 10),
                "players_near_ball_in_opponent_buildup": round(sum(recent_near) / len(recent_near), 2) if recent_near else None,
                "defensive_line_height_m": round(sum(recent_line) / len(recent_line), 1) if recent_line else None,
                "pressures": st.team[tid].pressures,
                "high_regains": st.team[tid].high_regains,
            }
        shifts = [m for m in self.ctx.moments if m.kind == "press_shift"]
        out["press_shifts"] = [{"clock": m.clock, "team": st.names.get(m.team or "", ""), "direction": m.facts["direction"],
                                "since": m.facts["onset_clock"], "players_near_ball": [m.facts["players_near_ball_before"],
                                                                                         m.facts["players_near_ball_after"]],
                                "line_height_m": [m.facts["line_height_before_m"], m.facts["line_height_after_m"]]}
                               for m in shifts[-3:]]
        return out

    def win_probability_path(self, points: int = 12) -> list[dict[str, Any]]:
        series = self.st.wp_series
        if len(series) <= points:
            return series
        step = max(1, len(series) // points)
        keep = [s for s in series if not s["label"].endswith("'")]  # every goal / red card
        return sorted({id(s): s for s in series[::step] + keep}.values(), key=lambda s: s["t"])

    def compare_players(self, player_a: str, player_b: str) -> dict[str, Any]:
        return {"a": self.player_stats(player_a), "b": self.player_stats(player_b)}

    # ------------------------------------------------------------------ agent framework tools
    def function_tools(self) -> list[Any]:
        t = self

        @tool(name="get_match_status", description="Score, clock, status, live win probability and momentum.")
        def get_match_status() -> dict[str, Any]:
            return t.match_status()

        @tool(name="get_team_stats", description="Live team statistics: xG, shots, possession, passing, pressing, PPDA inputs.")
        def get_team_stats(team: Annotated[str, "Team name or id, e.g. 'Northbridge' or 'CAL'"]) -> dict[str, Any]:
            return t.team_stats(team)

        @tool(name="get_player_stats", description="Live player statistics incl. tracking: distance, top speed, sprints, pass difficulty.")
        def get_player_stats(player: Annotated[str, "Player name or surname"]) -> dict[str, Any]:
            return t.player_stats(player)

        @tool(name="get_top_players", description="Leaderboard by a metric such as rating, xg, distance_km, top_speed_kmh, passes.")
        def get_top_players(metric: Annotated[str, "Metric to rank by"] = "rating",
                            n: Annotated[int, "How many"] = 5,
                            team: Annotated[str | None, "Optional team filter"] = None) -> list[dict[str, Any]]:
            return t.top_players(metric, n, team)

        @tool(name="list_key_moments", description="Key moments so far (goals, big chances, press shifts, control/chaos swings).")
        def list_key_moments(kind: Annotated[str, "Moment kind or 'any'"] = "any",
                             limit: Annotated[int, "Max moments"] = 6) -> list[dict[str, Any]]:
            return t.key_moments(kind, limit)

        @tool(name="explain_moment", description="Full explanation of one moment: facts, why-factors and evidence event ids.")
        def explain_moment(moment_id: Annotated[str, "Moment id such as m012"]) -> dict[str, Any]:
            return t.explain_moment(moment_id)

        @tool(name="get_tactical_picture", description="Control vs chaos index, game rhythm, pressing intensity, line heights, press shifts.")
        def get_tactical_picture() -> dict[str, Any]:
            return t.tactical_picture()

        @tool(name="get_win_probability_path", description="How each side's win probability has moved through the match.")
        def get_win_probability_path() -> list[dict[str, Any]]:
            return t.win_probability_path()

        @tool(name="compare_players", description="Side-by-side live stats for two players.")
        def compare_players(player_a: Annotated[str, "First player"], player_b: Annotated[str, "Second player"]) -> dict[str, Any]:
            return t.compare_players(player_a, player_b)

        return [get_match_status, get_team_stats, get_player_stats, get_top_players, list_key_moments, explain_moment,
                get_tactical_picture, get_win_probability_path, compare_players]
