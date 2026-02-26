"""Slugify text to URL-friendly strings.

Mirrors @sindresorhus/slugify with ``decamelize: false`` — identical logic to
the client-side ``slugify()`` in ``static/js/editor.js``.
"""

import re
import unicodedata

# Replacements applied before NFD diacritic stripping
# (mirrors @sindresorhus/transliterate)
_REPLACEMENTS = [
    ("&", " and "), ("\U0001f984", " unicorn "), ("\u2665", " love "),
    # German umlauts (must come before NFD which would strip to base letter)
    ("\u00e4", "ae"), ("\u00c4", "Ae"),
    ("\u00f6", "oe"), ("\u00d6", "Oe"),
    ("\u00fc", "ue"), ("\u00dc", "Ue"),
    ("\u00df", "ss"), ("\u1e9e", "Ss"),
    # Ligatures and special Latin
    ("\u00e6", "ae"), ("\u00c6", "AE"),
    ("\u0153", "oe"), ("\u0152", "OE"),
    ("\u00f8", "o"), ("\u00d8", "O"),
    ("\u0142", "l"), ("\u0141", "L"),
    ("\u00f0", "d"), ("\u00d0", "D"),
    ("\u00fe", "th"), ("\u00de", "TH"),
    ("\u0111", "d"), ("\u0110", "D"),
]

# Unicode category Dash_Punctuation (Pd)
_DASH_PUNCT_RE = re.compile(r"[\u002D\u058A\u05BE\u1400\u1806\u2010-\u2015"
                            r"\u2E17\u2E1A\u2E3A\u2E3B\u2E40\u301C\u3030"
                            r"\u30A0\uFE31\uFE32\uFE58\uFE63\uFF0D]")

# Contraction handling: 's → s, 't → t (straight and curly apostrophes)
_CONTRACTION_RE = re.compile(r"([a-z\d]+)['\u2019]([ts])(\s|$)")

_NON_ALNUM_RE = re.compile(r"[^a-z\d]+")
_LEADING_TRAILING_RE = re.compile(r"^-|-$")


def slugify(text):
    """Convert *text* to a URL-friendly slug.

    Matches the behavior of ``@sindresorhus/slugify`` with ``decamelize: false``
    and the client-side ``slugify()`` in ``static/js/editor.js``.

    Decamelization is intentionally disabled — stylized names like "fLaMEd",
    "CloudCannon", and "GoOz" should slugify as single words, not be split
    at case transitions.
    """
    # 1. Custom replacements (& → and, etc.)
    for old, new in _REPLACEMENTS:
        text = text.replace(old, new)

    # 2. Transliterate: NFD decompose, strip diacritics (Unicode Mn category)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = unicodedata.normalize("NFC", text)

    # Normalize dash punctuation to ASCII hyphen
    text = _DASH_PUNCT_RE.sub("-", text)

    # 3. Lowercase
    text = text.lower()

    # 4. Handle contractions
    text = _CONTRACTION_RE.sub(r"\1\2\3", text)

    # 5. Replace non-alphanumeric runs with separator
    text = _NON_ALNUM_RE.sub("-", text)

    # 6. Remove leading/trailing separators
    text = _LEADING_TRAILING_RE.sub("", text)

    return text
