"""Known fitness, supplement, footwear and sportswear brands, and a matcher that ties a caption,
bio or video description to one of them.

WHY: brand_extraction.py only recognises phrases like "in partnership with X" or "#ad @x". Indian
fitness promotion looks different: "⛽ @fuelone.in @muscleblaze code ABHI30" or "Supps @naturaltein_india:
Code 'HYPER'". Without a brand list those posts are flagged sponsored but never get a brand_id, so the
creator-to-brand mapping GAIL needs stays empty.

A match is STRONG (safe to set a brand_id) only with real evidence:
  - an @handle mention of the brand, or
  - the brand's name together with a discount code / coupon / disclosure tag close by.
A bare mention of a name ("I like my Puma shoes") is WEAK and never sets a brand_id. Brands whose name
is an ordinary word (Campus, Dynamite) need an @handle mention or a code next to the name.

This module only says "this text promotes this brand". It does NOT decide `is_sponsored`; that label
stays with Track C, as in brand_extraction.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# (canonical name, category, instagram handle or None, extra aliases, name_is_common_word)
# Handles are included only where they were seen on a real profile or post; None means "match by
# name only, with a code or disclosure beside it".
KNOWN_BRANDS: list[tuple[str, str, str | None, tuple[str, ...], bool]] = [
    ("MuscleBlaze", "supplement", "muscleblaze", ("muscle blaze",), False),
    ("HealthKart", "supplement", None, ("health kart",), False),
    ("HK Vitals", "supplement", None, ("hk vitals", "hkvitals"), False),
    ("Myprotein", "supplement", "myproteinin", (), False),
    ("Wellcore", "supplement", "wellcore.in", (), False),
    ("NaturalTein", "supplement", "naturaltein_india", ("natural tein",), False),
    ("Avvatar", "supplement", "avvatarindia", (), False),
    ("Boldfit", "supplement", "boldfit_official", (), False),
    ("Nutrabay", "supplement", "nutrabay", (), False),
    ("AsItIs Nutrition", "supplement", None, ("asitis", "as it is nutrition", "asitisnutrition"), False),
    ("FuelOne", "supplement", "fuelone.in", ("fuel one", "fuleone"), False),
    ("Wellversed", "supplement", "wellversed.in", (), False),
    ("Black Beast Nutrition", "supplement", "blackbeast.nutrition", ("black beast", "blackbeast"), False),
    ("Dynamite", "supplement", "dynamite.preworkout", ("dynamite preworkout", "dynamite pre workout"), True),
    ("YouWeFit", "supplement", "youwefitofficial", ("you we fit",), False),
    ("QNT", "supplement", "qnt.india", ("qnt india",), False),
    ("2XN", "supplement", None, ("2xn", "2x nutrition"), False),
    ("Red Skull Nutrition", "supplement", None, ("red skull", "redskull", "redskullnutrition", "redskullnutrition1", "carnivox"), False),
    ("DrChoice", "supplement", "thedrchoice", ("dr choice", "dr. choice"), False),
    ("GNC", "supplement", None, (), False),
    ("optimumnutri", "supplement", "optimumnutri", ("optimum nutrition",), False),  # existing brands row keeps this name
    ("Rasayanam", "wellness", "rasayanam", (), False),
    ("BeWellness", "wellness", "bewellnessindia", ("be wellness",), False),
    ("Fast&Up", "supplement", "fastandup_india", ("fast and up", "fastandup"), False),
    ("Grind Gear", "equipment", "grindgear_powerlifting", ("grindgear",), False),
    ("Fuaark", "apparel", "fuaarkofficial", (), False),
    ("Layerzz", "apparel", "layerzzindia", (), False),
    ("Young LA", "apparel", "youngla", ("youngla",), False),
    ("Gymshark", "apparel", "gymshark", (), False),
    ("HRX", "apparel", None, (), False),
    ("Puma", "footwear", "pumaindia", ("puma india",), False),
    ("Nike", "footwear", "nike", (), False),
    ("Adidas", "footwear", "adidas", (), False),
    ("Skechers", "footwear", "skechers", (), False),
    ("Asics", "footwear", "asics", (), False),
    ("Reebok", "footwear", "reebok", (), False),
    ("Campus", "footwear", None, ("campus shoes",), True),
    ("Decathlon", "equipment", None, (), False),
    # Added 2026-10-12 after reading the saved YouTube descriptions (Desi Gym Reviews, Fit Adess, Harsh Katkade ...).
    ("Nakpro", "supplement", None, (), False),
    ("Cult.fit", "equipment", "cultstoreindia", ("cultstore", "cultsport", "cult sport", "cult.fit", "cult fit"), False),
    ("Slovic", "equipment", None, (), False),
    ("Aceblend", "supplement", "aceblend", (), False),
    ("HyugaLife", "supplement", "thehyugalife", ("the hyuga life", "hyuga life"), False),
    ("Pintola", "food", None, (), False),
    ("MyFitness", "food", None, ("my fitness peanut butter",), False),
    ("Kapiva", "wellness", None, (), False),
    ("Yogabar", "food", None, ("yoga bar",), False),
    ("MuscleTech", "supplement", None, ("muscle tech",), False),
    ("Dymatize", "supplement", None, (), False),
    ("BigMuscles Nutrition", "supplement", None, ("big muscles nutrition", "bigmuscles", "bigmusclesnutrition"), False),
    ("Under Armour", "apparel", None, ("underarmour",), False),
    ("Oakley", "apparel", None, (), False),
    ("Lifelong", "equipment", None, (), True),
    ("Mille Supergrain", "food", "millesupergrain", ("mille supergrain", "mille"), True),
    ("Mylo", "wellness", "mylo.in", ("mylo app",), False),
    ("Lifespan", "wellness", None, (), True),
    ("TrueForma", "supplement", "trueforma.nutrition", ("true forma", "trueforma nutrition"), False),
    ("Gayor Essentials", "supplement", None, ("gayor",), False),
    ("Anecdote", "supplement", None, (), True),
    ("Alpino", "food", None, (), False),
    ("Ripped Up Nutrition", "supplement", None, ("ripped up supplements", "ripped up", "rippedupnutrition"), False),
]

_CODE = re.compile(r"(use\s+code|promo\s*code|coupon|discount|%\s*off|\bcode\b\s*[:\-–—=]?\s*[\"“'‘]?[A-Za-z0-9]{3,})", re.I)
_DISCLOSURE = re.compile(r"(#\s*ad\b|#\s*sponsored|#\s*paidpartnership|paid\s+partnership|in\s+collaboration\s+with|partnered\s+with|brand\s+ambassador)", re.I)
_MENTION = re.compile(r"@([A-Za-z0-9_.]+)")
_WINDOW = 120  # characters either side of a brand name in which a code or disclosure counts


@dataclass
class BrandMatch:
    name: str
    category: str
    signals: list[str] = field(default_factory=list)  # 'mention', 'name', 'code', 'disclosure'

    @property
    def strong(self) -> bool:
        return "mention" in self.signals or ("name" in self.signals and ("code" in self.signals or "disclosure" in self.signals))


def _alias_pattern(alias: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", re.I)


_COMPILED = [
    (name, cat, (handle or "").lower() or None, [_alias_pattern(a) for a in (name.lower(), *aliases)], common)
    for name, cat, handle, aliases, common in KNOWN_BRANDS
]


def match_known_brands(text: str | None) -> list[BrandMatch]:
    """Every known brand that appears in the text, with the evidence found for each."""
    if not text:
        return []
    mentions = {m.group(1).lower().rstrip(".") for m in _MENTION.finditer(text)}
    out: list[BrandMatch] = []
    for name, cat, handle, patterns, common_word in _COMPILED:
        signals: list[str] = []
        if handle and handle.rstrip(".") in mentions:
            signals.append("mention")
        for p in patterns:
            for m in p.finditer(text):
                # an '@name' of the brand itself is a mention (even when no handle is saved for it); the alias
                # pattern already stops at a word edge, so '@nikefootball' does not count as '@nike'
                if text[max(0, m.start() - 1):m.start()] == "@":
                    if "mention" not in signals:
                        signals.append("mention")
                    continue
                window = text[max(0, m.start() - _WINDOW): m.end() + _WINDOW]
                if "name" not in signals:
                    signals.append("name")
                if _CODE.search(window) and "code" not in signals:
                    signals.append("code")
                if _DISCLOSURE.search(window) and "disclosure" not in signals:
                    signals.append("disclosure")
        if "mention" in signals and _CODE.search(text) and "code" not in signals:
            signals.append("code")
        if not signals:
            continue
        # an ordinary-word brand name counts only with an @mention, or a code right beside the name
        if common_word and "mention" not in signals and "code" not in signals:
            continue
        out.append(BrandMatch(name, cat, signals))
    return out


def all_strong_brands(text: str | None) -> list[BrandMatch]:
    """Every brand the text clearly promotes (a description often lists several), best evidence first."""
    strong = [m for m in match_known_brands(text) if m.strong]
    strong.sort(key=lambda m: ("mention" not in m.signals, -len(m.signals)))
    return strong


def best_brand_for_text(text: str | None) -> BrandMatch | None:
    """The strongest brand the text clearly promotes, or None. Weak, name-only hits return None."""
    strong = [m for m in match_known_brands(text) if m.strong]
    if not strong:
        return None
    # prefer an @mention, then the most signals, then the earliest listed
    strong.sort(key=lambda m: ("mention" not in m.signals, -len(m.signals)))
    return strong[0]
