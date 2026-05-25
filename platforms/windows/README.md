# SpeechPrint — Windows

Linguistic annotation toolchain. Drop a WAV in, get a Praat TextGrid out.

## Quick start

In PowerShell or Command Prompt:

```
cd windows
.\SpeechPrint.bat
```

Or simply double-click `SpeechPrint.bat`.

The launcher opens a two-button window: **Install SpeechPrint** (one-time
setup via winget + uv) and **New Project / Corpus**. After creating a
project, the workspace opens with **Import Audio**, **● Record**,
**Run Annotation**, **Open in Praat**, and **Export ZIP**.

CLI usage:

```
.\SpeechPrint.bat new MyCorpus C:\Users\me\Corpora --language en
.\SpeechPrint.bat annotate C:\Users\me\Corpora\MyCorpus\data\recording.wav --language en
```

## Prerequisites

- Windows 10 (1809 or later) or Windows 11
- **winget** — built into Win10 1809+ / Win11. If you're on an older
  Windows you can install it from the Microsoft Store ("App Installer").
- PowerShell 5.1+ (built into Windows)
- Internet connection (the installer downloads system packages, MFA
  models, and Python deps)
- ~5 GB free disk space

If winget is unavailable, install these manually before running the
installer:

- Python 3.11 — https://python.org/downloads/
- ffmpeg — https://ffmpeg.org/download.html (add `bin\` to PATH)
- git — https://git-scm.com/download/win
- Praat — https://praat.org/

## What the installer does

1. `winget install Python.Python.3.11 Gyan.FFmpeg Git.Git PraatProject.Praat`
2. Installs **uv** (fast Python package manager)
3. Creates a venv at `%USERPROFILE%\SpeechPrint\.venv` and installs PyQt6,
   the SpeechPrint pipeline, WhisperX, torch, parselmouth, phonemizer,
   MFA, …
4. Downloads MFA acoustic models + dictionaries for the languages you
   checked (English by default; ~300 MB each)
5. Sets persistent user environment variables so new terminals see
   `SPEECHPRINT_ROOT`, `MFA_ROOT_DIR`, `WHISPERX_MODEL`, and the venv
   `Scripts\` directory on `PATH`

> Close and reopen any open terminals after install so the new env vars
> take effect.

## Output

Each annotated recording produces a Praat TextGrid with six tiers:

1. `words`
2. `syllables`
3. `phonemes` (IPA)
4. `f0_pitch` (mean Hz per syllable)
5. `prosody_labels` (`/` `\` `–`, strongest accent prefixed with `*`)
6. `warnings_review` (`ok` unless something fell back)

Plus `words.csv`, `syllables.csv`, `phonemes.csv`, `prosody.csv`,
`<recording>.json`, `warnings.json`, `LOG.txt`.

## Layout

```
windows\
├── SpeechPrint.bat                 ← launcher (no args = GUI, args = CLI)
├── speechprint-config.json         ← single source of truth for paths
├── lib\
│   ├── main.py                     ← Qt mode selector
│   ├── cli.py                      ← argparse + passthrough to pipeline
│   ├── config.py                   ← path resolution
│   ├── modes\{installation,corpus,project}.py
│   ├── ui\{theme.py, dark.qss}
│   ├── scripts\{install_deps.ps1, create_corpus.ps1}
│   └── templates\{corpus.toml, README.md, gitignore, vscode\}
└── resources\speechprint.png
```

## Recording on Windows

The workspace records via DirectShow (`ffmpeg -f dshow`). The auto-detect
picks the first audio input device ffmpeg sees. If you need a different
microphone, set it as the Windows default input device (Settings → Sound
→ Input).

## Notes / honesty about the current pipeline

- **Word timing**: WhisperX `align()` when available; otherwise
  segment-proportional or equal-width — a warning is written into the
  TextGrid's `warnings_review` tier when that happens.
- **Phonemes**: phonemizer + espeak-ng. Timing is distributed
  proportionally inside each syllable — not yet MFA-grade phone
  alignment.
- **Syllables**: proportional to phone count inside word intervals.
- **Prosody labels**: automatic symbolic estimate; thresholds adaptive
  (≥3 ST and ≥0.75× std-dev of the recording).

The Windows, Mac, and Linux builds share the same `speechprint_pkg`
pipeline backend — differences are confined to the launcher, the GUI
toolkit (Qt vs GTK), and the install scripts.
