"""Automated match recaps (half time and full time).

The Recap agent writes the story of the match from ranked moments, the
win-probability path and player ratings. Offline, the same JSON contract is
filled from templates; either way the Verifier checks every figure and every
turning point carries its evidence ids.
"""

from __future__ import annotations

import re
from typing import Any

from ..intel.moments import Moment
from ..intel.state import MatchState
from .templates import Names, narrate, num

STORY_KINDS = {"goal", "red_card", "press_shift", "momentum_swing", "big_chance"}

R = {
    "edge": {"en": "{w} edge {l} {s}", "es": "{w} se impone a {l} por {s}", "fr": "{w} s'impose face à {l} ({s})",
             "ar": "{w} يتفوق على {l} {s}", "pt": "{w} vence {l} por {s}"},
    "beat": {"en": "{w} beat {l} {s}", "es": "{w} vence a {l} por {s}", "fr": "{w} bat {l} {s}",
             "ar": "{w} يهزم {l} {s}", "pt": "{w} bate {l} por {s}"},
    "rout": {"en": "{w} run riot against {l}, {s}", "es": "{w} arrolla a {l}: {s}", "fr": "{w} écrase {l} {s}",
             "ar": "{w} يكتسح {l} {s}", "pt": "{w} atropela {l}: {s}"},
    "comeback": {"en": "{w} fight back to beat {l} {s}", "es": "{w} remonta y vence a {l} por {s}",
                 "fr": "{w} renverse {l} ({s})", "ar": "{w} يقلب الطاولة على {l} {s}", "pt": "{w} vira e vence {l} por {s}"},
    "draw": {"en": "{h} and {a} share the points at {s}", "es": "{h} y {a} se reparten los puntos: {s}",
             "fr": "{h} et {a} se quittent dos à dos ({s})", "ar": "{h} و{a} يتقاسمان النقاط {s}",
             "pt": "{h} e {a} dividem os pontos: {s}"},
    "ht_lead": {"en": "{w} lead {l} {s} at the break", "es": "{w} gana {s} a {l} al descanso",
                "fr": "{w} mène {s} face à {l} à la pause", "ar": "{w} يتقدم على {l} {s} بين الشوطين",
                "pt": "{w} vence {l} por {s} no intervalo"},
    "ht_level": {"en": "All square at the break: {h} {s} {a}", "es": "Empate al descanso: {h} {s} {a}",
                 "fr": "Égalité à la pause : {h} {s} {a}", "ar": "التعادل بين الشوطين: {h} {s} {a}",
                 "pt": "Empate no intervalo: {h} {s} {a}"},
    "summary": {"en": "xG {hxg}–{axg}, shots {hs}–{as_}, possession {hp}%–{ap}%.",
                "es": "xG {hxg}–{axg}, tiros {hs}–{as_}, posesión {hp}%–{ap}%.",
                "fr": "xG {hxg}–{axg}, tirs {hs}–{as_}, possession {hp} %–{ap} %.",
                "ar": "xG {hxg}–{axg}، التسديدات {hs}–{as_}، الاستحواذ {hp}%–{ap}%.",
                "pt": "xG {hxg}–{axg}, chutes {hs}–{as_}, posse {hp}%–{ap}%."},
    "low": {"en": "{t}'s win probability bottomed out at {p}% around {c} before the turnaround.",
            "es": "La probabilidad de victoria de {t} tocó fondo en el {p}% hacia el {c} antes de la remontada.",
            "fr": "La probabilité de victoire de {t} est tombée à {p} % vers la {c} avant le retournement.",
            "ar": "احتمال فوز {t} هبط إلى {p}% قرابة الدقيقة {c} قبل أن ينقلب كل شيء.",
            "pt": "A probabilidade de vitória do {t} chegou a {p}% por volta dos {c} antes da virada."},
    "fav": {"en": "{t} were favourites from {c} onwards.", "es": "{t} fue favorito desde el {c}.",
            "fr": "{t} était favori à partir de la {c}.", "ar": "كان {t} المرشح الأوفر حظا منذ الدقيقة {c}.",
            "pt": "O {t} foi favorito a partir dos {c}."},
    "potm": {"en": "{g} goal(s), {a} assist(s), {kp} key passes, {xg} xG, {d} km covered",
             "es": "{g} gol(es), {a} asistencia(s), {kp} pases clave, {xg} xG, {d} km recorridos",
             "fr": "{g} but(s), {a} passe(s) décisive(s), {kp} passes clés, {xg} xG, {d} km parcourus",
             "ar": "{g} هدف، {a} صناعة، {kp} تمريرات مفتاحية، {xg} xG، {d} كم مقطوعة",
             "pt": "{g} gol(s), {a} assistência(s), {kp} passes decisivos, {xg} xG, {d} km percorridos"},
    "no_shift": {"en": "Neither side changed its pressing plan significantly; the tracking data shows stable shapes.",
                 "es": "Ningún equipo cambió su plan de presión de forma significativa; el tracking muestra estructuras estables.",
                 "fr": "Aucune équipe n'a modifié son plan de pressing de façon nette ; le tracking montre des blocs stables.",
                 "ar": "لم يغيّر أي فريق خطة الضغط بشكل واضح؛ بيانات التتبع تُظهر تشكيلات مستقرة.",
                 "pt": "Nenhum time mudou o plano de pressão de forma clara; o rastreamento mostra estruturas estáveis."},
    "live_lead": {"en": "{w} lead {l} {s} at {c}", "es": "{w} gana {s} a {l} en el {c}", "fr": "{w} mène {s} face à {l} à la {c}",
                  "ar": "{w} يتقدم على {l} {s} في الدقيقة {c}", "pt": "{w} vence {l} por {s} aos {c}"},
    "live_level": {"en": "{h} {s} {a} at {c}", "es": "{h} {s} {a} en el {c}", "fr": "{h} {s} {a} à la {c}",
                   "ar": "{h} {s} {a} في الدقيقة {c}", "pt": "{h} {s} {a} aos {c}"},
    "close_live": {"en": "Still everything to play for.", "es": "Todo por decidir.", "fr": "Rien n'est encore joué.",
                   "ar": "كل شيء ما زال ممكنا.", "pt": "Tudo em aberto."},
    "close_win": {"en": "Three points for {w}.", "es": "Tres puntos para {w}.", "fr": "Trois points pour {w}.",
                  "ar": "ثلاث نقاط لـ{w}.", "pt": "Três pontos para o {w}."},
    "close_draw": {"en": "A point apiece.", "es": "Un punto para cada uno.", "fr": "Un point chacun.",
                   "ar": "نقطة لكل فريق.", "pt": "Um ponto para cada lado."},
    "close_ht": {"en": "Forty-five minutes to go.", "es": "Quedan cuarenta y cinco minutos.", "fr": "Encore quarante-cinq minutes.",
                 "ar": "تتبقى خمس وأربعون دقيقة.", "pt": "Faltam quarenta e cinco minutos."},
}


