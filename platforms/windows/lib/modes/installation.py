#!/usr/bin/env python3
"""Installation mode — multi-step setup wizard.

Mirrors the Linux GTK installer step-for-step:
    Step 1: Ready to Install?
    Step 2: Select Release Channel (Stable / Development)
    Step 3: Select Language Modules
    Step 4: System Verification
    Step 5: Prepare Analysis Tools  (runs install_deps.sh / .ps1)
    Step 6: Installation Complete!

The dependency-install script is the per-platform piece. Everything else here
is identical to the Linux GUI in wording, ordering, and behaviour.
"""

import asyncio
import os
import struct
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QFrame, QCheckBox, QScrollArea, QPlainTextEdit,
)

from lib.ui.theme import set_role


# ----------------------------------------------------------------------------
# Step base — every step has build_ui() + execute()
# ----------------------------------------------------------------------------


class _Step:
    """Common helpers."""

    def build_ui(self, container: QWidget):
        raise NotImplementedError

    def execute(self) -> bool:
        """Run any work for this step. Synchronous return value indicates
        whether the user should be allowed to proceed; long work goes in
        a worker thread (see DependenciesStep).
        """
        return True

    @staticmethod
    def _clear(container: QWidget):
        layout = container.layout()
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)


# ----------------------------------------------------------------------------
# Step 1 — confirmation
# ----------------------------------------------------------------------------


