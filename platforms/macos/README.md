# SpeechPrint — macOS

Linguistic annotation toolchain. Drop a WAV in, get a Praat TextGrid out.

## Quick start

```bash
cd macos
./SpeechPrint
```

The launcher opens a two-button window: **Install SpeechPrint** (one-time
setup via Homebrew + uv) and **New Project / Corpus**. After creating a
project, the workspace opens with **Import Audio**, **● Record**,
**Run Annotation**, **Open in Praat**, and **Export ZIP**.

If you'd rather use the command line:

```bash
./SpeechPrint new MyCorpus ~/Corpora/ --language en
./SpeechPrint annotate ~/Corpora/MyCorpus/data/recording.wav --language en
```

## Prerequisites

- macOS 14 (Sonoma) or later
- Internet connection (the installer downloads Homebrew packages, MFA
  models, and Python deps)
- ~5 GB free disk space
- Python 3.11+ with PyQt6 — the installer takes care of this. If you want
  to skip the installer you can run `pip install PyQt6` against your own
  Python and double-click `SpeechPrint` directly.

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

## What the installer does

1. Installs **Homebrew** if it's missing
2. `brew install python@3.11 ffmpeg git espeak-ng portaudio`
   and `brew install --cask praat`
3. Installs **uv** (fast Python package manager)
4. Creates a venv at `~/SpeechPrint/.venv` and installs PyQt6, the
   SpeechPrint pipeline, WhisperX, torch, parselmouth, phonemizer, MFA, …
5. Downloads MFA acoustic models + dictionaries for every language module
   you checked (English by default; ~300 MB each)
6. Appends a `# >>> SpeechPrint <<<` block to `~/.zshrc` so the venv
   activates in new terminals

## Layout

```
macos/
├── SpeechPrint                     ← launcher (no args = GUI, args = CLI)
├── speechprint-config.json         ← single source of truth for paths
├── bin/
│   └── speechprint-run             ← batch-annotate a folder of WAVs
├── lib/
│   ├── main.py                     ← Qt mode selector
│   ├── cli.py                      ← argparse + passthrough to pipeline
│   ├── config.py                   ← path resolution
│   ├── modes/{installation,corpus,project}.py
│   ├── ui/{theme.py, dark.qss}
│   ├── scripts/{install_deps.sh, create_corpus.sh}
│   └── templates/{corpus.toml, README.md, gitignore, vscode/}
└── resources/speechprint.png
```

## Notes / honesty about the current pipeline

- **Word timing**: WhisperX `align()` when available; otherwise
  segment-proportional or equal-width — a warning is written into the
  TextGrid's `warnings_review` tier when that happens.
- **Phonemes**: phonemizer + espeak-ng. Timing is distributed
  proportionally inside each syllable — not yet MFA-grade phone alignment.
- **Syllables**: proportional to phone count inside word intervals.
- **Prosody labels**: automatic symbolic estimate; thresholds adaptive
  (≥3 ST and ≥0.75× std-dev of the recording).

The Mac and Linux builds share the same `speechprint_pkg` pipeline backend
— differences are confined to the launcher, the GUI toolkit (Qt vs GTK),
and the install scripts.
