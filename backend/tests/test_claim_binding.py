"""Claims bound to what they describe: a scorer's tally, a team's manpower, a metric's unit and the match minute, in
every supported language. Each case is a mistake a fluent model makes, not a figure chosen to fail."""

from __future__ import annotations

import pytest

from regista.agents.templates import LANGS, Names, narrate
from regista.agents.verifier import verify_texts
from regista.intel.moments import MomentDetector
from regista.intel.state import MatchState
from regista.schema.events import EventType, MatchEvent
from regista.sim.engine import simulate

NAMES = {"NOR-09": "Valdane", "NOR-11": "Brightwell", "NOR-07": "Fontes"}


def ok(text: str, lang: str, facts: dict, context: dict | None = None) -> bool:
    evidence = [facts] + ([context] if context else [])
    return verify_texts({lang: {"analyst": {"line": text}}}, evidence, set(NAMES), NAMES, claims=facts).ok


GOAL = {"scorer": "NOR-09", "scorer_goals": 1, "score": {"NOR": 2, "CAL": 1}, "xg": 0.15, "shot_speed_kmh": 79.0}
TALLY_WRONG = {
    "en": ["Valdane has scored 2 goals.", "Valdane has scored three goals.", "Valdane bags a brace!", "Valdane scores his 2nd goal."],
    "es": ["Valdane ya suma 2 goles.", "Valdane ya lleva tres goles.", "Valdane firma un doblete.", "Valdane marca su segundo gol."],
    "fr": ["Valdane compte 2 buts.", "Valdane a marqué trois buts.", "Valdane signe un doublé.", "Valdane inscrit son deuxième but."],
    "pt": ["Valdane já soma 2 gols.", "Valdane já marcou três gols.", "Valdane faz uma dobradinha.", "Valdane marca o segundo gol."],
    "ar": ["Valdane يرفع رصيده إلى 2 أهداف.", "Valdane سجل ثلاثة أهداف.", "Valdane يسجل ثنائية."],
}
TALLY_RIGHT = {"en": "Valdane's first goal makes it 2-1.", "es": "Primer gol de Valdane: 2-1.", "fr": "Premier but de Valdane : 2-1.",
               "pt": "Primeiro gol de Valdane: 2-1.", "ar": "Valdane يسجل والنتيجة 2-1."}


@pytest.mark.parametrize("lang", LANGS)
def test_a_scorers_tally_must_be_their_own(lang):
    for text in TALLY_WRONG[lang]:
        assert not ok(text, lang, GOAL), text
    assert ok(TALLY_RIGHT[lang], lang, GOAL)


def test_english_but_after_xg_is_not_a_french_goal_unit():
    facts = {**GOAL, "xg": 0.22}
    assert ok("The shot had an xG of 0.22 but went off target.", "en", facts)
    assert not ok("The shot had an xG of 0.47 but went off target.", "en", facts)


@pytest.mark.parametrize("unit", ["but", "buts"])
def test_french_goal_units_still_check_metric_and_scorer_tally(unit):
    facts = {**GOAL, "xg": 0.22}
    assert not ok(f"0.22 {unit}.", "fr", facts)
    assert not ok(f"Valdane compte 2 {unit}.", "fr", facts)
    assert ok(f"Valdane compte 1 {unit}.", "fr", facts)


def test_both_red_cards_give_the_right_manpower_in_every_language():
    """Explicit synthetic feed: two dismissals leave nine, independently of a simulator seed's random cards."""
    st = MatchState(simulate("NOR", "CAL", 101, "derby").info)
    detector = MomentDetector(st)
    reds = []
    for seq, (pid, outcome) in enumerate((("NOR-04", "red"), ("NOR-05", "second_yellow")), 1):
        event = MatchEvent(id=f"test-red-{seq}", match_id=st.info.match_id, seq=seq, t=seq * 60,
                           period=1, minute=seq, second=0, clock=f"{seq}'", type=EventType.CARD,
                           team="NOR", player=pid, outcome=outcome)
        reds.extend(m for m in detector.on_enriched(st.on_event(event)) if m.kind == "red_card")
    assert [m.facts["players_remaining"] for m in reds] == [10, 9]
    names = Names({pid: p.info.short_name for pid, p in st.players.items()}, dict(st.short))
    roster = names.players
    words = {"en": ("ten", "nine"), "es": ("diez", "nueve"), "fr": ("dix", "neuf"), "pt": ("dez", "nove"),
             "ar": ("بعشرة", "بتسعة")}
    for m, left in zip(reds, (10, 9), strict=True):
        for lang in LANGS:
            line = narrate(m.as_dict(), names, lang, "casual", st.home, st.away)["line"]
            right, wrong = (words[lang][0], words[lang][1]) if left == 10 else (words[lang][1], words[lang][0])
            assert right in line and wrong not in line, (lang, line)
            assert verify_texts({lang: {"casual": {"line": line}}}, [m.facts], set(m.players), roster, claims=m.facts).ok
            # the same line with the other count is rejected
            assert not verify_texts({lang: {"casual": {"line": line.replace(right, wrong)}}}, [m.facts], set(m.players),
                                    roster, claims=m.facts).ok, (lang, line)


