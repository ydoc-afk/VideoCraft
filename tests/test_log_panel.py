"""Tests for ui.panels.log_panel — log display widget."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must create QApplication before any QWidget
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from ui.panels.log_panel import LogPanel


def test_log_panel_initial_state():
    """Log panel starts empty."""
    panel = LogPanel()
    assert panel.log_edit.toPlainText() == ""


def test_log_panel_append_text():
    """Appending log lines adds text and auto-scrolls."""
    panel = LogPanel()
    panel.append_log("[2025-01-01 00:00:00] [INFO] Starting up")
    text = panel.log_edit.toPlainText()
    assert "Starting up" in text
    assert "INFO" in text


def test_log_panel_clear():
    """Clear button resets content."""
    panel = LogPanel()
    panel.append_log("[2025-01-01] [ERROR] Something failed")
    assert len(panel.log_edit.toPlainText()) > 0
    panel.clear_log()
    assert panel.log_edit.toPlainText() == ""


def test_log_panel_severity_colors():
    """Different severity levels produce different colors in HTML."""
    panel = LogPanel()
    panel.append_log("[INFO] normal message")
    panel.append_log("[ERROR] something broke")
    panel.append_log("[WARNING] low disk space")
    html = panel.log_edit.document().toHtml()
    assert "#d4d4d4" in html  # INFO color
    assert "#f44747" in html  # ERROR color
    assert "#f0a500" in html  # WARNING color
