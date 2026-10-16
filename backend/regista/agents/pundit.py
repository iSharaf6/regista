"""Pundit: ask the match anything, in your language.

With a model configured, Pundit is an Agent Framework agent that calls the
match tools (function calling) before answering. Offline, a multilingual
intent router calls the same tools and answers from templates - so the
feature is demonstrable anywhere, and both paths cite their tool calls.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from agent_framework import Agent

from . import prompts
from .story import AgentRuntime
from .telemetry import Span
from .templates import num
from .tools import MatchTools, _norm

KEYWORDS = {
    "press": ["press", "pressing", "presion", "presión", "pressão", "pressao", "ضغط", "high line", "line", "winning the ball",
              "win the ball", "so high", "recuper", "récupèr", "recupera", "يستعيد", "tactic", "táctic", "tactique", "تكتيك"],
    "control": ["control", "chaos", "caos", "maîtrise", "maitrise", "possession", "posesion", "posesión", "posse",
                "سيطرة", "فوضى", "استحواذ", "dominat", "domina"],
    "win": ["win", "winning", "probability", "ganar", "victoria", "gagner", "victoire", "vencer", "vitória", "vitoria",
            "فوز", "يفوز", "chance of"],
    "xg": ["xg", "chance", "chances", "ocasion", "ocasión", "occasion", "shots", "tiros", "tirs", "chutes", "فرص", "تسديد"],
    "best": ["best", "who is playing", "standout", "mejor", "meilleur", "melhor", "أفضل", "man of the match", "potm"],
    "speed": ["fast", "fastest", "speed", "rapido", "rápido", "vitesse", "velocidade", "سرعة", "أسرع", "sprint"],
    "distance": ["distance", "ran", "running", "km", "distancia", "distância", "مسافة", "covered"],
}

A = {
    "status": {"en": "{clock}: {home} {hs}-{as_} {away}. Win probability: {home} {wph}%, draw {wpd}%, {away} {wpa}%.",
               "es": "{clock}: {home} {hs}-{as_} {away}. Probabilidad de victoria: {home} {wph}%, empate {wpd}%, {away} {wpa}%.",
               "fr": "{clock} : {home} {hs}-{as_} {away}. Probabilité de victoire : {home} {wph} %, nul {wpd} %, {away} {wpa} %.",
               "ar": "{clock}: {home} {hs}-{as_} {away}. احتمال الفوز: {home} {wph}%، التعادل {wpd}%، {away} {wpa}%.",
               "pt": "{clock}: {home} {hs}-{as_} {away}. Probabilidade de vitória: {home} {wph}%, empate {wpd}%, {away} {wpa}%."},
    "press": {"en": "{team} have {verb} their press since {since}: {nb} → {na} players near the ball in the opponent's build-up, defensive line {lb} m → {la} m.",
              "es": "{team} ha {verb} su presión desde el {since}: de {nb} a {na} jugadores cerca del balón en la salida rival, línea de {lb} m a {la} m.",
              "fr": "{team} a {verb} son pressing depuis la {since} : de {nb} à {na} joueurs près du ballon à la relance adverse, ligne de {lb} m à {la} m.",
              "ar": "{team} {verb} الضغط منذ الدقيقة {since}: من {nb} إلى {na} لاعبين قرب الكرة أثناء بناء الخصم، وخط الدفاع من {lb} م إلى {la} م.",
              "pt": "O {team} {verb} a pressão desde os {since}: de {nb} para {na} jogadores perto da bola na saída adversária, linha de {lb} m para {la} m."},
    "press_none": {"en": "No significant pressing change detected yet. Players near the ball in the opponent's build-up: {a} {an}, {b} {bn}.",
                   "es": "Aún no se detecta un cambio de presión. Jugadores cerca del balón en la salida rival: {a} {an}, {b} {bn}.",
                   "fr": "Pas de changement de pressing détecté. Joueurs près du ballon à la relance adverse : {a} {an}, {b} {bn}.",
                   "ar": "لم يُرصد تغيير واضح في الضغط بعد. اللاعبون قرب الكرة أثناء بناء الخصم: {a} {an}، {b} {bn}.",
                   "pt": "Nenhuma mudança de pressão detectada ainda. Jogadores perto da bola na saída adversária: {a} {an}, {b} {bn}."},
    "verb_up": {"en": "cranked up", "es": "intensificado", "fr": "intensifié", "ar": "رفع", "pt": "intensificou"},
    "verb_down": {"en": "dialled down", "es": "reducido", "fr": "relâché", "ar": "خفف", "pt": "reduziu"},
    "control": {"en": "Control index {index} ({label}). Possession in the last five minutes: {a} {pa}%, {b} {pb}%. Biggest driver: {f1}.",
                "es": "Índice de control {index} ({label}). Posesión en los últimos cinco minutos: {a} {pa}%, {b} {pb}%. Factor principal: {f1}.",
                "fr": "Indice de maîtrise {index} ({label}). Possession sur les cinq dernières minutes : {a} {pa} %, {b} {pb} %. Facteur principal : {f1}.",
                "ar": "مؤشر السيطرة {index} ({label}). الاستحواذ في آخر خمس دقائق: {a} {pa}%، {b} {pb}%. العامل الأبرز: {f1}.",
                "pt": "Índice de controle {index} ({label}). Posse nos últimos cinco minutos: {a} {pa}%, {b} {pb}%. Fator principal: {f1}."},
    "xg": {"en": "Chance quality so far: {a} {axg} xG from {as_} shots, {b} {bxg} xG from {bs} shots.",
           "es": "Calidad de ocasiones: {a} {axg} xG en {as_} tiros, {b} {bxg} xG en {bs} tiros.",
           "fr": "Qualité des occasions : {a} {axg} xG sur {as_} tirs, {b} {bxg} xG sur {bs} tirs.",
           "ar": "جودة الفرص حتى الآن: {a} {axg} xG من {as_} تسديدات، {b} {bxg} xG من {bs} تسديدات.",
           "pt": "Qualidade das chances: {a} {axg} xG em {as_} chutes, {b} {bxg} xG em {bs} chutes."},
    "best": {"en": "Top performer so far: {name} ({team}), rating {rating}: {detail}.",
             "es": "El mejor hasta ahora: {name} ({team}), nota {rating}: {detail}.",
             "fr": "Meilleur joueur jusqu'ici : {name} ({team}), note {rating} : {detail}.",
             "ar": "الأفضل حتى الآن: {name} ({team})، التقييم {rating}: {detail}.",
             "pt": "Melhor até agora: {name} ({team}), nota {rating}: {detail}."},
    "player": {"en": "{name}: rating {rating}, {passes} passes at {acc}%, {xg} xG, {dist} km covered, top speed {spd} km/h.",
               "es": "{name}: nota {rating}, {passes} pases con {acc}% de acierto, {xg} xG, {dist} km recorridos, velocidad máxima {spd} km/h.",
               "fr": "{name} : note {rating}, {passes} passes à {acc} %, {xg} xG, {dist} km parcourus, pointe à {spd} km/h.",
               "ar": "{name}: التقييم {rating}، {passes} تمريرة بدقة {acc}%، {xg} xG، {dist} كم مقطوعة، أقصى سرعة {spd} كم/س.",
               "pt": "{name}: nota {rating}, {passes} passes com {acc}% de acerto, {xg} xG, {dist} km percorridos, velocidade máxima {spd} km/h."},
    "speed": {"en": "Fastest so far: {name} at {spd} km/h ({sprints} sprints).",
              "es": "El más rápido: {name} a {spd} km/h ({sprints} sprints).",
              "fr": "Le plus rapide : {name} à {spd} km/h ({sprints} sprints).",
              "ar": "الأسرع حتى الآن: {name} بسرعة {spd} كم/س ({sprints} انطلاقات).",
              "pt": "O mais rápido: {name} a {spd} km/h ({sprints} sprints)."},
    "distance": {"en": "Most ground covered: {name} with {dist} km.",
                 "es": "Quien más ha corrido: {name}, con {dist} km.",
                 "fr": "Celui qui a le plus couru : {name}, avec {dist} km.",
                 "ar": "الأكثر جريا: {name} بمسافة {dist} كم.",
                 "pt": "Quem mais correu: {name}, com {dist} km."},
}
LABEL = {"control": {"en": "control", "es": "control", "fr": "maîtrise", "ar": "سيطرة", "pt": "controle"},
         "chaos": {"en": "chaos", "es": "caos", "fr": "chaos", "ar": "فوضى", "pt": "caos"},
         "balanced": {"en": "balanced", "es": "equilibrado", "fr": "équilibré", "ar": "متوازن", "pt": "equilibrado"}}


class Pundit:
    def __init__(self, rt: AgentRuntime, tools: MatchTools):
        self.rt = rt
        self.tools = tools
        self.agent = None if rt.cfg.is_offline else Agent(rt.client, prompts.PUNDIT, name="Pundit",
                                                         tools=tools.function_tools())

    async def ask(self, question: str, language: str = "en", persona: str = "casual") -> dict[str, Any]:
        t0 = time.perf_counter()
        if self.agent is not None and self.rt.breaker.allow():
            try:
                prompt = json.dumps({"question": question, "language": language, "style": persona}, ensure_ascii=False)
                res = await asyncio.wait_for(self.agent.run(prompt), timeout=self.rt.cfg.timeout_s * 2)
                calls = [c.name for m in res.messages for c in (m.contents or []) if getattr(c, "type", "") == "function_call"]
                ms = (time.perf_counter() - t0) * 1000
                self.rt.breaker.success()
                self.rt.telemetry.record(Span("Pundit", "ok", ms, self.rt.model_name, detail=f"tools: {', '.join(calls) or 'none'}"))
                return {"answer": res.text.strip(), "tools": calls, "model": self.rt.model_name, "ms": round(ms)}
            except Exception as exc:  # noqa: BLE001
                self.rt.breaker.failure()
                self.rt.telemetry.record(Span("Pundit", "error", (time.perf_counter() - t0) * 1000, self.rt.model_name,
                                              detail=str(exc)[:120]))
        answer, calls = self.offline_answer(question, language)
        ms = (time.perf_counter() - t0) * 1000
        self.rt.telemetry.record(Span("Pundit", "ok" if self.agent is None else "fallback", ms, "deterministic",
                                      detail=f"tools: {', '.join(calls)}"))
        return {"answer": answer, "tools": calls, "model": "deterministic", "ms": round(ms)}

    def offline_answer(self, question: str, lang: str) -> tuple[str, list[str]]:
        lang = lang if lang in A["status"] else "en"
        q = _norm(question)
        t = self.tools
        st = t.st
        a, b = st.home, st.away
        an, bn = st.short[a], st.short[b]
        players = t.mentioned_players(question)
        intents = [k for k, words in KEYWORDS.items() if any(_norm(w) in q for w in words)]  # dict order = priority
        if players and not intents:
            p = t.player_stats(players[0])
            return A["player"][lang].format(name=p["name"], rating=num(p["rating"], lang, 1), passes=p["passes"],
                                            acc=num(p["pass_accuracy"], lang), xg=num(p["xg"], lang, 2),
                                            dist=num(p["distance_km"], lang, 1), spd=num(p["top_speed_kmh"], lang, 1)), ["get_player_stats"]
        intent = intents[0] if intents else "status"
        if intent == "press":
            tp = t.tactical_picture()
            named = {st.names[tid] for tid in (a, b) if _norm(st.short[tid]) in q or _norm(st.names[tid]) in q}
            shifts = [x for x in tp["press_shifts"] if not named or x["team"] in named]
            if shifts:
                s = shifts[-1]
                return A["press"][lang].format(
                    team=s["team"], verb=A[f"verb_{s['direction']}"][lang], since=s["since"],
                    nb=num(s["players_near_ball"][0], lang, 1), na=num(s["players_near_ball"][1], lang, 1),
                    lb=num(s["line_height_m"][0], lang), la=num(s["line_height_m"][1], lang)), ["get_tactical_picture"]
            teams = tp["teams"]
            return A["press_none"][lang].format(
                a=an, b=bn, an=num(teams[st.names[a]]["players_near_ball_in_opponent_buildup"] or 0, lang, 1),
                bn=num(teams[st.names[b]]["players_near_ball_in_opponent_buildup"] or 0, lang, 1)), ["get_tactical_picture"]
        if intent == "control":
            cc = t.tactical_picture()["control_chaos"]
            f1 = cc["factors"][0] if cc["factors"] else {"label": "", "detail": ""}
            from .templates import FACTOR

            label = LABEL[cc["label"]][lang] + (f", {st.short[cc['controller']]}" if cc.get("controller") else "")
            return A["control"][lang].format(
                index=num(cc["index"], lang), label=label, a=an, b=bn,
                pa=num(cc["possession_share"][a], lang), pb=num(cc["possession_share"][b], lang),
                f1=f"{FACTOR.get(f1['label'], {}).get(lang, f1['label'])} {num(f1['value'] * (100 if f1['label'] == 'Pass completion' else 1), lang, 1)}"), ["get_tactical_picture"]
        if intent == "xg":
            ta, tb = t.team_stats(a), t.team_stats(b)
            return A["xg"][lang].format(a=an, b=bn, axg=num(ta["xg"], lang, 2), bxg=num(tb["xg"], lang, 2),
                                        as_=ta["shots"], bs=tb["shots"]), ["get_team_stats"]
        if intent in {"best", "speed", "distance"}:
            metric = {"best": "rating", "speed": "top_speed_kmh", "distance": "distance_km"}[intent]
            top = st.top_players(metric, 1)[0]
            if intent == "best":
                detail = f"{top['goals']}G {top['assists']}A, {num(top['xg'], lang, 2)} xG, {top['key_passes']} key passes"
                return A["best"][lang].format(name=top["name"], team=st.short[top["team"]], rating=num(top["rating"], lang, 1),
                                              detail=detail), ["get_top_players"]
            if intent == "speed":
                return A["speed"][lang].format(name=top["name"], spd=num(top["top_speed_kmh"], lang, 1),
                                               sprints=top["sprints"]), ["get_top_players"]
            return A["distance"][lang].format(name=top["name"], dist=num(top["distance_km"], lang, 1)), ["get_top_players"]
        ms = t.match_status()
        wp = ms["win_probability"]
        return A["status"][lang].format(clock=ms["clock"], home=an, away=bn, hs=ms["score"][a], as_=ms["score"][b],
                                        wph=round(100 * wp["home"]), wpd=round(100 * wp["draw"]),
                                        wpa=round(100 * wp["away"])), ["get_match_status"]
