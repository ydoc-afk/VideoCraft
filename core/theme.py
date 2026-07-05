"""qt-material theme helpers — single source of truth for theming.

The app previously hardcoded ``dark_orange.xml`` (which this qt-material
version does not ship) and then forced an orange ``primaryColor`` on top of
*every* theme, while the custom QSS hardcoded the same orange in ~28 places.
The net effect was that the Settings theme picker changed nothing visible.

Now: the base theme is applied as-is (its own accent shows through), and the
custom QSS's accent color is recolored at apply time to match the selected
theme's ``primaryColor``. Picking a different theme therefore actually
re-tints the whole UI. Theme names are validated against what qt-material
really provides so a version mismatch can't reintroduce a missing-theme.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# A real qt-material theme (amber reads close to the app's original orange).
DEFAULT_THEME = "dark_amber.xml"

# Both dark and light themes are offered. The custom QSS no longer hardcodes
# background/text colors — they are substituted from each theme's palette at
# apply time (see _palette / custom_qss), so text stays legible in either
# mode. Each theme also brings its own accent color, which is what the
# picker's tint changes.
_FALLBACK_THEMES = [
    "dark_amber.xml", "dark_blue.xml", "dark_cyan.xml", "dark_lightgreen.xml",
    "dark_pink.xml", "dark_purple.xml", "dark_red.xml", "dark_teal.xml",
    "dark_yellow.xml",
    "light_amber.xml", "light_blue.xml", "light_cyan.xml", "light_pink.xml",
    "light_purple.xml", "light_red.xml", "light_teal.xml",
]

# Only fonts/density here — colors come from the selected theme so the
# theme picker is meaningful. (Previously this also pinned primaryColor to
# orange, which is exactly what made every theme look the same.)
THEME_EXTRA = {
    "font_family": "Segoe UI",
    "font_size": "13px",
    "density_scale": "-1",
}

# The accent colors the custom QSS was authored with — recolored per theme.
_FALLBACK_PRIMARY = "#e85d04"
_FALLBACK_PRIMARY_LIGHT = "#ff8c42"

# Dark-theme palette used when qt-material can't report colors. The keys are
# the @tokens the custom QSS uses (see assets/themes/custom_overrides.qss).
_PALETTE_FALLBACK = {
    "bg": "#1e1e1e",
    "bgdark": "#111111",
    "bglight": "#2d2d2d",
    "text": "#d4d4d4",
    "textdim": "#888888",
    "border": "#444444",
    "accent": _FALLBACK_PRIMARY,
    "accentlight": _FALLBACK_PRIMARY_LIGHT,
    "success": "#4ec9b0",
}

_QSS_PATH = Path(__file__).parent.parent / "assets" / "themes" / "custom_overrides.qss"

# Palette of the most-recently applied theme, so runtime widgets that build
# their own inline styles (e.g. DragDropArea) can stay theme-aware.
_current_palette: dict[str, str] = dict(_PALETTE_FALLBACK)


def _luminance(hex_color: str) -> float:
    """Rough relative luminance (0=black, 1=white) of a #rrggbb color."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, IndexError):
        return 0.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _palette(theme: str) -> dict[str, str]:
    """Build the QSS token palette from a theme's qt-material colors.

    Maps qt-material's palette roles onto our tokens so backgrounds and text
    track the theme (dark bg/light text for dark themes, and vice-versa).
    Falls back to the dark palette if qt-material can't report colors.
    """
    try:
        from qt_material import get_theme
        c = get_theme(resolve_theme(theme))
        bg = c.get("secondaryColor") or _PALETTE_FALLBACK["bg"]
        text = c.get("primaryTextColor") or _PALETTE_FALLBACK["text"]
        accent = c.get("primaryColor") or _FALLBACK_PRIMARY
        is_dark = _luminance(bg) < 0.5

        # Hint text: qt-material sometimes reuses the primary text color (e.g.
        # white on dark), which leaves hints undimmed. Fall back to a legible
        # mid-tone when the reported dim color barely differs from the primary.
        textdim = c.get("secondaryTextColor") or ""
        if not textdim or abs(_luminance(textdim) - _luminance(text)) < 0.12:
            textdim = "#b0b0b0" if is_dark else "#555555"

        # Border: secondaryLightColor is often ~white on light themes, which
        # would vanish against the panel — force a contrasting tone instead.
        border = c.get("secondaryLightColor") or _PALETTE_FALLBACK["border"]
        if abs(_luminance(border) - _luminance(bg)) < 0.12:
            border = "#555a5f" if is_dark else "#c0c0c0"

        return {
            "bg": bg,
            "bgdark": c.get("secondaryDarkColor") or _PALETTE_FALLBACK["bgdark"],
            "bglight": c.get("secondaryLightColor") or _PALETTE_FALLBACK["bglight"],
            "text": text,
            "textdim": textdim,
            "border": border,
            "accent": accent,
            "accentlight": c.get("primaryLightColor") or accent,
            # qt-material has no "success" role; pick one that reads on this bg.
            "success": "#4ec9b0" if is_dark else "#0b7a63",
        }
    except Exception as e:
        logger.debug("Could not build palette for %s: %s", theme, e)
        return dict(_PALETTE_FALLBACK)


