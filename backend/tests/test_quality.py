"""What a judge reads: Arabic scores that read the right way round, copy without claims no data can back, and latency
figures that mean what they say."""

from __future__ import annotations

from regista.agents.telemetry import Span, Telemetry
from regista.agents.templates import rtl_safe, rtl_safe_all
from regista.agents.verifier import verify_texts
from regista.runtime.session import MatchSession
from regista.schema.profiles import FanProfile, Mode

LRI, PDI = "⁦", "⁩"


def test_scores_and_minutes_keep_their_order_inside_arabic():
    # an Arabic word before "2-1" would otherwise display it as "1-2"
    assert rtl_safe("Northbridge يسجل · 2-1", "ar") == f"Northbridge يسجل · {LRI}2-1{PDI}"
    assert rtl_safe("في الدقيقة 45+2'", "ar") == f"في الدقيقة {LRI}45+2'{PDI}"
    assert rtl_safe(rtl_safe("2-1", "ar"), "ar") == f"{LRI}2-1{PDI}"  # never wrapped twice
    assert rtl_safe("79.3 كم/س و 14%", "ar") == "79.3 كم/س و 14%"  # decimals and percentages already read correctly
    assert rtl_safe("Northbridge 2-1", "en") == "Northbridge 2-1"
    assert rtl_safe_all({"a": ["1-1", {"b": "3-0"}]}, "ar") == {"a": [f"{LRI}1-1{PDI}", {"b": f"{LRI}3-0{PDI}"}]}


def test_amiras_goal_card_shows_the_score_the_right_way_round():
    s = MatchSession(story_workers=0)
    s.advance(float(s.res.frame_t[-1]) - s.clock_t + 1, live=False)  # whichever match is loaded, find its first goal
    goal = next(m for m in s.moments if m.kind == "goal")
    cue = s.producer.by_moment[goal.id]
    amira = s.connect(FanProfile(id="amira", mode=Mode.CASUAL, language="ar", favorite_team="CAL"))
    out, _ = amira.director.preview(cue)
    assert f"{LRI}{goal.facts['score_text']}{PDI}" in out.title + out.body


def test_claims_about_feelings_and_the_future_are_rejected_in_every_language():
    facts = {"score": {"NOR": 2, "CAL": 1}}
    bad = {"en": ["This goal boosted their confidence.", "It likely forced Port Calder to take more risks.",
                  "Port Calder will have to attack now.", "promising an engaging tactical battle ahead"],
           "es": ["Un golpe a la moral de Port Calder.", "Port Calder tendrá que arriesgar."],
           "fr": ["La confiance de Northbridge grandit.", "Port Calder va devoir réagir."],
           "pt": ["A confiança da equipe cresceu.", "O Port Calder terá que atacar."],
           "ar": ["رفع هذا الهدف المعنويات.", "سيضطر بورت كالدر للهجوم."]}
    for lang, lines in bad.items():
        for line in lines:
            v = verify_texts({lang: {"casual": {"line": line}}}, [facts], set(), {})
            assert not v.ok and "feel or what happens next" in v.issues[0], (lang, line)
    for line in ["Detected from tracking data, not inferred from the score. Confidence z = 6.4.",
                 "Northbridge lead 2-1 after Valdane scored."]:
        assert verify_texts({"en": {"casual": {"line": line}}}, [{**facts, "z_score": 6.4}], set(), {}).ok, line


def test_untimed_steps_do_not_drag_the_latency_figures():
    t = Telemetry()
    for ms in (3000.0, 4000.0, 5000.0):
        t.record(Span("Analyst", "ok", ms, "model"))
    for _ in range(10):  # routine moments explained by rules, no model call, no timing
        t.record(Span("Analyst", "ok", 0.0, "deterministic"))
    t.record(Span("Producer", "ok", 0.0, "deterministic"))
    agents = t.summary()["agents"]
    assert agents["Analyst"]["p50_ms"] == 4000.0 and agents["Analyst"]["calls"] == 13
    assert agents.get("Producer", {}).get("p50_ms") is None
