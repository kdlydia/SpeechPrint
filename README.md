# SpeechPrint

SpeechPrint provides a unified environment for the analysis, annotation, and exploration of spoken language through computational, phonetic, and perceptual frameworks.

Rather than treating transcription, alignment, prosody, and symbolic representation as isolated stages, SpeechPrint approaches them as interconnected layers operating over the same temporal substrate.

At its core, SpeechPrint is not simply a forced-alignment utility or annotation interface. It is an infrastructural framework for examining how language behaves as acoustic material: simultaneously symbolic, physiological, temporal, and spectral. Pitch movement, phoneme structure, syllabic rhythm, intensity, and linguistic segmentation are treated not as separate domains requiring translation between tools, but as different analytical views over the same evolving signal.

SpeechPrint combines:

* forced alignment
* phonetic analysis
* IPA extraction
* symbolic prosody modeling
* corpus management
* recording workflows
* Praat interoperability
* comparative aligner evaluation

into a single research-oriented environment.

The system integrates multiple alignment backends including WhisperX, MFA, Gentle, and CrisperWhisper, allowing researchers to compare timing behavior across systems while maintaining a unified annotation structure.

---

# Architecture

SpeechPrint operates through layered analysis rather than isolated tooling.

A single recording may simultaneously contain:

* waveform structure
* spectral information
* pitch trajectories
* syllabic segmentation
* phoneme segmentation
* symbolic prosodic abstraction
* multi-aligner word timings

all synchronized within a shared temporal representation exported directly into Praat TextGrid structures.

Rather than converting between incompatible tools and formats, SpeechPrint treats annotation layers as composable analytical views over the same acoustic signal.

---

# Weave

SpeechPrint includes a management and project environment called **Weave**.

Weave automates:

* dependency installation
* project creation
* corpus generation
* recording workflows
* alignment execution
* export pipelines
* Praat integration
* cross-platform setup

across Linux, macOS, and Windows.

Rather than functioning as a conventional GUI wrapper, Weave acts as an orchestration layer between computational analysis, annotation infrastructure, and research-oriented workflows.

---

# Features

## Analysis

* Multi-aligner forced alignment
* IPA / phoneme extraction
* Syllable segmentation
* Symbolic prosody analysis
* F0 extraction
* Intensity analysis
* Formant analysis
* CSV + JSON export
* Comparative aligner evaluation

## Annotation

* Praat TextGrid export
* Multi-tier annotation generation
* Canonical analysis tiers
* Aligner comparison tiers
* Symbolic prosody tiers
* IPA + syllable layers

## Workflow

* Integrated recording
* Corpus project management
* Automated export structure
* GUI + CLI workflows
* Batch processing
* Cross-platform project portability

---

# Design Philosophy

SpeechPrint is built around the idea that language should not be treated purely as text.

Speech exists simultaneously as:

* acoustic structure
* embodied gesture
* symbolic system
* temporal behavior
* spectral material
* compositional form

Traditional tooling often separates these perspectives into disconnected software environments. SpeechPrint instead attempts to unify them into a shared analytical infrastructure.

The goal is not merely transcription accuracy.

The goal is to create a computational environment where linguistic structure, sonic material, annotation, and symbolic interpretation can coexist within the same workflow.

---

# Quick Start

## GUI

```bash
uv run python -m lib.main
```

## CLI

```bash
uv run python -m speechprint_pkg.cli annotate input.wav --language en
```

---

# Supported Aligners

| Aligner        | Purpose                         |
| -------------- | ------------------------------- |
| WhisperX       | Fast neural alignment           |
| MFA            | High-precision forced alignment |
| Gentle         | Lightweight alignment           |
| CrisperWhisper | Experimental Whisper refinement |

SpeechPrint can compare aligners simultaneously and export combined evaluation TextGrids and CSV reports.

---

# Output

SpeechPrint exports:

* Praat TextGrids
* CSV tables
* JSON manifests
* comparison reports
* IPA tiers
* symbolic prosody layers
* aligner evaluation data

---

# Platform Support

| Platform | Status      |
| -------- | ----------- |
| Linux    | Stable      |
| macOS    | In Progress |
| Windows  | In Progress |

Linux currently serves as the reference implementation.

---

# Intended Use

SpeechPrint is intended for:

* phonetic research
* speech analysis
* linguistic annotation
* corpus creation
* artistic research
* computational linguistics
* prosody research
* speech technology experimentation
* multilingual archival workflows

---

# Repository

For installation details, releases, and updates:

[SpeechPrint Repository](https://github.com/opensourceartwork/SpeechPrint?utm_source=chatgpt.com)
