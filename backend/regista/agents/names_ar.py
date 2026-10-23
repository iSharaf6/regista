"""One official Arabic spelling for every club and player in the synthetic league.

Arabic broadcasts write names in Arabic script, but a model left to transliterate invents its own spellings (one wrote
Port Calder as "بورتموند كالدير"), and nothing could check them. Here every name has exactly one spelling: the
templates use it, the Arabic writers are given it, the Verifier rejects near-misses of it, and any Latin name left in
Arabic copy is rewritten to it before display.
"""

from __future__ import annotations

import re

from ..sim.squads import TEAMS

CLUBS = {
    "Northbridge Rovers": "نورثبريدج روفرز", "Northbridge": "نورثبريدج",
    "Port Calder FC": "بورت كالدر", "Port Calder": "بورت كالدر",
    "Ashvale Town": "آشفيل تاون", "Ashvale": "آشفيل",
    "Kestrel City": "كيستريل سيتي", "Kestrel": "كيستريل",
}

SURNAMES = {
    # Northbridge Rovers
    "Lindqvist": "ليندكفيست", "Okafor": "أوكافور", "Fontes": "فونتيس", "Reid": "ريد", "Benali": "بن علي",
    "Haddad": "حداد", "Marchetti": "ماركيتي", "Arata": "أراتا", "Salvatierra": "سالفاتييرا", "Valdane": "فالدان",
    "Brightwell": "برايتويل", "de Waal": "دي فال", "Wren": "رين", "Nkosi": "نكوسي", "Diarra": "ديارا", "Varga": "فارغا",
    # Port Calder FC
    "Brandt": "برانت", "Ade": "آدي", "Kral": "كرال", "Erdem": "أردم", "Carrow": "كارو", "Iturra": "إيتورا",
    "Osei": "أوسي", "Seo": "سيو", "Quintero": "كينتيرو", "Morel": "موريل", "Pellegrini": "بيليغريني", "Hale": "هيل",
    "Asante": "أسانتي", "Ekdahl": "إكدال", "Lacombe": "لاكومب", "Mehta": "ميهتا",
    # Ashvale Town
    "Moffat": "موفات", "Brooks": "بروكس", "Ricci": "ريتشي", "Adeyemi": "أديمي", "Ferreira": "فيريرا",
    "Idrissi": "الإدريسي", "Albrecht": "ألبريشت", "Rivera": "ريفيرا", "Tanaka": "تاناكا", "Doyle": "دويل",
    "Ogun": "أوغون", "Larsen": "لارسن", "Ortega": "أورتيغا", "Novak": "نوفاك", "Mitchell": "ميتشل", "Bonsu": "بونسو",
    # Kestrel City
    "Castillo": "كاستيو", "Visser": "فيسر", "Keita": "كيتا", "Dahl": "دال", "Lima": "ليما", "Sokolenko": "سوكولينكو",
    "Pembroke": "بيمبروك", "Vidal": "فيدال", "Mansour": "منصور", "Bianchi": "بيانكي", "Hassan": "حسن",
    "Whitlock": "ويتلوك", "Obi": "أوبي", "Lund": "لوند", "Herrera": "هيريرا", "Lahti": "لاهتي",
}

