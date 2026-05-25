"""Project workspace — the main GUI for working with a SpeechPrint corpus.

What the user sees after creating a project:
    LEFT panel   recordings list  +  Import Audio / ● Record
    RIGHT panel  language picker, Run Annotation / Cancel,
                 Open in Praat / Open Folder / Export ZIP,
                 9-stage progress display, status line,
                 collapsible technical log, Feedback Form footer.

Platform-specific bits — and only these — branch on sys.platform:
    - Audio capture     (avfoundation on macOS, dshow on Windows, pulse on Linux)
    - Open file manager (Finder / Explorer / xdg-open)
    - Open in Praat     (Praat.app -> /usr/bin/open  on macOS,
                         Praat.exe                    on Windows,
                         `praat --open …`             on Linux)

Everything else is identical to the GTK Linux version in wording,
layout, and behaviour.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLabel,
    QPushButton, QComboBox, QListWidget, QListWidgetItem, QPlainTextEdit,
    QFileDialog, QMessageBox, QFrame, QScrollArea,
)

from lib.ui.theme import set_role


# ============================================================================
# UTILITIES
# ============================================================================


def _safe_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9_\-\.]", "_", name)
    return name or "recording"


def _next_recording_name(data_dir: Path, prefix: str = "recording") -> str:
    n = 1
    while (data_dir / f"{prefix}_{n:02d}.wav").exists():
        n += 1
    return f"{prefix}_{n:02d}.wav"


# ============================================================================
# OPEN-EXTERNAL HELPERS (per-platform)
# ============================================================================


def _which(*names: str) -> Optional[str]:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def open_folder(path: Path) -> tuple[bool, str]:
    """Open a folder in the system file manager."""
    if not path.exists():
        return False, f"Folder not found: {path}"
    try:
        if sys.platform == "darwin":
            subprocess.Popen(
                ["/usr/bin/open", str(path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True, ""
        elif sys.platform == "win32":
            # os.startfile is the right tool on Windows
            os.startfile(str(path))  # type: ignore[attr-defined]
            return True, ""
        else:
            opener = _which("xdg-open") or _which("gio")
            if not opener:
                return False, "No xdg-open found"
            subprocess.Popen(
                [opener, str(path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True, ""
    except Exception as e:
        return False, str(e)


def open_url(url: str) -> tuple[bool, str]:
    """Open URL in default browser."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["/usr/bin/open", url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "win32":
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            opener = _which("xdg-open")
            if not opener:
                return False, "No xdg-open found"
            subprocess.Popen([opener, url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, ""
    except Exception as e:
        return False, str(e)


def open_in_praat(wav: Path, textgrid: Optional[Path] = None) -> tuple[bool, str]:
    """Open a WAV (+ TextGrid) in Praat across platforms.

    macOS: try `praat` CLI first (Homebrew), else `open -a Praat <files>`.
    Windows: look up Praat.exe in PATH / Program Files; use it directly.
    Linux: `praat --open <wav> [<textgrid>]`.
    """
    if sys.platform == "darwin":
        praat = _which("praat")
        if praat:
            args = [praat, "--open", str(wav)]
            if textgrid and textgrid.exists():
                args.append(str(textgrid))
            try:
                subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True, ""
            except Exception as e:
                return False, str(e)
        # No CLI — hand off to /usr/bin/open with Praat.app
        files = [str(wav)]
        if textgrid and textgrid.exists():
            files.append(str(textgrid))
        try:
            subprocess.Popen(
                ["/usr/bin/open", "-a", "Praat"] + files,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True, ""
        except Exception as e:
            return False, (
                "Praat not found. Install Praat (https://praat.org) or "
                "`brew install praat` and try again.\n\n"
                f"Underlying error: {e}"
            )

    elif sys.platform == "win32":
        praat = _which("praat", "Praat", "praat.exe", "Praat.exe")
        if not praat:
            # Common install locations
            for cand in [
                Path(r"C:\Program Files\Praat\Praat.exe"),
                Path(r"C:\Program Files (x86)\Praat\Praat.exe"),
                Path.home() / "AppData/Local/Programs/Praat/Praat.exe",
            ]:
                if cand.exists():
                    praat = str(cand)
                    break
        if not praat:
            return False, (
                "Praat not found.\n\nDownload Praat from https://praat.org "
                "and either add it to PATH or install to its default location."
            )
        args = [praat, "--open", str(wav)]
        if textgrid and textgrid.exists():
            args.append(str(textgrid))
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, ""
        except Exception as e:
            return False, str(e)

    else:
        praat = _which("praat")
        if not praat:
            return False, "Praat not found in PATH"
        args = [praat, "--open", str(wav)]
        if textgrid and textgrid.exists():
            args.append(str(textgrid))
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, ""
        except Exception as e:
            return False, str(e)


# ============================================================================
# AUDIO RECORDER (per-platform)
# ============================================================================


class AudioRecorder:
    """Record from the default microphone to a 16 kHz mono WAV.

    Uses whichever capture stack is available on the host:
        macOS:    ffmpeg -f avfoundation -i :0
        Windows:  ffmpeg -f dshow  -i audio="..."   (auto-detected device)
        Linux:    ffmpeg -f pulse  -i default    (or arecord/parec)
    """

    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self.out_path: Optional[Path] = None
        self.started_at: Optional[float] = None

    @staticmethod
    def _list_dshow_audio_input() -> Optional[str]:
        """Find a usable DirectShow audio device name on Windows."""
        ffmpeg = _which("ffmpeg")
        if not ffmpeg:
            return None
        try:
            p = subprocess.run(
                [ffmpeg, "-hide_banner", "-list_devices", "true",
                 "-f", "dshow", "-i", "dummy"],
                capture_output=True, text=True, timeout=10,
            )
            text = (p.stderr or "") + (p.stdout or "")
        except Exception:
            return None
        # ffmpeg prints lines like:  [dshow @ 0x...] "Microphone (Realtek)" (audio)
        audio_devices = re.findall(r'"([^"]+)"\s*\(audio\)', text)
        if audio_devices:
            return audio_devices[0]
        return None

    def start(self, out_path: Path) -> tuple[bool, str]:
        self.out_path = out_path
        ffmpeg = _which("ffmpeg")

        if sys.platform == "darwin":
            if not ffmpeg:
                return False, (
                    "ffmpeg not found. Install it with `brew install ffmpeg`."
                )
            # ":0" = default audio device; "none:0" = no video + audio idx 0
            cmd = [
                ffmpeg, "-y",
                "-f", "avfoundation",
                "-i", ":0",
                "-ac", "1", "-ar", "16000",
                str(out_path),
            ]
        elif sys.platform == "win32":
            if not ffmpeg:
                return False, (
                    "ffmpeg not found. Install ffmpeg (winget install ffmpeg) "
                    "and reopen SpeechPrint."
                )
            device = self._list_dshow_audio_input()
            if not device:
                return False, "No DirectShow audio capture device detected."
            cmd = [
                ffmpeg, "-y",
                "-f", "dshow",
                "-i", f"audio={device}",
                "-ac", "1", "-ar", "16000",
                str(out_path),
            ]
        else:
            # Linux fallback path (kept for completeness; this file is the
            # cross-platform port, so the Linux GTK app has its own copy).
            arecord = _which("arecord")
            if ffmpeg:
                cmd = [
                    ffmpeg, "-y",
                    "-f", "pulse", "-i", "default",
                    "-ac", "1", "-ar", "16000",
                    str(out_path),
                ]
            elif arecord:
                cmd = [arecord, "-q", "-f", "S16_LE",
                       "-r", "16000", "-c", "1", str(out_path)]
            else:
                return False, "No audio capture tool found (ffmpeg or arecord)."

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.started_at = time.time()
            return True, ""
        except Exception as e:
            return False, str(e)

    def stop(self) -> tuple[bool, str]:
        if not self.proc:
            return False, "Not recording"
        try:
            # ffmpeg accepts 'q\n' on stdin to stop cleanly and finalise the WAV
            if self.proc.stdin is not None:
                try:
                    self.proc.stdin.write(b"q\n")
                    self.proc.stdin.flush()
                except Exception:
                    pass
            try:
                self.proc.wait(timeout=5)
                return True, ""
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
                return True, "Recorder force-stopped"
        except Exception as e:
            return False, str(e)
        finally:
            self.proc = None

    def elapsed(self) -> float:
        return (time.time() - self.started_at) if self.started_at else 0.0


# ============================================================================
# PIPELINE RUNNER
# ============================================================================


class _PipelineSignals(QObject):
    stage = pyqtSignal(int, int, str)
    line = pyqtSignal(str)
    done = pyqtSignal(int, object)  # rc, out_dir|None


class PipelineRunner:
    """Spawn `python -m speechprint_pkg.cli annotate …` and stream output."""

    def __init__(self, on_stage: Callable, on_line: Callable, on_done: Callable):
        self.signals = _PipelineSignals()
        self.signals.stage.connect(on_stage)
        self.signals.line.connect(on_line)
        self.signals.done.connect(on_done)
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._cancelled = False

    def run(self, wav: Path, language: str, output_dir: Path):
        # Prefer the venv python if SPEECHPRINT_ROOT is set.
        py = self._pick_python()
        cmd = [
            py, "-m", "speechprint_pkg.cli",
            "annotate", str(wav),
            "--language", language,
            "--output", str(output_dir),
        ]
        self._thread = threading.Thread(
            target=self._worker,
            args=(cmd, output_dir / wav.stem),
            daemon=True,
        )
        self._thread.start()

    def cancel(self):
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    @staticmethod
    def _pick_python() -> str:
        sp_root = os.environ.get("SPEECHPRINT_ROOT")
        if sp_root:
            if sys.platform == "win32":
                cand = Path(sp_root) / ".venv" / "Scripts" / "python.exe"
            else:
                cand = Path(sp_root) / ".venv" / "bin" / "python"
            if cand.exists():
                return str(cand)
        return sys.executable

    def _worker(self, cmd, expected_out_dir: Path):
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            self.signals.line.emit(f"✗ Failed to start pipeline: {e}")
            self.signals.done.emit(1, None)
            return

        stage_re = re.compile(r"^\[(\d+)/(\d+)\]\s+(.+)$")
        assert self._proc.stdout is not None
        for raw in self._proc.stdout:
            if self._cancelled:
                break
            line = raw.rstrip("\n")
            m = stage_re.match(line.strip())
            if m:
                num, total = int(m.group(1)), int(m.group(2))
                rest = m.group(3)
                name = rest.split(" — ", 1)[0]
                self.signals.stage.emit(num, total, name)
                self.signals.line.emit(line)
            else:
                self.signals.line.emit(line)

        rc = self._proc.wait()
        out_dir = expected_out_dir if expected_out_dir.exists() else None
        self.signals.done.emit(rc, out_dir)


# ============================================================================
# WORKSPACE WINDOW
# ============================================================================


PIPELINE_STAGES = [
    "Loading audio",
    "Transcribing speech with Whisper",
    "Preparing transcript for alignment",
    "Running forced alignment",
    "Extracting pitch, intensity, and formants",
    "Creating IPA / phone layer",
    "Creating symbolic prosody layer",
    "Writing Praat TextGrid",
    "Exporting CSV / ZIP",
]


FEEDBACK_FORM_URL = "https://forms.gle/speechprint-evaluation"


class ProjectWorkspace(QMainWindow):
    """Main project window."""

    def __init__(self, cfg, project_dir: Path):
        super().__init__()
        self.cfg = cfg
        self.project_dir = Path(project_dir).resolve()
        self.data_dir = self.project_dir / "data"
        self.out_dir = self.project_dir / "out"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.default_language = self._read_default_language()

        self.recorder = AudioRecorder()
        self._record_timer: Optional[QTimer] = None
        self.runner: Optional[PipelineRunner] = None
        self.selected_wav: Optional[Path] = None

        self.setWindowTitle(f"SpeechPrint — {self.project_dir.name}")
        self.resize(960, 700)

        self._build_ui()
        self.refresh_recordings()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QWidget()
        set_role(header, "headerbar")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(15, 8, 15, 8)
        h_layout.setSpacing(0)
        title = QLabel(self.project_dir.name)
        set_role(title, "section")
        subtitle = QLabel(str(self.project_dir))
        set_role(subtitle, "dim")
        h_layout.addWidget(title)
        h_layout.addWidget(subtitle)
        outer.addWidget(header)

        # Split panes
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(2)

        # --- LEFT pane -------------------------------------------------
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 6, 12)
        left_layout.setSpacing(8)

        section = QLabel("Recordings")
        set_role(section, "section")
        left_layout.addWidget(section)

        self.recordings_list = QListWidget()
        self.recordings_list.itemSelectionChanged.connect(self._on_row_selected)
        left_layout.addWidget(self.recordings_list, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        import_btn = QPushButton("Import Audio")
        import_btn.clicked.connect(self._on_import)
        action_row.addWidget(import_btn)
        self.record_btn = QPushButton("● Record")
        set_role(self.record_btn, "destructive")
        self.record_btn.clicked.connect(self._on_record_toggle)
        action_row.addWidget(self.record_btn)
        left_layout.addLayout(action_row)

        self.record_status = QLabel("")
        set_role(self.record_status, "dim")
        left_layout.addWidget(self.record_status)

        split.addWidget(left)

        # --- RIGHT pane ------------------------------------------------
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 12, 12, 12)
        right_layout.setSpacing(10)

        self.selected_label = QLabel("No recording selected")
        set_role(self.selected_label, "section")
        right_layout.addWidget(self.selected_label)

        # Language picker
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Language for this recording:"))
        self.lang_combo = QComboBox()
        self._lang_codes = list(self.cfg.supported_languages)
        for code in self._lang_codes:
            self.lang_combo.addItem(
                f"{self.cfg.language_names.get(code, code)} ({code})", code
            )
        try:
            self.lang_combo.setCurrentIndex(self._lang_codes.index(self.default_language))
        except ValueError:
            self.lang_combo.setCurrentIndex(0)
        lang_row.addWidget(self.lang_combo, 1)
        right_layout.addLayout(lang_row)

        # Run / cancel row
        run_row = QHBoxLayout()
        run_row.setSpacing(8)
        self.run_btn = QPushButton("Run Annotation")
        set_role(self.run_btn, "suggested")
        self.run_btn.clicked.connect(self._on_run_annotation)
        self.run_btn.setEnabled(False)
        run_row.addWidget(self.run_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel_pipeline)
        self.cancel_btn.setEnabled(False)
        run_row.addWidget(self.cancel_btn)
        right_layout.addLayout(run_row)

        # Open / Export row
        open_row = QHBoxLayout()
        open_row.setSpacing(8)
        self.praat_btn = QPushButton("Open in Praat")
        self.praat_btn.clicked.connect(self._on_open_in_praat)
        self.praat_btn.setEnabled(False)
        open_row.addWidget(self.praat_btn)
        self.folder_btn = QPushButton("Open Folder")
        self.folder_btn.clicked.connect(self._on_open_folder)
        self.folder_btn.setEnabled(False)
        open_row.addWidget(self.folder_btn)
        self.zip_btn = QPushButton("Export ZIP")
        self.zip_btn.clicked.connect(self._on_export_zip)
        self.zip_btn.setEnabled(False)
        open_row.addWidget(self.zip_btn)
        right_layout.addLayout(open_row)

        # Progress
        progress_section = QLabel("Annotation progress")
        set_role(progress_section, "section")
        right_layout.addWidget(progress_section)

        self.stage_labels: list[QLabel] = []
        progress_box = QFrame()
        pb_layout = QVBoxLayout(progress_box)
        pb_layout.setContentsMargins(8, 4, 8, 4)
        pb_layout.setSpacing(2)
        for i, name in enumerate(PIPELINE_STAGES, 1):
            lbl = QLabel(f"  ○  {i}. {name}")
            set_role(lbl, "dim")
            pb_layout.addWidget(lbl)
            self.stage_labels.append(lbl)
        right_layout.addWidget(progress_box)

        # Status line
        self.status_line = QLabel("")
        set_role(self.status_line, "status")
        right_layout.addWidget(self.status_line)

        # Technical log
        log_label = QLabel("Technical log")
        set_role(log_label, "dim")
        right_layout.addWidget(log_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        set_role(self.log_view, "log")
        self.log_view.setMinimumHeight(140)
        right_layout.addWidget(self.log_view, 1)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch(1)
        feedback_btn = QPushButton("Feedback Form")
        set_role(feedback_btn, "flat")
        feedback_btn.clicked.connect(lambda: open_url(FEEDBACK_FORM_URL))
        footer.addWidget(feedback_btn)
        right_layout.addLayout(footer)

        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        split.setSizes([330, 600])

        outer.addWidget(split, 1)
        self.setCentralWidget(root)

    # ----------------------------------------------------------- corpus.toml

    def _read_default_language(self) -> str:
        toml = self.project_dir / "corpus.toml"
        if not toml.exists():
            return self.cfg.default_language
        try:
            for line in toml.read_text(encoding="utf-8").splitlines():
                m = re.match(r"\s*language\s*=\s*[\"']([^\"']+)[\"']", line)
                if m:
                    return m.group(1).strip()
        except Exception:
            pass
        return self.cfg.default_language

    # ----------------------------------------------------------- recordings

    def refresh_recordings(self):
        self.recordings_list.clear()
        wavs = sorted(
            p for p in self.data_dir.glob("*.wav")
            if p.is_file() and not p.name.startswith(".")
        )
        if not wavs:
            item = QListWidgetItem(
                "\nNo recordings yet.\n\nUse Import Audio or ● Record to add one.\n"
            )
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.recordings_list.addItem(item)
            return

        for wav in wavs:
            annotated = (self.out_dir / wav.stem / f"{wav.stem}.TextGrid").exists()
            mark = "✓" if annotated else "○"
            status = "Annotated" if annotated else "Not yet annotated"
            label = f"  {mark}    {wav.name}\n       {status}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(wav))
            self.recordings_list.addItem(item)

    def _reselect_current(self):
        if not self.selected_wav:
            return
        for i in range(self.recordings_list.count()):
            item = self.recordings_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and Path(data) == self.selected_wav:
                self.recordings_list.setCurrentRow(i)
                return

    def _on_row_selected(self):
        items = self.recordings_list.selectedItems()
        if not items:
            self.selected_wav = None
            self.selected_label.setText("No recording selected")
            self.run_btn.setEnabled(False)
            self.praat_btn.setEnabled(False)
            self.folder_btn.setEnabled(False)
            self.zip_btn.setEnabled(False)
            return
        data = items[0].data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        wav = Path(data)
        self.selected_wav = wav
        self.selected_label.setText(wav.name)
        self.run_btn.setEnabled(True)
        annotated = (self.out_dir / wav.stem / f"{wav.stem}.TextGrid").exists()
        self.praat_btn.setEnabled(annotated)
        self.folder_btn.setEnabled(annotated)
        self.zip_btn.setEnabled(annotated)

    # --------------------------------------------------------------- import

    def _on_import(self):
        patterns = "Audio files (*.wav *.WAV *.mp3 *.MP3 *.flac *.FLAC *.ogg *.OGG *.m4a *.M4A *.aac *.AAC *.opus *.OPUS)"
        path, _ = QFileDialog.getOpenFileName(
            self, "Import audio file", str(Path.home()), patterns
        )
        if not path:
            return
        self._import_audio_file(Path(path))

    def _import_audio_file(self, src: Path):
        if not src.exists():
            self._error("Source file not found")
            return

        target_name = _safe_filename(src.stem) + ".wav"
        target = self.data_dir / target_name
        if target.exists():
            target = self.data_dir / _next_recording_name(
                self.data_dir, prefix=src.stem
            )

        if src.suffix.lower() == ".wav":
            try:
                shutil.copy2(src, target)
                self._info(f"Imported {target.name}")
                self.refresh_recordings()
                return
            except Exception as e:
                self._error(f"Import failed: {e}")
                return

        ffmpeg = _which("ffmpeg")
        if not ffmpeg:
            self._error(
                "Imported file is not WAV and ffmpeg isn't available to convert."
            )
            return

        try:
            subprocess.run(
                [ffmpeg, "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(target)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._info(f"Imported and converted {target.name}")
            self.refresh_recordings()
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b"").decode(errors="replace")[:400]
            self._error(f"ffmpeg conversion failed:\n{err}")

    # --------------------------------------------------------------- record

    def _on_record_toggle(self):
        if self.recorder.proc is None:
            name = _next_recording_name(self.data_dir)
            target = self.data_dir / name
            ok, err = self.recorder.start(target)
            if not ok:
                self._error(f"Recording failed: {err}")
                return
            self.record_btn.setText("■ Stop")
            self.record_status.setText(f"Recording → {name}")
            if self._record_timer is None:
                self._record_timer = QTimer(self)
                self._record_timer.setInterval(500)
                self._record_timer.timeout.connect(self._tick_record_status)
            self._record_timer.start()
        else:
            ok, msg = self.recorder.stop()
            self.record_btn.setText("● Record")
            if self._record_timer:
                self._record_timer.stop()
            saved = self.recorder.out_path.name if self.recorder.out_path else ""
            self.record_status.setText(f"Saved {saved}")
            self.refresh_recordings()

    def _tick_record_status(self):
        if self.recorder.proc is None:
            return
        sec = int(self.recorder.elapsed())
        name = self.recorder.out_path.name if self.recorder.out_path else ""
        self.record_status.setText(f"Recording → {name}  ({sec}s)")

    # ----------------------------------------------------------- annotate

    def _on_run_annotation(self):
        if not self.selected_wav:
            return

        for lbl in self.stage_labels:
            text = lbl.text()
            text = re.sub(r"^\s*[●✓○]\s*", "  ○  ", text)
            lbl.setText(text)
            set_role(lbl, "dim")

        self.status_line.setText("Starting…")
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.log_view.clear()

        idx = self.lang_combo.currentIndex()
        if 0 <= idx < len(self._lang_codes):
            lang = self._lang_codes[idx]
        else:
            lang = self.default_language

        self.runner = PipelineRunner(
            on_stage=self._on_pipeline_stage,
            on_line=self._append_log,
            on_done=self._on_pipeline_done,
        )
        self.runner.run(self.selected_wav, lang, self.out_dir)

    def _on_cancel_pipeline(self):
        if self.runner:
            self.runner.cancel()
            self.status_line.setText("Cancelling…")

    def _on_pipeline_stage(self, num: int, total: int, name: str):
        for i, lbl in enumerate(self.stage_labels, 1):
            text = lbl.text()
            stripped = re.sub(r"^\s*[●✓○]\s*\d+\.\s*", "", text)
            stage_name = stripped
            if i < num:
                marker = "✓"
                set_role(lbl, "success")
            elif i == num:
                marker = "●"
                set_role(lbl, "status")
            else:
                marker = "○"
                set_role(lbl, "dim")
            lbl.setText(f"  {marker}  {i}. {stage_name}")
        self.status_line.setText(f"Step {num} of {total}: {name}")

    def _append_log(self, text: str):
        self.log_view.appendPlainText(text)
        # Auto-scroll
        sb = self.log_view.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _on_pipeline_done(self, rc: int, out_dir):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if rc == 0 and out_dir is not None:
            for i, lbl in enumerate(self.stage_labels, 1):
                text = lbl.text()
                stripped = re.sub(r"^\s*[●✓○]\s*\d+\.\s*", "", text)
                lbl.setText(f"  ✓  {i}. {stripped}")
                set_role(lbl, "success")
            self.status_line.setText("✓ Annotation complete")
            self._success_dialog(out_dir)
            self.refresh_recordings()
            self._reselect_current()
        else:
            self.status_line.setText(f"✗ Pipeline exited with code {rc}")

    def _success_dialog(self, out_dir: Path):
        box = QMessageBox(self)
        box.setWindowTitle("Annotation complete")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText("Annotation complete.")
        box.setInformativeText(
            f"Created in {out_dir.name}/:\n"
            "  ✓ Praat TextGrid (6 tiers)\n"
            "  ✓ Words, syllables, phonemes\n"
            "  ✓ Prosody summary\n"
            "  ✓ CSV exports"
        )
        praat_btn = box.addButton("Open in Praat", QMessageBox.ButtonRole.AcceptRole)
        folder_btn = box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        zip_btn = box.addButton("Export ZIP", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(praat_btn)
        box.exec()
        clicked = box.clickedButton()
        wav = out_dir / f"{out_dir.name}.wav"
        if not wav.exists():
            wav = self.selected_wav  # fall back to source
        textgrid = out_dir / f"{out_dir.name}.TextGrid"
        if clicked is praat_btn:
            ok, err = open_in_praat(wav, textgrid)
            if not ok:
                self._error(err)
        elif clicked is folder_btn:
            ok, err = open_folder(out_dir)
            if not ok:
                self._error(err)
        elif clicked is zip_btn:
            self._export_zip(out_dir)

    # ---------------------------------------------------- open / export

    def _on_open_in_praat(self):
        if not self.selected_wav:
            return
        out_dir = self.out_dir / self.selected_wav.stem
        textgrid = out_dir / f"{self.selected_wav.stem}.TextGrid"
        wav_for_praat = out_dir / f"{self.selected_wav.stem}.wav"
        if not wav_for_praat.exists():
            wav_for_praat = self.selected_wav
        ok, err = open_in_praat(wav_for_praat, textgrid)
        if not ok:
            self._error(err)

    def _on_open_folder(self):
        if not self.selected_wav:
            return
        out_dir = self.out_dir / self.selected_wav.stem
        if not out_dir.exists():
            out_dir = self.project_dir
        ok, err = open_folder(out_dir)
        if not ok:
            self._error(err)

    def _on_export_zip(self):
        if not self.selected_wav:
            return
        out_dir = self.out_dir / self.selected_wav.stem
        if not out_dir.exists():
            self._error("Run annotation first to create an output folder to zip.")
            return
        self._export_zip(out_dir)

    def _export_zip(self, out_dir: Path):
        try:
            py = PipelineRunner._pick_python()
            cmd = [py, "-m", "speechprint_pkg.cli", "export-zip", str(out_dir)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                zip_path = out_dir.parent / f"{out_dir.name}.zip"
                self._info(f"Exported {zip_path.name}")
                open_folder(zip_path.parent)
            else:
                self._error(
                    f"Export failed:\n{result.stderr or result.stdout}"
                )
        except Exception as e:
            self._error(f"Export error: {e}")

    # --------------------------------------------------------- notifications

    def _info(self, message: str):
        self.status_line.setText(message)

    def _error(self, message: str):
        QMessageBox.critical(self, "SpeechPrint", str(message))
