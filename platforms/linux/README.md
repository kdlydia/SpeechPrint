# SpeechPrint

Linguistic annotation and prosody analysis environment.

Drop a WAV in, get a Praat TextGrid out.

SpeechPrint combines:

* forced alignment
* phoneme extraction
* IPA annotation
* symbolic prosody analysis
* corpus workflows
* Praat interoperability
* comparative aligner evaluation

into a unified research-oriented pipeline.

---

# Quick Start

## Linux

Install and launch:

```bash id="mbz8pv"
cd platforms/linux
export SPEECHPRINT_ROOT="$PWD"
uv run python -m lib.main
```

SpeechPrint opens in workspace mode with:

* Import Audio
* Record Audio
* Run Annotation
* Open in Praat
* Export ZIP

---

# Installation

SpeechPrint currently targets Linux as the primary validated platform.

The installer automates:

* dependency installation
* WhisperX setup
* MFA setup
* Gentle setup
* Praat integration
* project creation
* corpus generation

## Linux Installer

Download the latest Linux release from:

[SpeechPrint Releases](https://github.com/kdlydia/SpeechPrint/releases)

Launch:

```bash id="agjlwm"
uv run python -m lib.main
```

Choose:

* **Install SpeechPrint** — first-time setup
* **New Project / Corpus** — create a new annotation workspace

The installer configures:

* WhisperX
* Montreal Forced Aligner (MFA)
* Gentle
* Parselmouth
* Praat interoperability
* Python dependencies
* project templates

---

# Annotation Output

Each annotated recording produces:

## Praat TextGrid

Main tiers:

1. `words_selected`
2. `syllables`
3. `phonemes`
4. `f0_pitch`
5. `prosody_labels`
6. `warnings_review`

Optional comparison tiers:

* `words_whisperx`
* `words_mfa`
* `words_gentle`
* `words_crisperwhisper`

when comparative alignment is enabled.

---

# Export Structure

```text id="k4rjca"
recording_name/
├── recording.wav
├── recording.TextGrid
├── recording.master_emet.TextGrid
├── words.csv
├── syllables.csv
├── phonemes.csv
├── prosody.csv
├── recording.json
├── warnings.json
├── LOG.txt
└── aligners/
    ├── comparison.csv
    ├── selected_aligners.TextGrid
    ├── recording.whisperx.TextGrid
    ├── recording.mfa.TextGrid
    ├── recording.gentle.TextGrid
    └── recording.crisperwhisper.TextGrid
```

---

# Alignment Systems

SpeechPrint supports:

| Aligner        | Purpose                         |
| -------------- | ------------------------------- |
| WhisperX       | Fast neural alignment           |
| MFA            | High-precision forced alignment |
| Gentle         | Lightweight fallback alignment  |
| CrisperWhisper | Experimental Whisper refinement |

Comparative mode allows multiple aligners to run simultaneously and exports timing comparisons as CSV and TextGrid layers.

---

# Symbolic Prosody

SpeechPrint generates symbolic prosody tiers using Parselmouth-derived measurements including:

* F0 movement
* semitone excursion
* velocity
* intensity
* prominence
* harmonicity
* temporal positioning

Symbols include:

* `/` rising pitch
* `\` falling pitch
* `–` high level pitch
* `_` low level pitch
* `*` prominence marking

The symbolic layer is adaptive and measurement-derived rather than rule-only.

---

# Platforms

| Platform | Status      |
| -------- | ----------- |
| Linux    | Stable      |
| macOS    | In Progress |
| Windows  | In Progress |

Linux currently serves as the reference implementation.

---

# Documentation

* [Linux Guide](platforms/linux/README.md)
* [macOS Guide](platforms/macos/README.md)
* [Windows Guide](platforms/windows/README.md)

---

# License

GPL-3.0 — see LICENSE.