def recap_payload(state: MatchState, moments: list[Moment], names: dict[str, dict[str, str]], language: str,
                  persona: str, period: str) -> dict[str, Any]:
    ranked = sorted((m for m in moments if m.kind in STORY_KINDS and m.importance >= 45), key=lambda m: -m.importance)[:8]
    return {
        "task": "recap",
        "language": language,
        "persona": persona,
        "period": period,
        "clock": state.clock,
        "home": state.home,
        "away": state.away,
        "names": names,
        "score": dict(state.score),
        "teams": {t: state.team_view(t) for t in (state.home, state.away)},
        "top_players": state.top_players(n=5),
        "moments": [m.as_dict() for m in sorted(ranked, key=lambda m: m.t)],
        "wp_path": list(state.wp_series),  # a copy: a stored report must not keep growing
    }


_IDS_IN_PROSE = re.compile(r"\s*\((?:[me]\d{3,6})(?:\s*[,،]\s*[me]\d{3,6})*\)")


def normalize_recap(data: dict[str, Any], p: dict[str, Any], roster: dict[str, str]) -> dict[str, Any]:
    """The report as the screen shows it: evidence ids belong in turning_points[].evidence, not in the prose, and the
    player of the match is bound to the roster (name and rating come from match data, never from the model)."""
    out = dict(data)
    for key in ("headline", "summary", "tactical_story", "closing_line"):
        if isinstance(out.get(key), str):
            out[key] = _IDS_IN_PROSE.sub("", out[key]).strip()
    out["turning_points"] = [{**tp, "text": _IDS_IN_PROSE.sub("", str(tp.get("text", ""))).strip()}
                             for tp in out.get("turning_points") or [] if isinstance(tp, dict)]
    potm = dict(out.get("player_of_the_match") or {})
    pid = potm.get("player_id")
    potm.pop("rating", None)
    if isinstance(pid, str) and pid in roster:
        potm["name"] = roster[pid]
        rated = next((t for t in p.get("top_players", []) if t.get("id") == pid), None)
        if rated and rated.get("rating") is not None:
            potm["rating"] = rated["rating"]
    if isinstance(potm.get("reason"), str):
        potm["reason"] = _IDS_IN_PROSE.sub("", potm["reason"]).strip()
    out["player_of_the_match"] = potm
    return out


