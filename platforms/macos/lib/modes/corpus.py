#!/usr/bin/env python3
"""Corpus creation mode.

Mirrors the Linux GTK CorpusCreationMode 1:1:

    Project Name:      [_______________________]
    Location:          [~/Corpora       ] [Browse…]
    Primary Language:  [English (en)  ▼]
    [✓] Auto-ensemble
    [✓] Include VS Code configuration
    Project / corpus will be created at: <preview path>
    [Cancel]  [New Project / Corpus]

Delegates the actual filesystem work to lib/scripts/create_corpus.sh
(macOS / Linux) or create_corpus.ps1 (Windows). Same args, same result.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QFileDialog, QMessageBox, QScrollArea,
)

from lib.ui.theme import set_role


class CorpusCreationMode(QMainWindow):
    """Create a new SpeechPrint corpus."""

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.template_dir = Path(cfg.templates_dir)
        self.script_dir = Path(cfg.scripts_dir)
        self.on_finished: Optional[Callable[[Path], None]] = None
        self.created_path: Optional[Path] = None

        self.setWindowTitle("SpeechPrint - New Project / Corpus")
        self.resize(600, 540)

        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Headerbar
        header = QWidget()
        set_role(header, "headerbar")
        header.setFixedHeight(40)
        outer.addWidget(header)

        # Scroll body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(30, 20, 30, 20)
        body_layout.setSpacing(14)

        title = QLabel("New Project / Corpus")
        set_role(title, "title")
        body_layout.addWidget(title)

        # Project name
        body_layout.addWidget(QLabel("Project Name:"))
        self.name_entry = QLineEdit()
        self.name_entry.setPlaceholderText("MyCorpus")
        self.name_entry.setText("MyCorpus")
        self.name_entry.textChanged.connect(self._update_preview)
        body_layout.addWidget(self.name_entry)

        # Location
        body_layout.addWidget(QLabel("Location:"))
        loc_row = QHBoxLayout()
        self.loc_entry = QLineEdit()
        self.loc_entry.setText(str(Path.home() / "Corpora"))
        self.loc_entry.textChanged.connect(self._update_preview)
        loc_row.addWidget(self.loc_entry, 1)
        browse_btn = QPushButton("Browse…")
        browse_btn.setMinimumWidth(100)
        browse_btn.clicked.connect(self._on_browse)
        loc_row.addWidget(browse_btn)
        body_layout.addLayout(loc_row)

        # Language
        body_layout.addWidget(QLabel("Primary Language:"))
        self.lang_combo = QComboBox()
        self._lang_codes = list(cfg.supported_languages)
        names = cfg.language_names
        for code in self._lang_codes:
            self.lang_combo.addItem(f"{names.get(code, code)} ({code})", code)
        try:
            default_idx = self._lang_codes.index(cfg.default_language)
        except ValueError:
            default_idx = 0
        self.lang_combo.setCurrentIndex(default_idx)
        body_layout.addWidget(self.lang_combo)

        hint = QLabel(
            "This only sets the default language for new recordings. "
            "You can change language per file later."
        )
        set_role(hint, "dim")
        hint.setWordWrap(True)
        body_layout.addWidget(hint)

        # Options
        self.ensemble_check = QCheckBox(
            "Auto-ensemble (run aggregation after each annotate)"
        )
        body_layout.addWidget(self.ensemble_check)

        self.vscode_check = QCheckBox("Include VS Code configuration")
        self.vscode_check.setChecked(True)
        body_layout.addWidget(self.vscode_check)

        # Preview
        preview_label = QLabel("Project / corpus will be created at:")
        set_role(preview_label, "dim")
        body_layout.addWidget(preview_label)
        self.preview = QLabel()
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        font = self.preview.font()
        font.setFamily("Menlo, Consolas, Monaco, monospace")
        self.preview.setFont(font)
        body_layout.addWidget(self.preview)
        self._update_preview()

        body_layout.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(30, 10, 30, 15)
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(cancel_btn)
        self.create_btn = QPushButton("New Project / Corpus")
        set_role(self.create_btn, "suggested")
        self.create_btn.clicked.connect(self._on_create)
        btn_row.addWidget(self.create_btn)
        outer.addLayout(btn_row)

        self.setCentralWidget(root)

    # --------------------------------------------------------------- preview

    def _update_preview(self, *_):
        name = self.name_entry.text() or "MyCorpus"
        loc = self.loc_entry.text() or str(Path.home())
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        self.preview.setText(f"{loc}/{safe_name}")

    def _on_browse(self):
        current = self.loc_entry.text()
        start = current if Path(current).is_dir() else str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select Corpus Location", start)
        if chosen:
            self.loc_entry.setText(chosen)

    def _selected_language(self) -> str:
        idx = self.lang_combo.currentIndex()
        if 0 <= idx < len(self._lang_codes):
            return self._lang_codes[idx]
        return self.cfg.default_language

    # ---------------------------------------------------------------- create

    def _on_create(self):
        name = self.name_entry.text().strip()
        loc = self.loc_entry.text().strip()

        if not name:
            self._error("Corpus name cannot be empty")
            return
        if not loc:
            self._error("Please select a location")
            return

        loc_path = Path(loc).expanduser()
        try:
            loc_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._error(f"Cannot create location:\n{loc_path}\n\n{e}")
            return

        corpus_dir = loc_path / name
        if corpus_dir.exists():
            self._error(f"Corpus already exists:\n{corpus_dir}")
            return

        self.create_btn.setEnabled(False)
        original_label = self.create_btn.text()
        self.create_btn.setText("Creating…")

        try:
            self._run_create_script(name, str(loc_path), corpus_dir, original_label)
        except Exception as e:
            self._error(f"Error:\n{e}")
            self.create_btn.setEnabled(True)
            self.create_btn.setText(original_label)

    def _run_create_script(self, name: str, loc: str, corpus_dir: Path, original_label: str):
        env = os.environ.copy()
        env["SPEECHPRINT_TEMPLATE_DIR"] = str(self.template_dir)

        if sys.platform == "win32":
            script = self.script_dir / "create_corpus.ps1"
            cmd = [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script),
                "new", name, loc,
                "-Language", self._selected_language(),
            ]
            if self.ensemble_check.isChecked():
                cmd.append("-AutoEnsemble")
            if not self.vscode_check.isChecked():
                cmd.append("-NoVSCode")
        else:
            script = self.script_dir / "create_corpus.sh"
            cmd = [
                "/bin/bash", str(script),
                "new", name, loc,
                "--language", self._selected_language(),
            ]
            if self.ensemble_check.isChecked():
                cmd.append("--auto-ensemble")
            if not self.vscode_check.isChecked():
                cmd.append("--no-vscode")

        if not script.exists():
            self._error(f"Corpus script not found:\n{script}")
            self.create_btn.setEnabled(True)
            self.create_btn.setText(original_label)
            return

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, env=env,
        )

        if result.returncode == 0:
            self.created_path = corpus_dir
            self._success_dialog(corpus_dir)
        else:
            self._error(
                "Failed to create project:\n"
                + (result.stderr or result.stdout or "Unknown error")
            )
            self.create_btn.setEnabled(True)
            self.create_btn.setText(original_label)

    def _success_dialog(self, corpus_path: Path):
        box = QMessageBox(self)
        box.setWindowTitle("Project Created")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText("Project created.")
        box.setInformativeText(
            f"Location:\n{corpus_path}\n\n"
            "You can now import or record audio, run annotation, "
            "and open results in Praat — all from the workspace."
        )
        open_btn = box.addButton("Open Project", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(open_btn)
        box.exec()
        if box.clickedButton() is open_btn and self.on_finished:
            try:
                self.on_finished(corpus_path)
            except Exception as e:
                print(f"on_finished error: {e}")
        self.close()

    def _error(self, message: str):
        QMessageBox.critical(self, "SpeechPrint", message)
