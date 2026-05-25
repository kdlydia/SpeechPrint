#!/bin/bash
# SpeechPrint - Corpus Creator for Linux
# Creates new SpeechPrint corpora from embedded templates

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

SPEECHPRINT_ROOT="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"

if [ -n "${SPEECHPRINT_TEMPLATE_DIR:-}" ] && [ -d "$SPEECHPRINT_TEMPLATE_DIR" ]; then
    TEMPLATES_DIR="$SPEECHPRINT_TEMPLATE_DIR"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    TEMPLATES_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")/templates"
fi

# ============================================================================
# UTILITIES
# ============================================================================

usage() {
    cat <<EOF
SpeechPrint - Corpus Creator

Usage:
  speechprint new <corpus-name> [destination-dir] [options]
  speechprint --help

Examples:
  speechprint new FieldRecordings ~/Corpora/
  speechprint new MyCorpus . --language it

Options:
  --language <code>  Default corpus language (en, de, it, es, fr, cs)
  --no-vscode        Skip VS Code configuration
  --auto-ensemble    Run ensemble aggregation after each annotate
  --help             Show this help

Environment Variables:
  SPEECHPRINT_ROOT   Override SpeechPrint installation location
                     (default: \$HOME/SpeechPrint)
EOF
    exit 0
}

error() {
    echo "[SpeechPrint ERROR] $*" >&2
    exit 1
}

log() {
    echo "[SpeechPrint] $*"
}

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

[ "$#" -eq 0 ] && usage

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    usage
fi

if [ "$1" != "new" ]; then
    error "Unknown command: $1. Use 'speechprint new <name>'"
fi

shift
CORPUS_NAME="${1:-}"
DEST_DIR="${2:-.}"
LANGUAGE="en"
WITH_VSCODE=true
AUTO_ENSEMBLE=false

shift 2 2>/dev/null || true

while [ "$#" -gt 0 ]; do
    case "$1" in
    --language)
        shift
        LANGUAGE="${1:-en}"
        ;;
    --no-vscode)
        WITH_VSCODE=false
        ;;
    --auto-ensemble)
        AUTO_ENSEMBLE=true
        ;;
    *)
        error "Unknown option: $1"
        ;;
    esac
    shift
done

# ============================================================================
# VALIDATION
# ============================================================================

[ -z "$CORPUS_NAME" ] && error "Corpus name required"

DEST_DIR="${DEST_DIR/#\~/$HOME}"

mkdir -p "$DEST_DIR" || error "Cannot create destination directory: $DEST_DIR"
DEST_DIR="$(cd "$DEST_DIR" && pwd)"

CORPUS_DIR="$DEST_DIR/$CORPUS_NAME"

if [ -d "$CORPUS_DIR" ]; then
    if [ -f "$CORPUS_DIR/corpus.toml" ]; then
        log "Corpus '$CORPUS_NAME' already exists at $CORPUS_DIR."
        log "Nothing to do."
        exit 0
    else
        error "Directory already exists and is not a SpeechPrint corpus: $CORPUS_DIR"
    fi
fi

# ============================================================================
# CHECK TEMPLATES
# ============================================================================

if [ ! -d "$TEMPLATES_DIR" ]; then
    error "Templates not found at $TEMPLATES_DIR"
fi

REQUIRED_TEMPLATES=(
    "corpus.toml"
    "README.md"
    "gitignore"
)

for template in "${REQUIRED_TEMPLATES[@]}"; do
    if [ ! -f "$TEMPLATES_DIR/$template" ]; then
        error "Required template missing: $template at $TEMPLATES_DIR/$template"
    fi
done

# ============================================================================
# CREATE CORPUS STRUCTURE
# ============================================================================

log "Creating corpus: $CORPUS_NAME"
mkdir -p "$CORPUS_DIR/data"
mkdir -p "$CORPUS_DIR/out"
touch "$CORPUS_DIR/data/.gitkeep"
touch "$CORPUS_DIR/out/.gitkeep"

if [ "$WITH_VSCODE" = true ]; then
    mkdir -p "$CORPUS_DIR/.vscode"
    log "  ✓ Created .vscode directory"
fi

log "  ✓ Created corpus structure"

# ============================================================================
# GENERATE corpus.toml
# ============================================================================

log "Generating corpus.toml"

if [ "$AUTO_ENSEMBLE" = true ]; then
    AUTO_ENSEMBLE_VAL="true"
else
    AUTO_ENSEMBLE_VAL="false"
fi

sed \
    -e "s|@CORPUS_NAME@|$CORPUS_NAME|g" \
    -e "s|@LANGUAGE@|$LANGUAGE|g" \
    -e "s|@AUTO_ENSEMBLE@|$AUTO_ENSEMBLE_VAL|g" \
    "$TEMPLATES_DIR/corpus.toml" > "$CORPUS_DIR/corpus.toml"

log "  ✓ Generated corpus.toml (default language: $LANGUAGE)"

# ============================================================================
# CREATE VS CODE CONFIGURATION (if enabled)
# ============================================================================

if [ "$WITH_VSCODE" = true ]; then
    if [ -d "$TEMPLATES_DIR/vscode" ]; then
        log "Generating VS Code configuration"

        for vscode_file in settings.json tasks.json launch.json; do
            if [ -f "$TEMPLATES_DIR/vscode/$vscode_file" ]; then
                sed \
                    -e "s|@CORPUS_NAME@|$CORPUS_NAME|g" \
                    -e "s|@LANGUAGE@|$LANGUAGE|g" \
                    "$TEMPLATES_DIR/vscode/$vscode_file" \
                    > "$CORPUS_DIR/.vscode/$vscode_file"
            fi
        done

        log "  ✓ Generated VS Code configuration"
    else
        log "  ⚠ VS Code templates not found, skipping"
    fi
fi

# ============================================================================
# CREATE .GITIGNORE
# ============================================================================

log "Generating .gitignore"
cp "$TEMPLATES_DIR/gitignore" "$CORPUS_DIR/.gitignore"
log "  ✓ Generated .gitignore"

# ============================================================================
# CREATE README
# ============================================================================

log "Generating README.md"

sed \
    -e "s|@CORPUS_NAME@|$CORPUS_NAME|g" \
    -e "s|@LANGUAGE@|$LANGUAGE|g" \
    "$TEMPLATES_DIR/README.md" > "$CORPUS_DIR/README.md"

log "  ✓ Generated README.md"

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
echo "=========================================="
echo "  ✓ Corpus '$CORPUS_NAME' created!"
echo "=========================================="
echo ""
echo "Location: $CORPUS_DIR"
echo "Default language: $LANGUAGE"
echo ""
echo "Next steps:"
echo "  1. cd $CORPUS_DIR"
echo "  2. Drop WAV files in data/"

if [ "$WITH_VSCODE" = true ]; then
    echo "  3. code .                    # Open in VS Code"
    echo "  4. speechprint annotate data/<file>.wav --language $LANGUAGE"
else
    echo "  3. speechprint annotate data/<file>.wav --language $LANGUAGE"
fi

echo "  5. speechprint ensemble"
echo ""
echo "Documentation: https://github.com/SpeechPrint/SpeechPrint"
echo ""

exit 0
