# @CORPUS_NAME@

SpeechPrint project. Default language: **@LANGUAGE@** (per-file override allowed).

## Use

Open SpeechPrint, choose **New Project / Corpus** or pass this folder on the
command line:

```bash
SpeechPrint @CORPUS_NAME@/
```

Or from the terminal:

```bash
speechprint annotate data/<recording>.wav --language @LANGUAGE@
speechprint ensemble --root .
```

## Output (per recording)

`out/<recording>/` containing a 6-tier Praat TextGrid
(`words`, `syllables`, `phonemes`, `f0_pitch`, `prosody_labels`,
`warnings_review`), plus `words.csv`, `syllables.csv`, `phonemes.csv`,
`prosody.csv`, `warnings.json`, `LOG.txt`.
