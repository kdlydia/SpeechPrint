#!/usr/bin/env python3
"""SpeechPrint - cross-platform Qt launcher.

Mirrors the Linux GTK launcher 1:1 in behaviour:
    ┌─────────────────────────────────────────┐
    │  What would you like to do?             │
    │                                         │
    │  [  Install SpeechPrint           ]     │
    │  [  New Project / Corpus          ]     │
    └─────────────────────────────────────────┘

If the launcher is invoked with a directory path that contains corpus.toml,
it skips the mode selector and opens that project's workspace directly.
"""

import os
import sys
from enum import Enum
from pathlib import Path

# Ensure `lib` is importable when the launcher is run as `python -m lib.main`
_main_dir = Path(__file__).resolve().parent
_lib_dir = _main_dir.parent
if str(_lib_dir) not in sys.path:
    sys.path.insert(0, str(_lib_dir))

try:
    from lib.config import get_config
    cfg = get_config()
    for key, value in cfg.get_env_vars().items():
        os.environ.setdefault(key, value)
except Exception as e:
    print(f"Error loading SpeechPrint configuration: {e}", file=sys.stderr)
    sys.exit(1)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from lib.ui.theme import setup_theme, set_role
from lib.modes.installation import InstallationMode
from lib.modes.corpus import CorpusCreationMode
from lib.modes.project import ProjectWorkspace


class Mode(Enum):
    INSTALLATION = 1
    CORPUS_CREATION = 2


class ModeSelector(QMainWindow):
    """Modal landing window: Install or New Project / Corpus."""

    def __init__(self, on_choose):
        super().__init__()
        self.on_choose = on_choose
        self.setWindowTitle("SpeechPrint - Select Mode")
        self.resize(500, 300)

        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        title = QLabel("What would you like to do?")
        set_role(title, "title")
        layout.addWidget(title)

        install_btn = QPushButton("Install SpeechPrint")
        install_btn.setMinimumHeight(80)
        set_role(install_btn, "suggested")
        install_btn.clicked.connect(lambda: self._choose(Mode.INSTALLATION))
        layout.addWidget(install_btn)

        corpus_btn = QPushButton("New Project / Corpus")
        corpus_btn.setMinimumHeight(80)
        set_role(corpus_btn, "suggested")
        corpus_btn.clicked.connect(lambda: self._choose(Mode.CORPUS_CREATION))
        layout.addWidget(corpus_btn)

        layout.addStretch(1)
        self.setCentralWidget(root)

    def _choose(self, mode: Mode):
        self.close()
        # Use a single-shot to fire after the close event has fully drained.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.on_choose(mode))


class SpeechPrintApp:
    """Owns the open top-level windows so Qt doesn't garbage-collect them."""

    def __init__(self):
        self.windows: list = []

    def open_selector(self):
        sel = ModeSelector(self._on_mode_chosen)
        self.windows.append(sel)
        sel.show()

    def _on_mode_chosen(self, mode: Mode):
        if mode == Mode.INSTALLATION:
            w = InstallationMode(cfg)
            self.windows.append(w)
            w.show()
        elif mode == Mode.CORPUS_CREATION:
            w = CorpusCreationMode(cfg)
            w.on_finished = self._open_workspace_from_path
            self.windows.append(w)
            w.show()

    def _open_workspace_from_path(self, project_dir: Path):
        w = ProjectWorkspace(cfg, project_dir)
        self.windows.append(w)
        w.show()


def main():
    # High-DPI is automatic in Qt6; nothing to enable here.
    app = QApplication(sys.argv)
    app.setApplicationName("SpeechPrint")
    app.setOrganizationName("SpeechPrint")

    setup_theme(app)

    icon_path = Path(__file__).resolve().parent.parent / "resources" / "speechprint.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    sp_app = SpeechPrintApp()

    # If invoked with a project directory, jump straight in.
    direct_opened = False
    for a in sys.argv[1:]:
        p = Path(a)
        if p.is_dir() and (p / "corpus.toml").exists():
            sp_app._open_workspace_from_path(p.resolve())
            direct_opened = True
            break

    if not direct_opened:
        sp_app.open_selector()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
