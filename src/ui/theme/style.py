"""Global Qt stylesheet built from design tokens."""

from .fonts import css_font
from .tokens import Color, Radius, Size, Type


def _button_rules() -> str:
    variants = {
        # name: (bg, fg, border, hover_bg)
        "primary": (Color.PRIMARY, "#FFFFFF", Color.PRIMARY, Color.PRIMARY_HOVER),
        "secondary": (Color.SECONDARY_BG, Color.SECONDARY_FG, Color.SECONDARY_BORDER, "#FFDDEF"),
        "outline": (Color.SURFACE, Color.TEXT_PRIMARY, Color.BORDER_STRONG, Color.SUBTLE),
        "navy": (Color.BRAND, "#FFFFFF", Color.BRAND, "#2C4A62"),
        "ghost": ("transparent", Color.BRAND, "transparent", Color.BRAND_SOFT),
        "danger": (Color.DANGER, "#FFFFFF", Color.DANGER, "#C2187E"),
    }
    rules = []
    for name, (bg, fg, border, hover) in variants.items():
        rules.append(
            f"""
QPushButton[variant="{name}"] {{
    background: {bg}; color: {fg}; border: 1px solid {border};
}}
QPushButton[variant="{name}"]:hover {{ background: {hover}; }}
QPushButton[variant="{name}"]:pressed {{ padding-top: 1px; }}"""
        )
    rules.append(
        f"""
QPushButton[variant] {{ {css_font(Type.LABEL)} }}
QPushButton[btnSize="md"] {{
    min-height: {Size.BUTTON_MD - 2}px; max-height: {Size.BUTTON_MD - 2}px;
    border-radius: {Size.BUTTON_MD // 2}px; padding: 0 18px; font-size: 14px;
}}
QPushButton[btnSize="sm"] {{
    min-height: {Size.BUTTON_SM - 2}px; max-height: {Size.BUTTON_SM - 2}px;
    border-radius: {Size.BUTTON_SM // 2}px; padding: 0 12px;
}}
QPushButton[variant]:disabled {{
    background: {Color.CANVAS_ALT}; color: {Color.TEXT_TERTIARY}; border-color: {Color.BORDER};
}}"""
    )
    return "\n".join(rules)


def build_stylesheet() -> str:
    return f"""
QWidget {{
    color: {Color.TEXT_PRIMARY};
}}
QToolTip {{
    background: {Color.BRAND_STRONG}; color: #FFFFFF; border: none;
    padding: 6px 10px; border-radius: 8px; {css_font(Type.CAPTION)}
}}

/* Cards */
QFrame#Card {{
    background: {Color.SURFACE}; border: 1px solid {Color.BORDER};
    border-radius: {Radius.CARD}px;
}}

/* Line edits inside InputField / SearchField */
QLineEdit {{
    background: transparent; border: none; padding: 0;
    selection-background-color: {Color.PINK}; selection-color: {Color.TEXT_PRIMARY};
    {css_font(Type.BODY)}
}}

/* Icon buttons */
QToolButton[iconStyle] {{ border-radius: 12px; }}
QToolButton[iconStyle="outline"] {{ background: {Color.SURFACE}; border: 1px solid {Color.BORDER}; }}
QToolButton[iconStyle="soft"] {{ background: {Color.CANVAS}; border: none; }}
QToolButton[iconStyle="ghost"] {{ background: transparent; border: none; }}
QToolButton[iconStyle]:hover {{ background: {Color.BRAND_SOFT}; }}

/* Scroll bars */
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {Color.BORDER_STRONG}; border-radius: 3px; min-height: 40px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
{_button_rules()}
"""