@pytest.mark.parametrize("lang,text", [
    ("en", "Northbridge are down to ten men."), ("es", "Northbridge se queda con diez."),
    ("fr", "Northbridge est réduit à dix joueurs."), ("pt", "O Northbridge fica com dez."), ("ar", "Northbridge يكمل بعشرة لاعبين."),
])
def test_later_moments_are_held_to_the_current_manpower(lang, text):
    goal = {"scorer": "NOR-09", "scorer_goals": 1, "score": {"NOR": 1, "CAL": 1}}
    assert not ok(text, lang, goal, {"players_on_pitch": {"NOR": 9, "CAL": 11}})
    assert ok(text, lang, goal, {"players_on_pitch": {"NOR": 10, "CAL": 11}})


PRESS = {"press_rate_before": 22.0, "press_rate_after": 31.0, "players_near_ball_after": 0.9}


@pytest.mark.parametrize("lang,wrong,right", [
    ("en", "Pressing up from 22 to 31 actions per minute.", "Pressing up from 22 to 31 per 100 opponent passes."),
    ("es", "La presión sube de 22 a 31 acciones por minuto.", "La presión sube de 22 a 31 por cada 100 pases rivales."),
    ("fr", "Le pressing passe de 22 à 31 actions par minute.", "Le pressing passe de 22 à 31 pour 100 passes adverses."),
    ("pt", "A pressão sobe de 22 para 31 ações por minuto.", "A pressão sobe de 22 para 31 a cada 100 passes rivais."),
    ("ar", "الضغط يرتفع من 22 إلى 31 مرة كل دقيقة.", "الضغط يرتفع من 22 إلى 31 لكل 100 تمريرة للمنافس."),
])
def test_a_rate_keeps_its_unit(lang, wrong, right):
    assert not ok(wrong, lang, PRESS) and ok(right, lang, PRESS)


@pytest.mark.parametrize("lang,text", [
    ("en", "It came in the 99th minute."), ("es", "Llegó en el minuto 99."), ("fr", "C'est arrivé à la 99e minute."),
    ("pt", "Aconteceu no minuto 99."), ("ar", "جاء ذلك في الدقيقة 99."),
])
def test_a_wrong_minute_fails_in_every_language(lang, text):
    """Portuguese 'no minuto' once read as a shirt number ('No. 9') and skipped the minute check."""
    assert not ok(text, lang, {**GOAL, "clock": "74'"}, {"clock": "74'"})


@pytest.mark.parametrize("lang,unit", [("en", "goals"), ("es", "goles"), ("fr", "buts"), ("pt", "gols"), ("ar", "أهداف")])
def test_unicode_decimal_and_long_counts_cannot_evade_unit_checks(lang, unit):
    # Arabic separators previously split 33.0 into the domain constants 33 and 0, checking only "0 goals".
    # Seven also cannot come from scorer ID NOR-09 minus the team's score of two.
    for count in ("٣٣٫٠", "١٬٠٠٠", "10000", "３３．０", "7"):
        assert not ok(f"{count} {unit}", lang, GOAL), (lang, count)
    assert ok(f"١٫٠ {unit}", lang, GOAL)


def test_player_binding_and_exclusions_preserve_unicode_and_case_equivalence():
    names = {"NOR-09": "Élias Valdane", "NOR-11": "José Brightwell"}

    def check(text):
        return verify_texts({"en": {"analyst": {"line": text}}}, [GOAL], {"NOR-09"}, names, claims=GOAL)

    for name in ("Élias Valdane", "élias valdane", "E\u0301lias Valdane"):
        assert not check(f"{name} has 2 goals.").ok
        assert check(f"{name} has 1 goal.").ok
    for name in ("José Brightwell", "josé brightwell", "Jose\u0301 Brightwell"):
        assert not check(f"An assist from {name}.").ok
