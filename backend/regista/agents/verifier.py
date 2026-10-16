"""The Verifier: nothing goes to air unless the numbers and names check out.

Every figure in generated copy must trace back to a fact the Interpret stage
computed (within rounding), every player named must belong to the moment or
the insight, copy must fit the on-screen slot, and brand-safety rules must
hold. Failures come back as specific, actionable issues that the Narrator
receives on its retry - that is the self-correcting loop.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

NUM_RE = re.compile(r"(?<![\w])(\d{1,4}(?:[.,]\d{1,2})?)(?![\w])")
LIMITS = {"caption": 52, "line": 230, "explainer": 380}
BLOCKLIST = {
    "bet", "bets", "betting", "bookmaker", "bookie", "wager", "casino", "gamble", "gambling", "beer", "alcohol",
    "apuesta", "apuestas", "cerveza", "pari", "paris sportifs", "bière", "aposta", "apostas", "cerveja", "مراهنة", "رهان", "كحول",
}


# Football claims a writer may only make when the facts back them (en, es, fr, ar, pt).
CLAIMS: dict[str, tuple[str, Any, str]] = {
    "header": (r"\bheader\b|\bheaded\b|\b(nods?|heads?) (it )?(in|home)\b|cabezazo|de cabeza|\bt[êe]te\b|رأسية|بالرأس|cabe[çc]ada|de cabe[çc]a",
               lambda f: "body_part" in f and f.get("body_part") != "head", "the shot was not a header"),
    "penalty": (r"\bpenalty\b(?! (area|box))|\bspot[- ]kick|\bpenalti\b|p[êe]nalti|ركلة جزاء|ضربة جزاء",
                lambda f: "set_piece" in f and f.get("set_piece") != "penalty", "it was not a penalty"),
    "free_kick": (r"free[- ]kick|tiro libre|coup franc|ركلة حرة|cobran[çc]a de falta",
                  lambda f: "set_piece" in f and f.get("set_piece") != "direct_free_kick", "it was not a direct free kick"),
}


@dataclass
class Verdict:
    ok: bool
    issues: list[str] = field(default_factory=list)
    numbers_checked: int = 0
    numbers_supported: int = 0
    names_checked: int = 0
    failed_langs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "issues": self.issues[:8], "numbers_checked": self.numbers_checked,
                "numbers_supported": self.numbers_supported, "names_checked": self.names_checked,
                "failed_langs": self.failed_langs}


def _walk(v: Any) -> Iterable[float]:
    if isinstance(v, bool):
        return
    if isinstance(v, (int, float)):
        yield float(v)
    elif isinstance(v, str):
        for m in re.finditer(r"\d+(?:\.\d+)?", v):
            yield float(m.group())
    elif isinstance(v, dict):
        for x in v.values():
            yield from _walk(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _walk(x)


def allowed_numbers(*sources: Any) -> set[float]:
    """All figures a writer may use: the facts, plus their honest derived forms."""
    # domain constants the copy may cite: sprint threshold, elite speed, typical shot speeds, penalty conversion
    out: set[float] = {0.0, 1.0, 2.0, 3.0, 8.0, 10.0, 25.0, 33.0, 70.0, 76.0, 100.0}
    for src in sources:
        for v in _walk(src):
            v = abs(v)  # signs are rendered as words ("down", "dropped"), digits are checked unsigned
            out.add(round(v, 2))
            out.add(round(v, 1))
            out.add(float(round(v)))
            if 0 < v <= 1:
                pct = v * 100
                out.update({round(pct, 1), float(round(pct)), float(round(1 / v)), float(round(100 - pct))})
            if 1 < v <= 100:
                out.add(float(round(100 - v)))
    return out


def _supported(n: float, allowed: set[float]) -> bool:
    for a in allowed:
        tol = max(0.011, 0.015 * abs(a))
        if abs(n - a) <= tol or (abs(a) >= 1 and abs(n - round(a)) < 0.51 and float(n).is_integer()):
            return True
    return False


def verify_texts(texts: dict[str, dict[str, dict[str, str]]], facts: list[Any], allowed_players: set[str],
                 roster_names: dict[str, str], claims: dict[str, Any] | None = None) -> Verdict:
    """texts: {lang: {persona: {caption, line, explainer}}}."""
    allowed = allowed_numbers(*facts)
    allowed_names = {roster_names[p] for p in allowed_players if p in roster_names}
    other_names = {n for pid, n in roster_names.items() if pid not in allowed_players and len(n) > 3}
    v = Verdict(ok=True)
    failed: set[str] = set()
    for lang, personas in texts.items():
        if not isinstance(personas, dict):
            v.issues.append(f"[{lang}] malformed output")
            failed.add(lang)
            continue
        for persona, fields in personas.items():
            if not isinstance(fields, dict):
                v.issues.append(f"[{lang}/{persona}] malformed output")
                failed.add(lang)
                continue
            for key, text in fields.items():
                if not isinstance(text, str):
                    continue
                where = f"[{lang}/{persona}/{key}]"
                lim = LIMITS.get(key)
                if lim and len(text) > lim:
                    v.issues.append(f"{where} too long ({len(text)} > {lim} chars) - shorten it")
                    failed.add(lang)
                low = text.lower()
                for pattern, contradicts, why in CLAIMS.values():
                    if claims is not None and contradicts(claims) and re.search(pattern, low):
                        v.issues.append(f"{where} makes a claim the facts contradict: {why} - describe it accurately")
                        failed.add(lang)
                for bad in BLOCKLIST:
                    if re.search(rf"(?<!\w){re.escape(bad)}(?!\w)", low):
                        v.issues.append(f"{where} brand-safety: remove '{bad}'")
                        failed.add(lang)
                for m in NUM_RE.finditer(text):
                    raw = m.group(1).replace(",", ".")
                    try:
                        n = float(raw)
                    except ValueError:
                        continue
                    v.numbers_checked += 1
                    if _supported(n, allowed):
                        v.numbers_supported += 1
                    else:
                        v.issues.append(f"{where} number {m.group(1)} is not supported by the facts - use only provided figures")
                        failed.add(lang)
                for name in other_names:
                    if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text):
                        v.names_checked += 1
                        v.issues.append(f"{where} mentions {name}, who is not part of this moment")
                        failed.add(lang)
                for name in allowed_names:
                    if name in text:
                        v.names_checked += 1
    v.failed_langs = sorted(failed)
    v.ok = not failed
    return v