FIRST_NAMES = {
    "Mats": "ماتس", "Jayden": "جايدن", "Rui": "روي", "Callum": "كالوم", "Idris": "إدريس", "Sami": "سامي", "Leo": "ليو",
    "Kenji": "كينجي", "Diego": "دييغو", "Teo": "تيو", "Noah": "نوح", "Pieter": "بيتر", "Oskar": "أوسكار",
    "Thabo": "تابو", "Malik": "مالك", "Elias": "إلياس", "Ivo": "إيفو", "Marcus": "ماركوس", "Tomas": "توماس",
    "Yusuf": "يوسف", "Liam": "ليام", "Ander": "أندير", "Felix": "فيليكس", "Min-jun": "مين جون", "Rafael": "رافائيل",
    "Bastien": "باستيان", "Dario": "داريو", "Owen": "أوين", "Kwame": "كوامي", "Nils": "نيلس", "Hugo": "هوغو",
    "Arjun": "أرجون", "Grant": "غرانت", "Elijah": "إيلايجا", "Matteo": "ماتيو", "Samuel": "صامويل", "Lucas": "لوكاس",
    "Hamza": "حمزة", "Jonas": "يوناس", "Tomás": "توماس", "Ryo": "ريو", "Kieran": "كيران", "Ade": "آدي", "Finn": "فين",
    "Pablo": "بابلو", "Dominik": "دومينيك", "Zane": "زين", "Yannick": "يانيك", "Andre": "أندريه", "Bram": "برام",
    "Oumar": "عمر", "Henrik": "هنريك", "Mateus": "ماتيوس", "Ilya": "إيليا", "Charlie": "تشارلي", "Sergio": "سيرخيو",
    "Karim": "كريم", "Luca": "لوكا", "Tariq": "طارق", "Joe": "جو", "Emeka": "إيميكا", "Viktor": "فيكتور", "Nico": "نيكو",
}


def _build() -> dict[str, str]:
    table = dict(CLUBS)
    for make in TEAMS.values():
        for p in make().players:
            table[p.short_name] = SURNAMES[p.short_name]
            first = p.name[: -len(p.short_name)].strip() if p.name.endswith(p.short_name) else p.name.split(" ", 1)[0]
            table[p.name] = f"{FIRST_NAMES[first]} {SURNAMES[p.short_name]}" if first else SURNAMES[p.short_name]
    return table


AR: dict[str, str] = _build()
_LATIN = re.compile("|".join(rf"(?<![A-Za-zÀ-ÿ]){re.escape(n)}(?![A-Za-zÀ-ÿ])"
                             for n in sorted(AR, key=len, reverse=True)))


def ar_name(name: str) -> str:
    """The official Arabic spelling of a club or player name (unchanged if it is not in the league)."""
    return AR.get(name, name)


def arabize(text: str) -> str:
    """Rewrite any club or player name left in Latin script inside Arabic copy to its official Arabic spelling."""
    return _LATIN.sub(lambda m: AR[m.group(0)], text) if isinstance(text, str) else text


# ---------------------------------------------------------------------------------------------- spelling check
_TASHKEEL = re.compile("[ً-ْٰـ]")
_PROCLITICS = ("وال", "بال", "فال", "كال", "لل", "ال", "و", "ف", "ب", "ل", "ك")


def _norm(word: str) -> str:
    w = _TASHKEEL.sub("", word)
    return w.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}))


def _variants(word: str) -> set[str]:
    """A word and the forms it takes with Arabic's attached prefixes removed (و, ب, ل, ال ...)."""
    out = {word}
    for p in _PROCLITICS:
        if word.startswith(p) and len(word) - len(p) >= 3:
            out.add(word[len(p):])
    return out


def _distance(a: str, b: str, limit: int) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# official name words long enough to tell a misspelling from an ordinary word (short ones like "ريد" or "حسن" are
# everyday Arabic words and are left alone)
_OFFICIAL = {_norm(w) for name in AR.values() for w in name.split() if len(_norm(w)) >= 5}
_ARABIC_WORD = re.compile(r"[ء-يٰ]+")


def misspelled_names(text: str) -> list[tuple[str, str]]:
    """(written, official) for words that are near-misses of an official name word but not that spelling."""
    found: list[tuple[str, str]] = []
    for raw in _ARABIC_WORD.findall(text or ""):
        whole = _norm(raw)
        variants = [whole] + sorted({_norm(v) for v in _variants(raw)} - {whole}, key=len, reverse=True)
        if set(variants) & _OFFICIAL:
            continue
        best: tuple[int, int, str] | None = None  # (distance, variant rank, official): the word as written wins ties
        for rank, v in enumerate(variants):
            if len(v) < 5:
                continue
            limit = 1 if len(v) <= 6 else 2
            for o in _OFFICIAL:
                d = _distance(v, o, limit)
                if d <= limit and (best is None or (d, rank) < best[:2]):
                    best = (d, rank, o)
        if best:
            official = next(w for name in AR.values() for w in name.split() if _norm(w) == best[2])
            found.append((raw, official))
    return found