class ConfirmationStep(_Step):
    def build_ui(self, container: QWidget):
        self._clear(container)
        layout = container.layout()

        title = QLabel("Ready to Install?")
        set_role(title, "title")
        layout.addWidget(title)

        info = QLabel(
            "Configures this machine for SpeechPrint analysis:\n"
            "• Whisper / WhisperX transcription\n"
            "• Praat / Parselmouth prosody analysis\n"
            "• phonemizer + espeak-ng (IPA phones)\n"
            "• TextGrid generation\n\n"
            "Once per computer. Internet required, ~5 GB disk."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch(1)


# ----------------------------------------------------------------------------
# Step 2 — release channel
# ----------------------------------------------------------------------------


class ReleaseTypeStep(_Step):
    def __init__(self):
        self.stable_radio: Optional[QRadioButton] = None
        self.dev_radio: Optional[QRadioButton] = None

    def build_ui(self, container: QWidget):
        self._clear(container)
        layout = container.layout()

        title = QLabel("Select Release Channel")
        set_role(title, "title")
        layout.addWidget(title)

        subtitle = QLabel("Choose which version of SpeechPrint to install:")
        set_role(subtitle, "dim")
        layout.addWidget(subtitle)

        # Stable card
        stable_frame = QFrame()
        set_role(stable_frame, "card")
        sf_layout = QVBoxLayout(stable_frame)
        sf_layout.setContentsMargins(15, 12, 15, 12)
        sf_layout.setSpacing(6)
        self.stable_radio = QRadioButton("Stable Release (Recommended)")
        self.stable_radio.setChecked(True)
        sf_layout.addWidget(self.stable_radio)
        sd = QLabel(
            "Production-ready release. Tested and stable.\n"
            "Recommended for general use and field-recording workflows."
        )
        set_role(sd, "dim")
        sd.setContentsMargins(25, 0, 0, 0)
        sf_layout.addWidget(sd)
        layout.addWidget(stable_frame)

        # Dev card
        dev_frame = QFrame()
        set_role(dev_frame, "card")
        df_layout = QVBoxLayout(dev_frame)
        df_layout.setContentsMargins(15, 12, 15, 12)
        df_layout.setSpacing(6)
        self.dev_radio = QRadioButton("Development Release")
        df_layout.addWidget(self.dev_radio)
        dd = QLabel(
            "Latest features and improvements. May contain bugs.\n"
            "For testing and early access to new functionality."
        )
        set_role(dd, "dim")
        dd.setContentsMargins(25, 0, 0, 0)
        df_layout.addWidget(dd)
        layout.addWidget(dev_frame)

        # Mutex group
        group = QButtonGroup(container)
        group.setExclusive(True)
        group.addButton(self.stable_radio)
        group.addButton(self.dev_radio)

        layout.addStretch(1)

    def get_release_type(self) -> str:
        if self.dev_radio is not None and self.dev_radio.isChecked():
            return "dev"
        return "stable"


# ----------------------------------------------------------------------------
# Step 3 — language modules
# ----------------------------------------------------------------------------


class LanguageModulesStep(_Step):
    def __init__(self, cfg):
        self.cfg = cfg
        self.checks: dict[str, QCheckBox] = {}
        self.selected: set[str] = set()
        self.summary: Optional[QLabel] = None

    def build_ui(self, container: QWidget):
        self._clear(container)
        layout = container.layout()

        title = QLabel("Select Language Modules")
        set_role(title, "title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Pick the languages you expect to use. Each adds an acoustic "
            "model + dictionary (~300 MB).\n"
            "You can add more languages later from this installer without "
            "starting over — per-recording language is set inside each project."
        )
        set_role(subtitle, "dim")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        ilayout = QVBoxLayout(inner)
        ilayout.setContentsMargins(10, 10, 10, 10)
        ilayout.setSpacing(6)

        names = self.cfg.language_names
        default = self.cfg.default_language
        for code in self.cfg.supported_languages:
            display = names.get(code, code)
            cb = QCheckBox(f"{display} ({code})")
            if code == default:
                cb.setChecked(True)
                self.selected.add(code)
            cb.toggled.connect(lambda checked, c=code: self._on_toggled(c, checked))
            self.checks[code] = cb
            ilayout.addWidget(cb)
        ilayout.addStretch(1)

        scroll.setWidget(inner)
        scroll.setMinimumHeight(280)
        layout.addWidget(scroll, 1)

        self.summary = QLabel()
        set_role(self.summary, "dim")
        self._update_summary()
        layout.addWidget(self.summary)

    def _on_toggled(self, code: str, checked: bool):
        if checked:
            self.selected.add(code)
        else:
            self.selected.discard(code)
        self._update_summary()

    def _update_summary(self):
        if self.summary is None:
            return
        n = len(self.selected)
        size = n * 300
        if n == 0:
            self.summary.setText("Select at least one language.")
            set_role(self.summary, "error")
        else:
            self.summary.setText(
                f"{n} module(s) selected · approx. {size} MB acoustic models"
            )
            set_role(self.summary, "dim")

    def get_languages(self) -> list[str]:
        return sorted(self.selected) if self.selected else [self.cfg.default_language]


# ----------------------------------------------------------------------------
# Step 4 — system check
# ----------------------------------------------------------------------------


class SystemCheckStep(_Step):
    def __init__(self):
        self.log: Optional[QPlainTextEdit] = None
        self.status: Optional[QLabel] = None

    def build_ui(self, container: QWidget):
        self._clear(container)
        layout = container.layout()

        title = QLabel("Step 4: Verify Installation")
        set_role(title, "title")
        layout.addWidget(title)

        self.status = QLabel("Checking…")
        layout.addWidget(self.status)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        set_role(self.log, "log")
        layout.addWidget(self.log, 1)

        self._run_checks()

    def _run_checks(self):
        checks = [
            ("64-bit system", lambda: struct.calcsize("P") == 8),
            ("Python 3.11+", lambda: sys.version_info >= (3, 11)),
            ("Git", lambda: self._has_command("git")),
            ("ffmpeg (optional, will install if missing)", lambda: True),
        ]

        all_pass = True
        for name, check in checks:
            try:
                result = check()
            except Exception:
                result = False
            mark = "✓" if result else "✗"
            self._log(f"{mark} {name}")
            if not result and "optional" not in name:
                all_pass = False

        if all_pass:
            self.status.setText("✓ Check complete")
        else:
            self.status.setText("⚠ Some checks failed — installer will continue")

    @staticmethod
    def _has_command(cmd: str) -> bool:
        try:
            subprocess.run(
                [cmd, "--version"], capture_output=True, timeout=5, check=True
            )
            return True
        except Exception:
            return False

    def _log(self, msg: str):
        if self.log is not None:
            self.log.appendPlainText(msg)


# ----------------------------------------------------------------------------
# Step 5 — dependencies install (per-platform script)
# ----------------------------------------------------------------------------


class _DepsWorker(QThread):
    line = pyqtSignal(str)
    finished_ok = pyqtSignal(int)  # returncode

    def __init__(self, script: Path, release_type: str, languages: list[str]):
        super().__init__()
        self.script = script
        self.release_type = release_type
        self.languages = languages

    def run(self):
        if sys.platform == "win32":
            cmd = [
                "powershell.exe",
                "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(self.script),
                "-ReleaseType", self.release_type,
                "-Languages", ",".join(self.languages),
            ]
        else:
            # macOS / Linux: bash
            try:
                os.chmod(self.script, 0o755)
            except Exception:
                pass
            cmd = [
                "/bin/bash", str(self.script),
                self.release_type, ",".join(self.languages),
            ]

        self.line.emit(f"[debug] release={self.release_type}  languages={','.join(self.languages)}")
        self.line.emit(f"Running: {self.script}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            self.line.emit(f"✗ Failed to start installer: {e}")
            self.finished_ok.emit(1)
            return

        assert proc.stdout is not None
        for raw in proc.stdout:
            self.line.emit(raw.rstrip("\n"))
        rc = proc.wait()
        self.finished_ok.emit(rc)


class DependenciesStep(_Step):
    def __init__(self, script_dir: Path):
        self.script_dir = Path(script_dir)
        self.release_type = "stable"
        self.languages = ["en"]
        self.status: Optional[QLabel] = None
        self.log: Optional[QPlainTextEdit] = None
        self.worker: Optional[_DepsWorker] = None
        self._enable_next = None  # set by InstallationMode

    def build_ui(self, container: QWidget):
        self._clear(container)
        layout = container.layout()

        title = QLabel("Step 5: Prepare Analysis Tools")
        set_role(title, "title")
        layout.addWidget(title)

        self.status = QLabel("Preparing…")
        layout.addWidget(self.status)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        set_role(self.log, "log")
        layout.addWidget(self.log, 1)

        self._start_install()

    def _start_install(self):
        # Per-platform script name
        if sys.platform == "win32":
            script_name = "install_deps.ps1"
        else:
            script_name = "install_deps.sh"

        script = self.script_dir / script_name
        if not script.exists():
            fallback = Path(__file__).resolve().parent.parent / "scripts" / script_name
            if fallback.exists():
                script = fallback

        if not script.exists():
            self._log(f"✗ {script_name} not found at {script}")
            if self.status:
                self.status.setText("✗ Script not found")
            if self._enable_next:
                self._enable_next()
            return

        self.worker = _DepsWorker(script, self.release_type, self.languages)
        self.worker.line.connect(self._log)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.start()

    def _on_done(self, rc: int):
        if rc == 0:
            if self.status:
                self.status.setText("✓ Dependencies installed")
        else:
            self._log(f"✗ Exit code: {rc}")
            if self.status:
                self.status.setText("⚠ Installation completed with warnings")
        if self._enable_next:
            self._enable_next()

    def _log(self, msg: str):
        if self.log is not None:
            self.log.appendPlainText(msg)


# ----------------------------------------------------------------------------
# Step 6 — completion
# ----------------------------------------------------------------------------


class CompletionStep(_Step):
    def build_ui(self, container: QWidget):
        self._clear(container)
        layout = container.layout()

        title = QLabel("✓ Installation Complete!")
        set_role(title, "title")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        info = QLabel(
            "Next steps:\n\n"
            "1. Click Finish to close this installer.\n"
            "2. From the launcher, choose New Project / Corpus.\n"
            "3. Inside the project workspace you can:\n"
            "   • Import Audio or ● Record a new file\n"
            "   • Run Annotation to generate the TextGrid\n"
            "   • Open in Praat to inspect\n"
            "   • Export ZIP to share\n\n"
            "The CLI is still available for power users:\n"
            "    speechprint annotate data/recording.wav --language en"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch(1)


# ----------------------------------------------------------------------------
# Wizard window
# ----------------------------------------------------------------------------


class InstallationMode(QMainWindow):
    """6-step installer wizard."""

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.script_dir = Path(cfg.scripts_dir)
        self.setWindowTitle("SpeechPrint - Install Toolchain")
        self.resize(700, 600)

        self.steps: list[_Step] = [
            ConfirmationStep(),
            ReleaseTypeStep(),
            LanguageModulesStep(cfg),
            SystemCheckStep(),
            DependenciesStep(self.script_dir),
            CompletionStep(),
        ]
        self.current = 0
        self.release_type = "stable"
        self.languages = ["en"]

        # ----- frame layout -----
        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header bar
        header = QWidget()
        set_role(header, "headerbar")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(15, 10, 15, 10)
        self.step_label = QLabel("")
        set_role(self.step_label, "section")
        h_layout.addWidget(self.step_label)
        outer.addWidget(header)

        # Content container — each step rebuilds its children inside this
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(30, 20, 30, 10)
        self.content_layout.setSpacing(15)
        outer.addWidget(self.content, 1)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(30, 10, 30, 15)

        self.back_btn = QPushButton("Back")
        self.back_btn.setEnabled(False)
        self.back_btn.clicked.connect(self._on_back)
        btn_row.addWidget(self.back_btn)

        btn_row.addStretch(1)

        self.next_btn = QPushButton("Next")
        set_role(self.next_btn, "suggested")
        self.next_btn.clicked.connect(self._on_next)
        btn_row.addWidget(self.next_btn)

        outer.addLayout(btn_row)
        self.setCentralWidget(root)

        self._show_step(0)

    # ------------------------------------------------------------------ flow

    def _show_step(self, idx: int):
        self.current = idx
        self.step_label.setText(f"Step {idx + 1} of {len(self.steps)}")

        step = self.steps[idx]

        # Special-case the deps step so it can re-enable Next when its worker
        # exits, since it's the only step that runs long async work.
        if isinstance(step, DependenciesStep):
            step._enable_next = lambda: self.next_btn.setEnabled(True)

        step.build_ui(self.content)

        self.back_btn.setEnabled(idx > 0)

        if idx == 0:
            self.next_btn.setText("Start Installation")
        elif idx == len(self.steps) - 1:
            self.next_btn.setText("Finish")
        else:
            self.next_btn.setText("Next")

        # Steps that block "Next" until they're done:
        if isinstance(step, DependenciesStep):
            self.next_btn.setEnabled(False)
        else:
            self.next_btn.setEnabled(True)

    def _on_next(self):
        # Capture state from the step we're leaving
        if self.current == 1:
            step = self.steps[1]
            if isinstance(step, ReleaseTypeStep):
                self.release_type = step.get_release_type()
                deps = self.steps[4]
                if isinstance(deps, DependenciesStep):
                    deps.release_type = self.release_type
        elif self.current == 2:
            step = self.steps[2]
            if isinstance(step, LanguageModulesStep):
                self.languages = step.get_languages()
                deps = self.steps[4]
                if isinstance(deps, DependenciesStep):
                    deps.languages = self.languages

        if self.current < len(self.steps) - 1:
            self._show_step(self.current + 1)
        else:
            self.close()

    def _on_back(self):
        if self.current > 0:
            self._show_step(self.current - 1)
