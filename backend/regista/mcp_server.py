"""Regista MCP server: the live match as tools any agent can use.

Mounted at /mcp on the API (streamable HTTP), so GitHub Copilot agent mode
in VS Code, Microsoft Foundry agents or any MCP client can ask "why are
Northbridge suddenly winning the ball so high?" and get grounded answers
from the same tools the Pundit agent uses. Also runnable over stdio:
`regista mcp`.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from .runtime.session import MatchSession

INSTRUCTIONS = (
    "Live football match intelligence from Regista. Every figure is computed from a synthetic event + tracking feed. "
    "Call get_match_status first, then the specific tool. Prefer get_tactical_picture for 'why' questions about "
    "pressing, control or chaos, and explain_moment for evidence behind a key moment."
)


def build_mcp(session_ref: dict[str, MatchSession]) -> MCPServer:
    mcp = MCPServer(name="regista", title="Regista match intelligence", instructions=INSTRUCTIONS, version="0.1.0")

    def tools() -> Any:
        return session_ref["session"].tools

    @mcp.tool(description="Score, clock, status, live win probability and momentum for the match in progress.")
    def get_match_status() -> dict[str, Any]:
        return tools().match_status()

    @mcp.tool(description="Live team statistics (xG, shots, possession, passing, pressing). team: name or id.")
    def get_team_stats(team: str) -> dict[str, Any]:
        return tools().team_stats(team)

    @mcp.tool(description="Live player statistics including tracking: distance, top speed, sprints, pass difficulty.")
    def get_player_stats(player: str) -> dict[str, Any]:
        return tools().player_stats(player)

    @mcp.tool(description="Leaderboard by metric: rating, xg, distance_km, top_speed_kmh, passes, opponents_bypassed.")
    def get_top_players(metric: str = "rating", n: int = 5, team: str | None = None) -> list[dict[str, Any]]:
        return tools().top_players(metric, n, team)

    @mcp.tool(description="Key moments so far, optionally filtered by kind (goal, big_chance, press_shift, control_chaos...).")
    def list_key_moments(kind: str = "any", limit: int = 6) -> list[dict[str, Any]]:
        return tools().key_moments(kind, limit)

    @mcp.tool(description="Full explanation of one moment: facts, why-factors and evidence event ids.")
    def explain_moment(moment_id: str) -> dict[str, Any]:
        return tools().explain_moment(moment_id)

    @mcp.tool(description="Control vs chaos index, game rhythm, pressing intensity, defensive line heights, press shifts.")
    def get_tactical_picture() -> dict[str, Any]:
        return tools().tactical_picture()

    @mcp.tool(description="How each side's win probability has moved through the match.")
    def get_win_probability_path() -> list[dict[str, Any]]:
        return tools().win_probability_path()

    @mcp.tool(description="Side-by-side live stats for two players.")
    def compare_players(player_a: str, player_b: str) -> dict[str, Any]:
        return tools().compare_players(player_a, player_b)

    @mcp.tool(description="Automated match recap in a language (en, es, fr, ar, pt) and persona (casual, analyst, new_fan).")
    async def get_recap(language: str = "en", persona: str = "analyst") -> dict[str, Any]:
        return await session_ref["session"].recap(language, persona)

    @mcp.resource("regista://match/info", name="match-info", mime_type="application/json",
                  description="Teams, squads, venue and roster order of the live match.")
    def match_info() -> dict[str, Any]:
        return session_ref["session"].res.info.model_dump()

    return mcp