def recap_fields(data: dict[str, Any], p: dict[str, Any], roster: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Every text the Recap screen shows, for the Verifier, plus structural problems text checks cannot see: a player of
    the match who is not in this match, turning points at a minute or with evidence the match data does not have."""
    fields = {"headline": data.get("headline", ""), "summary": data.get("summary", ""),
              "tactical": data.get("tactical_story", ""), "closing": data.get("closing_line", "")}
    potm = data.get("player_of_the_match") or {}
    fields["potm"] = str(potm.get("reason", ""))
    issues: list[str] = []
    if potm and potm.get("player_id") not in roster:
        issues.append(f"player of the match {potm.get('player_id')!r} is not a player in this match")
    clocks = {m.get("clock") for m in p.get("moments", [])}
    known = {m["id"] for m in p.get("moments", [])} | {e for m in p.get("moments", []) for e in m.get("evidence", [])}
    for i, tp in enumerate(data.get("turning_points") or []):
        fields[f"tp{i}"] = str(tp.get("text", ""))
        if tp.get("clock") not in clocks:
            issues.append(f"turning point {i + 1}: {tp.get('clock')!r} is not the minute of a moment in this match")
        bad = [e for e in tp.get("evidence") or [] if e not in known]
        if bad:
            issues.append(f"turning point {i + 1}: evidence {', '.join(map(str, bad[:3]))} is not in the match data")
    return fields, issues


def recap_evidence(p: dict[str, Any]) -> list[Any]:
    """What the Verifier checks a recap against: deterministic match data only, with each moment's minute."""
    return [p["teams"], p["score"], p["top_players"], [{"clock": m.get("clock", ""), **m["facts"]} for m in p["moments"]],
            p["wp_path"], {"clock": p.get("clock", "")}]


def offline_recap(p: dict[str, Any]) -> dict[str, Any]:
    lang = p["language"] if p["language"] in R["edge"] else "en"
    persona = p.get("persona", "casual")
    names = Names(p["names"]["players"], p["names"]["teams"])
    h, a = p["home"], p["away"]
    hn, an = names.t(h), names.t(a)
    sh, sa = p["score"][h], p["score"][a]
    score = f"{sh}-{sa}"
    teams = p["teams"]
    wp = p["wp_path"]
    clock = p.get("clock", "")
    clock = clock.rstrip("'") if lang == "ar" else clock
    if p.get("live"):
        if sh == sa:
            headline = R["live_level"][lang].format(h=hn, a=an, s=score, c=clock)
        else:
            w, lo = (hn, an) if sh > sa else (an, hn)
            headline = R["live_lead"][lang].format(w=w, l=lo, s=f"{max(sh, sa)}-{min(sh, sa)}", c=clock)
        closing = R["close_live"][lang]
    elif p["period"] == "half_time":
        if sh == sa:
            headline = R["ht_level"][lang].format(h=hn, a=an, s=score)
        else:
            w, lo = (hn, an) if sh > sa else (an, hn)
            headline = R["ht_lead"][lang].format(w=w, l=lo, s=f"{max(sh, sa)}-{min(sh, sa)}")
        closing = R["close_ht"][lang]
    elif sh == sa:
        headline = R["draw"][lang].format(h=hn, a=an, s=score)
        closing = R["close_draw"][lang]
    else:
        wid = h if sh > sa else a
        w, lo = names.t(wid), names.t(a if wid == h else h)
        key = "home" if wid == h else "away"
        low = min(wp, key=lambda x: x[key]) if wp else None
        margin = abs(sh - sa)
        style = "comeback" if low and low[key] < 0.25 else ("edge" if margin == 1 else ("beat" if margin == 2 else "rout"))
        headline = R[style][lang].format(w=w, l=lo, s=f"{max(sh, sa)}-{min(sh, sa)}")
        closing = R["close_win"][lang].format(w=w)
    summary = R["summary"][lang].format(
        hxg=num(teams[h]["xg"], lang, 2), axg=num(teams[a]["xg"], lang, 2), hs=teams[h]["shots"], as_=teams[a]["shots"],
        hp=num(teams[h]["possession"], lang), ap=num(teams[a]["possession"], lang))
    if wp and sh != sa and p["period"] != "half_time":
        wid = h if sh > sa else a
        key = "home" if wid == h else "away"
        low = min(wp, key=lambda x: x[key])
        if low[key] < 0.35:
            summary += " " + R["low"][lang].format(t=names.t(wid), p=round(100 * low[key]), c=low["clock"].rstrip("'") if lang == "ar" else low["clock"])
        else:
            fav = next((x for x in wp if x[key] > 0.5), None)
            if fav:
                summary += " " + R["fav"][lang].format(t=names.t(wid), c=fav["clock"].rstrip("'") if lang == "ar" else fav["clock"])
    turning = []
    for m in p["moments"]:
        if m["kind"] in {"goal", "red_card", "press_shift"}:
            line = narrate(m, names, lang, "analyst" if persona == "analyst" else "casual", h, a)["line"]
            turning.append({"clock": m["clock"], "text": line, "evidence": m.get("evidence") or [m["id"]], "moment_id": m["id"]})
    tp = (p.get("top_players") or [{}])[0]
    potm = {
        "player_id": tp.get("id", ""), "name": tp.get("name", ""),
        "reason": R["potm"][lang].format(g=tp.get("goals", 0), a=tp.get("assists", 0), kp=tp.get("key_passes", 0),
                                         xg=num(tp.get("xg", 0), lang, 2), d=num(tp.get("distance_km", 0), lang, 1)),
        "rating": tp.get("rating"),
    }
    shifts = [m for m in p["moments"] if m["kind"] == "press_shift"]
    tactical = " ".join(narrate(m, names, lang, "analyst", h, a)["line"] for m in shifts[:2]) or R["no_shift"][lang]
    return {"headline": headline, "summary": summary, "turning_points": turning[:5], "player_of_the_match": potm,
            "tactical_story": tactical, "closing_line": closing}
