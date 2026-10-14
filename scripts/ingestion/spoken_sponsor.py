"""Find sponsors that are SPOKEN in a video, from its captions (Hindi, Hinglish or English).

Many creators write nothing in the description and say "yeh video X ke sponsor se hai, code Y use karo" out loud. YouTube's
auto-captions turn that into Devanagari or Roman text, brand names included (Wellcore becomes वेलकोर or "Velco"), so the
detector looks for:
  * a code / discount / sponsor phrase (Hindi and English), and
  * a known brand written in any of its Roman or Devanagari spellings within SPOKEN_WINDOW characters of it.
A brand with a code phrase nearby gives the evidence string 'spoken:brand:NAME(code)'; an explicit sponsor phrase alone gives
'spoken:disclosure:<phrase>'. Evidence type 'spoken' (see sponsorship_evidence_of in the migration 20261014000000).

Captions are fetched with the youtube-transcript-api package (no browser, no API quota). They are auto-generated, so this
is a best-effort signal: it misses what the speech recogniser garbles.
"""

import re

SPOKEN_WINDOW = 220

CODE_PHRASES = re.compile(
    r"(use\s+(my\s+|the\s+)?code|discount\s+code|promo\s*code|coupon|code\s+(lagao|use|daal)|link\s+(is\s+)?(in|below)|"
    r"कोड|डिस्काउंट|डिसकाउंट|कूपन|प्रोमो|लिंक\s+(नीचे|डिस्क्रिप्शन)|डिस्क्रिप्शन\s+(में|मे))", re.I)
SPONSOR_PHRASES = re.compile(
    r"(sponsor(ed|ship)?|brought\s+to\s+you\s+by|paid\s+(promotion|partnership|collab\w*)|in\s+collaboration\s+with|"
    r"स्पॉन्सर|स्पोंसर|स्पांसर|स्पॉन्सरशिप|प्रमोशन|प्रोमोशन|पेड\s+(प्रमोशन|पार्टनरशिप))", re.I)

# brand -> spellings as they come out of speech recognition (Roman and Devanagari)
BRAND_SPOKEN = {
    "MuscleBlaze": ["muscleblaze", "muscle blaze", "मसलब्लेज", "मसल ब्लेज", "मसल्ब्लेज", "मस्कल ब्लेज", "मसलब्लेस"],
    "Wellcore": ["wellcore", "well core", "velco", "वेलकोर", "वेल कोर", "वेलको"],
    "Wellversed": ["wellversed", "well versed", "वेलवर्स्ड", "वेल वर्स्ड"],
    "Nutrabay": ["nutrabay", "nutra bay", "न्यूट्राबे", "न्यूट्रा बे", "न्यूट्राबै"],
    "NaturalTein": ["naturaltein", "natural tein", "natural teen", "नेचुरल टीन", "नैचुरल टीन", "नेचुरलटीन"],
    "Avvatar": ["avvatar", "avatar", "अवतार", "एवतार"],
    "FuelOne": ["fuelone", "fuel one", "फ्यूल वन", "फ्यूलवन", "फ्यूएल वन"],
    "Boldfit": ["boldfit", "bold fit", "बोल्डफिट", "बोल्ड फिट"],
    "HealthKart": ["healthkart", "health kart", "हेल्थकार्ट", "हेल्थ कार्ट"],
    "GNC": ["gnc", "जीएनसी"],
    "Myprotein": ["myprotein", "my protein", "माय प्रोटीन"],
    "AsItIs Nutrition": ["asitis", "as it is", "एज़ इट इज़", "एज इट इज"],
    "Ripped Up Nutrition": ["ripped up", "rippedup", "रिप्ड अप", "रिप्ट अप"],
    "Red Skull Nutrition": ["red skull", "redskull", "रेड स्कल"],
    "Black Beast Nutrition": ["black beast", "blackbeast", "ब्लैक बीस्ट"],
    "QNT": ["qnt", "क्यूएनटी"],
    "Dynamite": ["dynamite", "डायनामाइट"],
    "Nakpro": ["nakpro", "नाकप्रो"],
    "Gayor Essentials": ["gayor", "गायोर"],
    "Fast&Up": ["fast and up", "fast & up", "फास्ट एंड अप"],
}
_BRAND_PATTERNS = {n: [re.compile(re.escape(s), re.I) for s in spellings] for n, spellings in BRAND_SPOKEN.items()}


def spoken_evidence(transcript: str | None) -> list[str]:
    """Evidence strings found in a transcript: ['spoken:brand:NAME(code)', 'spoken:disclosure:<phrase>']."""
    text = re.sub(r"\s+", " ", transcript or "")
    if not text:
        return []
    out: list[str] = []
    for name, patterns in _BRAND_PATTERNS.items():
        for pat in patterns:
            hit = None
            for m in pat.finditer(text):
                window = text[max(0, m.start() - SPOKEN_WINDOW): m.end() + SPOKEN_WINDOW]
                if CODE_PHRASES.search(window) or SPONSOR_PHRASES.search(window):
                    hit = m
                    break
            if hit:
                out.append(f"spoken:brand:{name}(code)")
                break
    m = SPONSOR_PHRASES.search(text)
    if m:
        out.append(f"spoken:disclosure:{m.group(0).lower()}")
    return out


def fetch_transcript(video_id: str, languages=("hi", "en")) -> str | None:
    """The video's captions as one string (auto-generated ones included), or None when there are none."""
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        listing = YouTubeTranscriptApi().list(video_id)
        try:
            transcript = listing.find_transcript(list(languages))
        except Exception:
            transcript = next(iter(listing))
        return " ".join(s.text for s in transcript.fetch())
    except Exception:
        return None
