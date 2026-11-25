"""Design tokens for the SiMonPro desktop UI.

Values mirror the "Color" and "Type" variable collections in the Figma file
(page "Design System"). Keep names in sync with Figma so designers and
developers talk about the same thing.
"""

from dataclasses import dataclass


class Color:
    # Base
    CANVAS = "#F1F4F8"
    SURFACE = "#FFFFFF"
    SUBTLE = "#F8FAFC"
    CANVAS_ALT = "#EEF0E2"

    # Brand (navy from the original lasti_yey palette)
    BRAND = "#355872"
    BRAND_STRONG = "#172A3A"
    BRAND_SOFT = "#EAF6FF"

    # Text
    TEXT_PRIMARY = "#172A3A"
    TEXT_SECONDARY = "#56718A"
    TEXT_TERTIARY = "#7F97AB"
    TEXT_ON_BRAND = "#FFFFFF"
    TEXT_LINK = "#3533CD"

    # Icons and borders
    ICON = "#56718A"
    ICON_STRONG = "#172A3A"
    BORDER = "#E4EBF2"
    BORDER_STRONG = "#C9D6E1"
    BORDER_FOCUS = "#5C61E4"

    # Accents
    AQUA = "#A8E9EC"
    PINK = "#F4B3CD"
    INDIGO = "#5C61E4"
    MAGENTA = "#FD31AE"
    ROYAL = "#3533CD"

    # Buttons
    PRIMARY = "#5C61E4"
    PRIMARY_HOVER = "#4B50D3"
    SECONDARY_BG = "#FFE9F5"
    SECONDARY_FG = "#9B1C5A"
    SECONDARY_BORDER = "#F4B3CD"
    DANGER = "#D61F8F"

    # Charts
    CHART_OK = "#355872"
    CHART_OK_SOFT = "#C9D6E1"
    CHART_NG = "#FD31AE"
    CHART_GRID = "#E4EBF2"

    # Sidebar
    SIDEBAR_ACTIVE = "#355872"
    SIDEBAR_TEXT = "#56718A"
    SIDEBAR_ICON = "#7F97AB"


@dataclass(frozen=True)
class Tone:
    """Four levels per status tone, same as Figma tone/<name>-<level>."""

    soft: str
    mid: str
    solid: str
    ink: str


TONES = {
    "blue": Tone("#EAF6FF", "#CDEBFF", "#4C9BD6", "#2C4A62"),
    "green": Tone("#E2F5F0", "#CDEFE4", "#2BB48F", "#0C5C4B"),
    "pink": Tone("#FFE9F5", "#FBD6E5", "#FD31AE", "#9B1C5A"),
    "indigo": Tone("#EEEFFD", "#DCDDFB", "#5C61E4", "#2D2FA8"),
    "amber": Tone("#FCF2E1", "#F8E3BE", "#E39B2F", "#7A4D0C"),
}

# Badge status -> tone name (None = neutral grey)
STATUS_TONE = {
    "OK": "green",
    "PASSED": "green",
    "NG": "pink",
    "HOLD": "amber",
    "BERJALAN": "blue",
    "DITUTUP": None,
}


@dataclass(frozen=True)
class TextStyle:
    family: str  # "display" or "body"
    size: int  # pixel size, matches Figma
    weight: int  # CSS-like weight 400..700
    line_height: int
    letter_spacing: float = 0.0
    uppercase: bool = False


class Type:
    DISPLAY_XL = TextStyle("display", 44, 700, 50, -1.2)
    DISPLAY = TextStyle("display", 32, 700, 38, -0.8)
    TITLE = TextStyle("display", 22, 600, 28, -0.3)
    HEADING = TextStyle("body", 17, 700, 24, -0.1)
    BODY = TextStyle("body", 15, 400, 22)
    BODY_STRONG = TextStyle("body", 15, 600, 22)
    LABEL = TextStyle("body", 14, 600, 20)
    CAPTION = TextStyle("body", 13, 500, 18)
    OVERLINE = TextStyle("body", 12, 700, 16, 0.8, True)


class Radius:
    CARD = 20
    PANEL = 22
    MODAL = 24
    INPUT = 12
    CHIP = 12
    BADGE = 8


class Size:
    SIDEBAR_EXPANDED = 240
    SIDEBAR_COLLAPSED = 80
    BUTTON_MD = 44
    BUTTON_SM = 36
    INPUT = 46
    ICON_BUTTON = 40


# Business rule shown across the UI (PRD FR-26)
NG_TOLERANCE_PERCENT = 5.0