def current_palette() -> dict[str, str]:
    """Return the palette of the last-applied theme (dark fallback if none)."""
    return dict(_current_palette)


def mark_hint(widget, on: bool = True) -> None:
    """Style a label as secondary/hint text (or clear it), theme-aware.

    Sets the ``hint`` dynamic property the custom QSS keys off, then repolishes
    so the change takes effect on an already-shown widget. Use this instead of
    an inline ``color:`` so the text adapts to light and dark themes.
    """
    widget.setProperty("hint", "true" if on else "false")
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


def available_themes() -> list[str]:
    """Return the qt-material themes shipped (fallback if unknown).

    Both dark and light themes are offered now that the custom QSS adapts its
    colors per theme (see _palette).
    """
    try:
        from qt_material import list_themes
        themes = [t for t in list_themes() if t.startswith(("dark_", "light_"))]
        if themes:
            return themes
    except Exception as e:  # ImportError or API change
        logger.debug("Could not query qt-material themes: %s", e)
    return list(_FALLBACK_THEMES)


def resolve_theme(name: str) -> str:
    """Return ``name`` if qt-material ships it, else a safe default."""
    themes = available_themes()
    if name in themes:
        return name
    fallback = DEFAULT_THEME if DEFAULT_THEME in themes else (themes[0] if themes else DEFAULT_THEME)
    if name:
        logger.warning("Theme %r not available — falling back to %s", name, fallback)
    return fallback


def theme_colors(theme: str) -> tuple[str, str]:
    """Return (primaryColor, primaryLightColor) for a theme.

    Falls back to the app's orange if qt-material can't report them.
    """
    try:
        from qt_material import get_theme
        colors = get_theme(resolve_theme(theme))
        primary = colors.get("primaryColor") or _FALLBACK_PRIMARY
        light = colors.get("primaryLightColor") or primary
        return primary, light
    except Exception as e:
        logger.debug("Could not read theme colors for %s: %s", theme, e)
        return _FALLBACK_PRIMARY, _FALLBACK_PRIMARY_LIGHT


def custom_qss(theme: str) -> str:
    """Load the custom QSS with its @tokens substituted from the theme palette.

    Tokens are replaced longest-first so that prefixes can't clobber longer
    tokens (e.g. @accent must not partially match inside @accentlight).
    """
    if not _QSS_PATH.exists():
        return ""
    qss = _QSS_PATH.read_text()
    pal = _palette(theme)
    for token in sorted(pal, key=len, reverse=True):
        qss = qss.replace("@" + token, pal[token])
    return qss


def apply_theme(app_or_widget, theme: str) -> str:
    """Apply a validated qt-material theme plus the recolored custom QSS.

    Returns the theme actually applied. If qt-material is not installed the
    custom QSS is still applied (with its default orange) and the requested
    name is returned.
    """
    resolved = resolve_theme(theme)
    try:
        from qt_material import apply_stylesheet
        apply_stylesheet(app_or_widget, theme=resolved, extra=THEME_EXTRA)
        logger.info("qt-material theme applied: %s", resolved)
    except ImportError:
        logger.warning("qt-material not installed — using system theme")
        resolved = theme

    # Record the palette so runtime widgets (e.g. DragDropArea) can match it.
    global _current_palette
    _current_palette = _palette(resolved)

    # apply_stylesheet replaces the app stylesheet, so append the (tokenized)
    # custom overrides afterwards. Target the QApplication so the whole UI
    # picks it up regardless of what was passed in.
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or app_or_widget
    extra_qss = custom_qss(resolved)
    if extra_qss:
        app.setStyleSheet(app.styleSheet() + extra_qss)
    return resolved
