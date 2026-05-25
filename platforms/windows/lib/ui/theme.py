#!/usr/bin/env python3
"""Qt dark theme + role helpers.

The role helpers tag widgets with a `role` property that the QSS selectors
pick up — letting us style "suggested" / "destructive" / "dim" / "section"
labels without sprinkling raw CSS through the UI code.
"""

from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget


def setup_theme(app: QApplication):
    """Load dark.qss and apply it to the whole application."""
    qss_file = Path(__file__).parent / "dark.qss"
    if not qss_file.exists():
        return
    try:
        app.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[SpeechPrint theme] Could not load {qss_file}: {e}")


def set_role(widget: QWidget, role: str):
    """Tag a widget so the QSS picks up the role selector.

    role is one of: title, section, dim, success, error, status, log,
    suggested, destructive, flat, card, headerbar.
    """
    widget.setProperty("role", role)
    # Re-polish so a runtime property change is picked up.
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()
