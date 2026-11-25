"""Font loading and QFont helpers.

Fonts live in the repository ``font/`` folder:
- Plus Jakarta Sans for body text
- Bricolage Grotesque for titles and numbers

Some static TTFs register as separate families (for example
"Plus Jakarta Sans SemiBold"), so we remember the family name Qt reports for
each weight and build fonts from that mapping.
"""

import os

from PyQt6.QtGui import QFont, QFontDatabase

from .tokens import TextStyle

_FONT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "font")
)

_FILES = {
    "body": {
        400: "PlusJakartaSans-Regular.ttf",
        500: "PlusJakartaSans-Medium.ttf",
        600: "PlusJakartaSans-SemiBold.ttf",
        700: "PlusJakartaSans-Bold.ttf",
    },
    "display": {
        600: "BricolageGrotesque-SemiBold.ttf",
        700: "BricolageGrotesque-Bold.ttf",
    },
}

_FALLBACK = {"body": "Segoe UI", "display": "Segoe UI"}

# (role, weight) -> family name reported by Qt
_families: dict = {}


def load_fonts() -> bool:
    """Register bundled fonts. Call once after QApplication is created."""
    ok = True
    for role, weights in _FILES.items():
        for weight, filename in weights.items():
            font_id = QFontDatabase.addApplicationFont(os.path.join(_FONT_DIR, filename))
            if font_id == -1:
                ok = False
                continue
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _families[(role, weight)] = families[0]
    return ok


def _family_for(role: str, weight: int) -> str:
    if (role, weight) in _families:
        return _families[(role, weight)]
    # nearest loaded weight for the role
    candidates = [w for (r, w) in _families if r == role]
    if candidates:
        nearest = min(candidates, key=lambda w: abs(w - weight))
        return _families[(role, nearest)]
    return _FALLBACK[role]


def font(style: TextStyle, size: int | None = None, weight: int | None = None) -> QFont:
    """Return a QFont for a design-system text style."""
    w = weight or style.weight
    f = QFont(_family_for(style.family, w))
    f.setPixelSize(size or style.size)
    f.setWeight(QFont.Weight(w))
    if style.letter_spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, style.letter_spacing)
    if style.uppercase:
        f.setCapitalization(QFont.Capitalization.AllUppercase)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


def css_font(style: TextStyle) -> str:
    """Font declaration for QSS (family + pixel size + weight)."""
    fam = _family_for(style.family, style.weight)
    return f"font-family: '{fam}'; font-size: {style.size}px; font-weight: {style.weight};"
