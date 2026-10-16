"""Fictional clubs and players for the synthetic league.

Every name here is invented. No real club, player, crest or trademark is used,
so generated matches are safe to broadcast, publish and demo.

Formation anchors are expressed in the team's own attacking frame:
x = 0 is the team's own goal line, x = 105 the goal it attacks; y runs 0..68
with y < 34 being the team's right-hand side.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FORMATIONS: dict[str, list[tuple[str, float, float]]] = {
    "4-3-3": [
        ("GK", 4, 34),
        ("RB", 38, 8),
        ("CB", 27, 24),
        ("CB", 27, 44),
        ("LB", 38, 60),
        ("DM", 42, 34),
        ("CM", 56, 21),
        ("CM", 56, 47),
        ("RW", 76, 9),
        ("ST", 82, 34),
        ("LW", 76, 59),
    ],
    "4-2-3-1": [
        ("GK", 4, 34),
        ("RB", 36, 8),
        ("CB", 26, 24),
        ("CB", 26, 44),
        ("LB", 36, 60),
        ("DM", 43, 26),
        ("DM", 43, 42),
        ("RW", 68, 10),
        ("AM", 66, 34),
        ("LW", 68, 58),
        ("ST", 81, 34),
    ],
    "4-4-2": [
        ("GK", 4, 34),
        ("RB", 36, 8),
        ("CB", 26, 25),
        ("CB", 26, 43),
        ("LB", 36, 60),
        ("RM", 58, 9),
        ("CM", 50, 27),
        ("CM", 50, 41),
        ("LM", 58, 59),
        ("ST", 80, 27),
        ("ST", 80, 41),
    ],
}


@dataclass
class Player:
    id: str
    name: str
    short_name: str
    number: int
    position: str
    nationality: str
    age: int
    top_speed_kmh: float
    passing: float
    vision: float
    finishing: float
    dribbling: float
    tackling: float
    pressing: float
    stamina: float
    aerial: float
    starting: bool = True
    slot: int = -1  # formation slot index when on the pitch


@dataclass
class Style:
    press_intensity: float  # 0 passive .. 1 relentless high press
    directness: float  # 0 patient circulation .. 1 vertical/long
    width: float  # 0 narrow .. 1 very wide
    tempo: float  # 0 slow .. 1 fast
    line_height: float  # 0 deep block .. 1 high line
    strength: float  # overall quality prior, ~0.8 .. 1.2

    def copy(self) -> Style:
        return Style(**self.__dict__)


@dataclass
class Team:
    id: str
    name: str
    short_name: str
    abbr: str
    primary: str
    secondary: str
    formation: str
    style_label: str
    style: Style
    players: list[Player] = field(default_factory=list)

    @property
    def starters(self) -> list[Player]:
        return [p for p in self.players if p.starting]

    @property
    def bench(self) -> list[Player]:
        return [p for p in self.players if not p.starting]


def _p(team: str, n: int, name: str, short: str, pos: str, nat: str, age: int, spd: float, **attrs: float) -> Player:
    base = dict(
        passing=0.72,
        vision=0.65,
        finishing=0.45,
        dribbling=0.6,
        tackling=0.55,
        pressing=0.6,
        stamina=0.75,
        aerial=0.55,
    )
    base.update(attrs)
    return Player(
        id=f"{team}-{n:02d}",
        name=name,
        short_name=short,
        number=n,
        position=pos,
        nationality=nat,
        age=age,
        top_speed_kmh=spd,
        **base,
    )


def northbridge() -> Team:
    t = "NOR"
    players = [
        _p(t, 1, "Mats Lindqvist", "Lindqvist", "GK", "Sweden", 29, 27.5, passing=0.66, aerial=0.8),
        _p(t, 2, "Jayden Okafor", "Okafor", "RB", "Nigeria", 24, 34.1, tackling=0.68, pressing=0.74, stamina=0.88),
        _p(t, 4, "Rui Fontes", "Fontes", "CB", "Portugal", 28, 31.2, tackling=0.8, aerial=0.82, passing=0.78),
        _p(t, 5, "Callum Reid", "Reid", "CB", "Scotland", 31, 30.0, tackling=0.82, aerial=0.86),
        _p(t, 3, "Idris Benali", "Benali", "LB", "Morocco", 23, 34.6, dribbling=0.7, stamina=0.9, pressing=0.72),
        _p(t, 6, "Sami Haddad", "Haddad", "DM", "Lebanon", 27, 31.0, passing=0.86, tackling=0.78, pressing=0.8, vision=0.78),
        _p(t, 8, "Leo Marchetti", "Marchetti", "CM", "Italy", 26, 32.2, passing=0.84, stamina=0.92, pressing=0.82),
        _p(t, 10, "Kenji Arata", "Arata", "CM", "Japan", 25, 32.5, passing=0.9, vision=0.93, dribbling=0.82, finishing=0.6),
        _p(t, 7, "Diego Salvatierra", "Salvatierra", "RW", "Chile", 22, 35.4, dribbling=0.88, finishing=0.64, pressing=0.7),
        _p(t, 9, "Teo Valdane", "Valdane", "ST", "Uruguay", 27, 33.6, finishing=0.86, aerial=0.78, dribbling=0.7, pressing=0.78),
        _p(t, 11, "Noah Brightwell", "Brightwell", "LW", "England", 21, 35.9, dribbling=0.84, finishing=0.66),
        _p(t, 12, "Pieter de Waal", "de Waal", "GK", "Netherlands", 33, 26.8),
        _p(t, 14, "Oskar Wren", "Wren", "CM", "Denmark", 20, 32.0, passing=0.8, pressing=0.8),
        _p(t, 15, "Thabo Nkosi", "Nkosi", "CB", "South Africa", 25, 31.8, tackling=0.78, aerial=0.8),
        _p(t, 17, "Malik Diarra", "Diarra", "ST", "Mali", 23, 34.8, finishing=0.8, aerial=0.74),
        _p(t, 19, "Elias Varga", "Varga", "LW", "Hungary", 24, 35.2, dribbling=0.83, finishing=0.62),
    ]
    for p in players[11:]:
        p.starting = False
    return Team(
        id=t,
        name="Northbridge Rovers",
        short_name="Northbridge",
        abbr="NOR",
        primary="#0E7C7B",
        secondary="#F2F4F3",
        formation="4-3-3",
        style_label="Possession and high press",
        style=Style(press_intensity=0.78, directness=0.32, width=0.7, tempo=0.66, line_height=0.74, strength=1.06),
        players=players,
    )


def port_calder() -> Team:
    t = "CAL"
    players = [
        _p(t, 1, "Ivo Brandt", "Brandt", "GK", "Germany", 30, 27.0, passing=0.62, aerial=0.84),
        _p(t, 2, "Marcus Ade", "Ade", "RB", "Ghana", 26, 33.8, tackling=0.7, stamina=0.86),
        _p(t, 5, "Tomas Kral", "Kral", "CB", "Czechia", 29, 30.4, tackling=0.84, aerial=0.88),
        _p(t, 6, "Yusuf Erdem", "Erdem", "CB", "Türkiye", 27, 31.0, tackling=0.8, aerial=0.83, passing=0.74),
        _p(t, 3, "Liam Carrow", "Carrow", "LB", "Ireland", 25, 33.5, stamina=0.88, tackling=0.68),
        _p(t, 4, "Ander Iturra", "Iturra", "DM", "Spain", 30, 30.2, tackling=0.84, passing=0.8, pressing=0.66),
        _p(t, 8, "Felix Osei", "Osei", "DM", "Ghana", 24, 32.4, stamina=0.92, tackling=0.78, pressing=0.7),
        _p(t, 7, "Min-jun Seo", "Seo", "RW", "Korea Republic", 23, 35.6, dribbling=0.84, finishing=0.64),
        _p(t, 10, "Rafael Quintero", "Quintero", "AM", "Colombia", 27, 32.0, passing=0.88, vision=0.92, dribbling=0.85, finishing=0.68),
        _p(t, 11, "Bastien Morel", "Morel", "LW", "France", 22, 35.1, dribbling=0.82, finishing=0.6),
        _p(t, 9, "Dario Pellegrini", "Pellegrini", "ST", "Argentina", 29, 33.0, finishing=0.84, aerial=0.86, pressing=0.6),
        _p(t, 13, "Owen Hale", "Hale", "GK", "Wales", 27, 26.5),
        _p(t, 14, "Kwame Asante", "Asante", "CM", "Ghana", 21, 33.0, pressing=0.8, stamina=0.9),
        _p(t, 16, "Nils Ekdahl", "Ekdahl", "CB", "Norway", 26, 31.0, tackling=0.78, aerial=0.84),
        _p(t, 18, "Hugo Lacombe", "Lacombe", "ST", "France", 24, 34.2, finishing=0.78, pressing=0.76),
        _p(t, 20, "Arjun Mehta", "Mehta", "RW", "India", 22, 35.0, dribbling=0.82, finishing=0.6),
    ]
    for p in players[11:]:
        p.starting = False
    return Team(
        id=t,
        name="Port Calder FC",
        short_name="Port Calder",
        abbr="CAL",
        primary="#E4572E",
        secondary="#17255A",
        formation="4-2-3-1",
        style_label="Mid-block and fast counters",
        style=Style(press_intensity=0.42, directness=0.66, width=0.62, tempo=0.58, line_height=0.42, strength=0.98),
        players=players,
    )


def ashvale() -> Team:
    t = "ASH"
    names = [
        ("Grant Moffat", "GK", "Scotland"), ("Elijah Brooks", "RB", "England"), ("Matteo Ricci", "CB", "Italy"),
        ("Samuel Adeyemi", "CB", "Nigeria"), ("Lucas Ferreira", "LB", "Portugal"), ("Hamza Idrissi", "CM", "Morocco"),
        ("Jonas Albrecht", "CM", "Germany"), ("Tomás Rivera", "RM", "Mexico"), ("Ryo Tanaka", "LM", "Japan"),
        ("Kieran Doyle", "ST", "Ireland"), ("Ade Ogun", "ST", "Nigeria"), ("Finn Larsen", "GK", "Denmark"),
        ("Pablo Ortega", "CM", "Spain"), ("Dominik Novak", "CB", "Slovakia"), ("Zane Mitchell", "ST", "Australia"),
        ("Yannick Bonsu", "RM", "Ghana"),
    ]
    players = [
        _p(t, i + 1, n, n.split()[-1], pos, nat, 22 + (i * 3) % 11, 31.0 + (i * 7 % 9) * 0.5)
        for i, (n, pos, nat) in enumerate(names)
    ]
    for p in players[11:]:
        p.starting = False
    return Team(
        id=t, name="Ashvale Town", short_name="Ashvale", abbr="ASH", primary="#5B2A86", secondary="#F7C548",
        formation="4-4-2", style_label="Compact and direct",
        style=Style(press_intensity=0.5, directness=0.74, width=0.55, tempo=0.6, line_height=0.45, strength=0.94),
        players=players,
    )


def kestrel() -> Team:
    t = "KES"
    names = [
        ("Andre Castillo", "GK", "Spain"), ("Bram Visser", "RB", "Netherlands"), ("Oumar Keita", "CB", "Senegal"),
        ("Henrik Dahl", "CB", "Norway"), ("Mateus Lima", "LB", "Portugal"), ("Ilya Sokolenko", "DM", "Ukraine"),
        ("Charlie Pembroke", "CM", "England"), ("Sergio Vidal", "CM", "Spain"), ("Karim Mansour", "RW", "Egypt"),
        ("Luca Bianchi", "ST", "Italy"), ("Tariq Hassan", "LW", "Jordan"), ("Joe Whitlock", "GK", "England"),
        ("Emeka Obi", "CM", "Nigeria"), ("Viktor Lund", "CB", "Sweden"), ("Nico Herrera", "ST", "Argentina"),
        ("Sami Lahti", "LW", "Finland"),
    ]
    players = [
        _p(t, i + 1, n, n.split()[-1], pos, nat, 21 + (i * 5) % 12, 31.5 + (i * 5 % 8) * 0.5)
        for i, (n, pos, nat) in enumerate(names)
    ]
    for p in players[11:]:
        p.starting = False
    return Team(
        id=t, name="Kestrel City", short_name="Kestrel", abbr="KES", primary="#1D4ED8", secondary="#E5E7EB",
        formation="4-3-3", style_label="Wing play and crosses",
        style=Style(press_intensity=0.6, directness=0.5, width=0.86, tempo=0.62, line_height=0.6, strength=1.0),
        players=players,
    )


TEAMS = {"NOR": northbridge, "CAL": port_calder, "ASH": ashvale, "KES": kestrel}


def load_team(team_id: str) -> Team:
    try:
        team = TEAMS[team_id.upper()]()
    except KeyError as exc:
        raise ValueError(f"Unknown team {team_id!r}; choose from {sorted(TEAMS)}") from exc
    shape = FORMATIONS[team.formation]
    for i, player in enumerate(team.starters):
        player.slot = i
        player.position = shape[i][0] if player.position != "GK" else "GK"
    return team
