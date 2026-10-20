"""The Verifier: nothing goes to air unless the numbers and names check out.

Evidence is deterministic only: the facts the Interpret stage computed, the match context, the moment's clock
and shirt numbers. Nothing a model produced (not even the Analyst's key numbers) counts as evidence.

What it checks, in every supported language:
- every figure (digits, ordinals, written-out numbers) traces back to a fact, within rounding;
- figures with a unit (km/h, metres, %, goals, players, per-minute rates, the match minute) match a fact of that kind,
  so a 33 km/h speed cannot support "33 goals" and a rate per 100 passes cannot be called "per minute";
- a goal count attached to the scorer ("Valdane has scored two goals", "his 2nd goal", "a brace") must equal the
  scorer's tally, and a team's manpower ("down to ten", "con diez") must equal the players it has left;
- roster players outside the moment are not named; selected football claims (header, penalty, free kick)
  agree with the facts; copy fits its on-screen slot; brand-safety rules hold.

What it does not check: invented names outside the roster, causal claims and tone. A goal count is bound to the
closest player named before it in the same sentence, so a pronoun in a later sentence ("He has two now") is checked
only against the match's goal figures, not the scorer's tally. Failures come back as
specific, actionable issues that the writer receives on its retry - that is the self-correcting loop.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

# digits, optionally with an ordinal suffix (2nd, 63rd, 2º, 63e, 2ème) so ordinals are checked too
NUM_RE = re.compile(r"(?<![\w])(\d{1,4}(?:[.,]\d{1,3})?)(?:st|nd|rd|th|º|ª|°|er|e|ème|eme)?(?![\w])")
_NUM = r"(\d{1,4}(?:[.,]\d{1,3})?)"

# A figure with a unit must match a fact of that kind: (pattern, fact-key hints, unit constants, description).
UNITS: dict[str, tuple[re.Pattern[str], tuple[str, ...], set[float], str]] = {
    "speed": (re.compile(_NUM + r"\s?(?:km/h|kph|km/hr|كم/س(?:اعة)?|كلم/س)", re.I), ("kmh", "speed"), {25.0, 33.0, 70.0},
              "a speed"),
    "distance": (re.compile(_NUM + r"\s?(?:m|metres?|meters?|metros?|mètres?|متر[اًا]?|أمتار)(?![\w/])", re.I),
                 ("_m", "distance", "length", "height", "_m."), {8.0}, "a distance"),
    "percent": (re.compile(_NUM + r"\s?(?:%|٪|per ?cent\b|por ciento|pour ?cent|por cento|بالمئة|بالمائة|في المئة|في المائة)", re.I),
                ("pct", "percent", "accuracy", "possession", "difficulty", "prob", "wp", "xg", "swing", "share", "conversion"),
                {0.0, 50.0, 76.0, 100.0}, "a percentage"),
    "goals": (re.compile(_NUM + r"(?:st|nd|rd|th|º|ª|e|ème|er)?\s?(?:goals?\b|goles?\b|gol\b|buts?\b|gols?\b|أهداف|اهداف|هدف)",
                         re.I),
              ("goals", "score"), {0.0, 1.0}, "a goal count"),
    "players": (re.compile(_NUM + r"\s?(?:-?man\b|men\b|players?\b|jugadores\b|hombres\b|joueurs\b|hommes\b|"
                           r"jogadores\b|homens\b|لاعبين|لاعبا|لاعب)"
                           r"|(?:down to|se queda con|se quedan con|réduits? à|fica com|ficam com)\s+(\d{1,2})(?!\d)", re.I),
                ("players_remaining", "players_on_pitch", "players_near", "bypassed"), {1.0, 2.0, 3.0},
                "a player count"),
    "rate": (re.compile(_NUM + r"\s?(?:[^\W\d]+\s){0,3}?(?:per minute|each minute|every minute|por minuto|par minute|"
                        r"à la minute|كل دقيقة|في الدقيقة الواحدة)", re.I),
             ("per_min",), set(), "a per-minute rate"),
    "minute": (re.compile(r"(?:minute|minuto|الدقيقة)\s+(\d{1,3})|(\d{1,3})(?:st|nd|rd|th|e|ème|º)?\s+(?:minute|minuto)\b"
                          r"|(\d{1,3})\s?['’′]", re.I),
               ("clock", "minute"), set(), "the match minute"),
}

# written-out numbers (4 and up; 0-3 are domain constants anyway), normalised to digits before checking
_WORDS: dict[str, dict[str, int]] = {
    "en": {"four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
           "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
           "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
           "hundred": 100},
    "es": {"cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
           "trece": 13, "catorce": 14, "quince": 15, "dieciséis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
           "veinte": 20, "veintiuno": 21, "veintidós": 22, "veintitrés": 23, "veinticuatro": 24, "veinticinco": 25,
           "veintiséis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "treinta": 30, "cuarenta": 40,
           "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100},
    "fr": {"quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
           "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16, "vingt": 20, "trente": 30, "quarante": 40,
           "cinquante": 50, "soixante": 60, "quatre-vingt": 80, "quatre-vingts": 80, "cent": 100},
    "pt": {"quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
           "treze": 13, "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
           "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80,
           "noventa": 90, "cem": 100},
    "ar": {"أربعة": 4, "خمسة": 5, "ستة": 6, "سبعة": 7, "ثمانية": 8, "تسعة": 9, "عشرة": 10, "عشرون": 20, "عشرين": 20,
           "ثلاثون": 30, "ثلاثين": 30, "أربعون": 40, "أربعين": 40, "خمسون": 50, "خمسين": 50, "ستون": 60, "ستين": 60,
           "سبعون": 70, "سبعين": 70, "ثمانون": 80, "ثمانين": 80, "تسعون": 90, "تسعين": 90, "مئة": 100, "مائة": 100},
}
_UNITS_WORDS = {"en": {"one": 1, "two": 2, "three": 3}, "es": {"uno": 1, "una": 1, "dos": 2, "tres": 3},
                "fr": {"un": 1, "une": 1, "deux": 2, "trois": 3}, "pt": {"um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3}}
# small counts written out ("two goals", "tres goles"): the ones that are never an article
_SMALL = {"en": {"one": 1, "two": 2, "three": 3}, "es": {"dos": 2, "tres": 3}, "fr": {"deux": 2, "trois": 3},
          "pt": {"dois": 2, "duas": 2, "três": 3}, "ar": {"اثنان": 2, "اثنين": 2, "ثلاثة": 3}}
# ordinals written out, rewritten with a digit and suffix so "his second goal" is checked like "his 2nd goal"
_ORDINALS = {
    "en": {"first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th", "fifth": "5th"},
    "es": {"primer": "1º", "primero": "1º", "primera": "1ª", "segundo": "2º", "segunda": "2ª", "tercer": "3º",
           "tercero": "3º", "tercera": "3ª", "cuarto": "4º", "cuarta": "4ª"},
    "fr": {"premier": "1er", "première": "1e", "deuxième": "2e", "second": "2e", "seconde": "2e", "troisième": "3e",
           "quatrième": "4e"},
    "pt": {"primeiro": "1º", "primeira": "1ª", "segundo": "2º", "segunda": "2ª", "terceiro": "3º", "terceira": "3ª",
           "quarto": "4º", "quarta": "4ª"},
}
_JOIN = r"(?:-|\s+y\s+|\s+e\s+|-et-|\s+et\s+|\s+)"


def _spell_out_digits(text: str, lang: str) -> str:
    """Rewrite written-out numbers as digits ("ninety-seven" -> "97", "two goals" -> "2 goals", "second" -> "2nd") so
    they get the same checks as digits. Arabic attaches prepositions to the word (بعشرة, "with ten"): they are kept,
    split off by a space, so the digit can still be read."""
    words = _WORDS.get(lang)
    if not words:
        return text
    if lang == "ar":
        units = {"واحد": 1, "اثنان": 2, "اثنين": 2, "ثلاث": 3, "ثلاثة": 3, "أربع": 4, "أربعة": 4, "خمس": 5, "خمسة": 5,
                 "ست": 6, "ستة": 6, "سبع": 7, "سبعة": 7, "ثماني": 8, "ثمانية": 8, "تسع": 9, "تسعة": 9}
        tens = {w: n for w, n in words.items() if 20 <= n < 100 and n % 10 == 0}
        text = re.sub(rf"(?<!\w)({'|'.join(sorted(units, key=len, reverse=True))})\s+و\s*"
                      rf"({'|'.join(sorted(tens, key=len, reverse=True))})(?!\w)",
                      lambda m: str(units[m.group(1)] + tens[m.group(2)]), text)
        every = {**words, **_SMALL["ar"]}
        alt = "|".join(map(re.escape, sorted(every, key=len, reverse=True)))
        return re.sub(rf"(?<!\w)([وبلف]?)({alt})(?!\w)", lambda m: (m.group(1) + " " if m.group(1) else "") +
                      str(every[m.group(2)]), text)
    ords = _ORDINALS.get(lang, {})
    if ords:
        text = re.sub(rf"(?<!\w)({'|'.join(map(re.escape, sorted(ords, key=len, reverse=True)))})(?!\w)",
                      lambda m: ords[m.group(1).lower()], text, flags=re.I)
    words = {**_SMALL.get(lang, {}), **words}
    small = {**_UNITS_WORDS.get(lang, {}), **{w: n for w, n in words.items() if n < 10}}
    tens = {w: n for w, n in words.items() if n >= 20 and n % 10 == 0 and n < 100}
    if tens and small:
        compound = re.compile(rf"(?<!\w)({'|'.join(map(re.escape, sorted(tens, key=len, reverse=True)))}){_JOIN}"
                              rf"({'|'.join(map(re.escape, sorted(small, key=len, reverse=True)))})(?!\w)", re.I)
        text = compound.sub(lambda m: str(tens[m.group(1).lower()] + small[m.group(2).lower()]), text)
    single = re.compile(rf"(?<!\w)({'|'.join(map(re.escape, sorted(words, key=len, reverse=True)))})(?!\w)", re.I)
    return single.sub(lambda m: str(words[m.group(1).lower()]), text)
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
    "brace": (r"\bbrace\b|doblete|\bdoubl[ée]\b|dobradinha|ثنائية",
              lambda f: "scorer_goals" in f and f.get("scorer_goals") != 2, "the scorer does not have two goals"),
    "hat_trick": (r"hat[- ]?trick|triplete|tripleta|\btripl[ée]\b|ثلاثية",
                  lambda f: "scorer_goals" in f and f.get("scorer_goals") != 3, "the scorer does not have three goals"),
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
    # domain constants a bare figure may use: football idiom (a back four or five, the six- and 18-yard boxes, the starting
    # eleven, 12 yards, 45 and 90 minutes) plus sprint threshold, elite speed, typical shot speed, penalty conversion.
    # Figures with a unit are held to their own, stricter sets (UNITS), so "the 90th minute" still needs the clock.
    out: set[float] = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 11.0, 12.0, 18.0, 25.0, 33.0, 45.0, 70.0, 76.0, 90.0,
                       100.0}
    pct_hints = UNITS["percent"][1]
    for src in sources:
        for path, v in _keyed(src):
            v = abs(v)  # signs are rendered as words ("down", "dropped"), digits are checked unsigned
            out.add(round(v, 2))
            out.add(round(v, 1))
            out.add(float(round(v)))
            if 0 < v <= 1:  # a probability or rate: as a percentage, its complement, or "1 in N"
                pct = v * 100
                out.update({round(pct, 1), float(round(pct)), float(round(1 / v)), float(round(100 - pct))})
            if 1 < v <= 100 and any(h in path for h in pct_hints):  # complements only make sense for percentages
                out.add(float(round(100 - v)))
    return out


def _keyed(v: Any, path: str = "") -> Iterable[tuple[str, float]]:
    """(dotted key path, number) pairs, so a figure can be matched to the kind of fact it came from."""
    if isinstance(v, bool) or v is None:
        return
    if isinstance(v, (int, float)):
        yield path, float(v)
    elif isinstance(v, str):
        p = path or ("clock" if re.fullmatch(r"\d{1,3}(\+\d{1,2})?['’′]", v.strip()) else "")
        for m in re.finditer(r"\d+(?:\.\d+)?", v):
            yield p, float(m.group())
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from _keyed(x, f"{path}.{k}".lower() if path else str(k).lower())
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _keyed(x, path)


def unit_numbers(*sources: Any) -> dict[str, set[float]]:
    """For each unit, the figures a writer may attach to it: facts of that kind plus their honest derived forms."""
    out = {unit: set(consts) for unit, (_, _, consts, _) in UNITS.items()}
    for path, v in (kv for src in sources for kv in _keyed(src)):
        v = abs(v)
        forms = {round(v, 2), round(v, 1), float(round(v))}
        for unit, (_, hints, _, _) in UNITS.items():
            if any(h in path for h in hints):
                out[unit].update(forms)
                if unit == "percent" and 1 < v <= 100:
                    out[unit].add(float(round(100 - v)))
        if 0 < v <= 1:  # probabilities and rates read as percentages
            pct = v * 100
            out["percent"].update({round(pct, 1), float(round(pct)), float(round(100 - pct))})
    goals = sorted(out["goals"])
    out["goals"].update({a + b for a in goals for b in goals} | {abs(a - b) for a in goals for b in goals})
    return out


def _bound_to(text: str, at: int, name: str, names: set[str]) -> bool:
    """Whether the figure at `at` belongs to `name`: that name is the closest player named before it in the same sentence."""
    before = re.split(r"[.!?;؟]", text[max(0, at - 90):at])[-1]
    best, where = "", -1
    for n in names:
        i = before.rfind(n)
        if i > where:
            best, where = n, i
    return best == name


# "No. 9" is a shirt number; a bare "no" is Portuguese for "in the" ("no minuto 45"), so the dot is required
_SHIRT_BEFORE = re.compile(r"(?:رقم|(?<!\w)no\.|#|número|numéro|nº|n°|numero)\s*$", re.I)


def _supported(n: float, allowed: set[float]) -> bool:
    for a in allowed:
        tol = 0.011  # rounded forms (2 dp, 1 dp, whole) are already in the set: no relative slack for large figures
        if abs(n - a) <= tol or (abs(a) >= 1 and float(n).is_integer() and abs(n - a) <= 0.5):  # 13.5 -> 13 or 14
            return True
    return False


def verify_texts(texts: dict[str, dict[str, dict[str, str]]], facts: list[Any], allowed_players: set[str],
                 roster_names: dict[str, str], claims: dict[str, Any] | None = None) -> Verdict:
    """texts: {lang: {persona: {caption, line, explainer}}}."""
    allowed = allowed_numbers(*facts)
    units = unit_numbers(*facts)
    allowed_names = {roster_names[p] for p in allowed_players if p in roster_names}
    # the scorer's tally, so "Valdane has scored 2 goals" is held to Valdane's goals, not to any goal figure in the match
    scorer = (claims or {}).get("scorer")
    tally = (claims or {}).get("scorer_goals")
    scorer_name = roster_names.get(scorer, "") if isinstance(scorer, str) else ""
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
                norm = _spell_out_digits(text, lang)
                for m in NUM_RE.finditer(norm):
                    raw = m.group(1).replace(",", ".")
                    try:
                        n = float(raw)
                    except ValueError:
                        continue
                    v.numbers_checked += 1
                    if _supported(n, allowed):
                        v.numbers_supported += 1
                    else:
                        v.issues.append(f"{where} number {m.group(1)} is not supported by the facts - remove it, or use only FIGURES")
                        failed.add(lang)
                for unit, (pattern, _, _, what) in UNITS.items():
                    for m in pattern.finditer(norm):
                        if _SHIRT_BEFORE.search(norm[max(0, m.start() - 9):m.start()]):
                            continue  # "No. 9" is a shirt number, not a figure of this kind
                        raw = next(g for g in m.groups() if g)
                        n = float(raw.replace(",", "."))
                        if unit == "goals" and tally is not None and scorer_name and _bound_to(norm, m.start(), scorer_name,
                                                                                               allowed_names):
                            if n != float(tally):
                                v.issues.append(f"{where} '{m.group(0).strip()}' does not match {scorer_name}'s goals in "
                                                f"this match ({tally}) - use the scorer's tally")
                                failed.add(lang)
                            continue
                        if not _supported(n, units[unit]):
                            v.issues.append(f"{where} '{m.group(0).strip()}' does not match {what} in the facts - "
                                            f"remove it, or use the FIGURES value for that metric")
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
