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

# The app's custom QSS is authored for a dark UI (dark panel backgrounds,
# light text), so only dark qt-material themes are offered — light themes
# would leave light text on light backgrounds. Each dark theme still brings
# its own accent color, which is what the picker changes.
_FALLBACK_THEMES = [
    "dark_amber.xml", "dark_blue.xml", "dark_cyan.xml", "dark_lightgreen.xml",
    "dark_pink.xml", "dark_purple.xml", "dark_red.xml", "dark_teal.xml",
    "dark_yellow.xml",
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
_QSS_PRIMARY = "#e85d04"
_QSS_PRIMARY_LIGHT = "#ff8c42"
_FALLBACK_PRIMARY = "#e85d04"
_FALLBACK_PRIMARY_LIGHT = "#ff8c42"

_QSS_PATH = Path(__file__).parent.parent / "assets" / "themes" / "custom_overrides.qss"


def available_themes() -> list[str]:
    """Return the dark qt-material themes shipped (fallback if unknown).

    Filtered to dark themes only — see _FALLBACK_THEMES for why.
    """
    try:
        from qt_material import list_themes
        themes = [t for t in list_themes() if t.startswith("dark_")]
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
    """Load the custom QSS with its accent recolored to the theme's accent."""
    if not _QSS_PATH.exists():
        return ""
    qss = _QSS_PATH.read_text()
    primary, light = theme_colors(theme)
    # Recolor both the base and light accent (case-insensitive on the hex).
    for token in (_QSS_PRIMARY, _QSS_PRIMARY.upper()):
        qss = qss.replace(token, primary)
    for token in (_QSS_PRIMARY_LIGHT, _QSS_PRIMARY_LIGHT.upper()):
        qss = qss.replace(token, light)
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

    # apply_stylesheet replaces the app stylesheet, so append the (recolored)
    # custom overrides afterwards. Target the QApplication so the whole UI
    # picks it up regardless of what was passed in.
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or app_or_widget
    extra_qss = custom_qss(resolved)
    if extra_qss:
        app.setStyleSheet(app.styleSheet() + extra_qss)
    return resolved
