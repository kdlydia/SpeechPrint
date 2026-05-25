#!/usr/bin/env bash
# SpeechPrint - Dependency installer for macOS
#
# Installs system packages (via Homebrew), the Python toolchain (via uv),
# and MFA acoustic models. Takes two positional args from the GUI:
#
#   $1   release type   (stable | dev)        default: stable
#   $2   languages csv  (en,de,it,…)          default: en
#
# Designed to match the Linux installer 1:1 in behaviour and output.

set -e

RELEASE_TYPE="${1:-stable}"
LANGUAGES_CSV="${2:-en}"

# ============================================================================
# UTILITIES
# ============================================================================

# macOS native dialog via AppleScript — used when the GUI launched us and
# we need to prompt for a sudo password or show an info dialog.
osa_password_prompt() {
    osascript <<'EOF' 2>/dev/null || true
display dialog "SpeechPrint Installer requires administrator privileges.

Please enter your password:" default answer "" with hidden answer ¬
    with title "SpeechPrint Installer" buttons {"Cancel", "OK"} default button "OK"
return text returned of result
EOF
}

osa_info() {
    local title="$1"
    local message="$2"
    osascript <<EOF 2>/dev/null || true
display dialog "$message" with title "$title" buttons {"OK"} default button "OK"
EOF
}

get_sudo_password() {
    local password=""
    if [[ -t 0 ]]; then
        echo "SpeechPrint Installer requires administrator privileges." >&2
        read -rsp "Password: " password
        echo "" >&2
    else
        password=$(osa_password_prompt)
    fi
    echo "$password"
}

run_with_sudo() {
    if [[ $EUID -eq 0 ]]; then
        "$@"
    else
        if [[ -z "${SUDO_PASSWORD+x}" ]]; then
            SUDO_PASSWORD=$(get_sudo_password)
            if ! echo "$SUDO_PASSWORD" | sudo -S -v 2>/dev/null; then
                echo "ERROR: Incorrect password. Please run the installer again." >&2
                exit 1
            fi
            export SUDO_PASSWORD
        fi
        echo "$SUDO_PASSWORD" | sudo -S "$@"
    fi
}

show_welcome() {
    osa_info "SpeechPrint Installer" \
        "Welcome to SpeechPrint Installer!\n\nThis installer will set up the SpeechPrint annotation toolchain.\n\nYou may be asked for your password to install system packages via Homebrew."
}

# ============================================================================
# HOMEBREW (system package manager on macOS)
# ============================================================================

ensure_homebrew() {
    if command -v brew &>/dev/null; then
        echo "✓ Homebrew already installed: $(brew --version | head -1)"
        return 0
    fi

    # Apple-silicon vs Intel default install path
    for cand in /opt/homebrew/bin/brew /usr/local/bin/brew; do
        if [[ -x "$cand" ]]; then
            export PATH="$(dirname "$cand"):$PATH"
            if command -v brew &>/dev/null; then
                echo "✓ Found Homebrew at $cand"
                return 0
            fi
        fi
    done

    echo "Installing Homebrew (this can take a few minutes)…"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
        || { echo "ERROR: Homebrew install failed" >&2; return 1; }

    # Initialise brew shellenv for this script
    if [[ -x /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -x /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi

    if ! command -v brew &>/dev/null; then
        echo "ERROR: Homebrew installed but 'brew' is not on PATH." >&2
        return 1
    fi
    echo "✓ Homebrew installed: $(brew --version | head -1)"
}

install_system_macos() {
    osa_info "macOS" "Installing SpeechPrint system dependencies via Homebrew."

    ensure_homebrew || return 1

    # Praat is a cask (GUI app)
    brew install python@3.11 ffmpeg git espeak-ng portaudio \
        || echo "⚠ Some brew formulas failed"
    brew install --cask praat \
        || echo "⚠ Could not install Praat cask (may already be installed)"
}

# ============================================================================
# PYTHON TOOLCHAIN (uv-based, matches Linux installer)
# ============================================================================

ensure_uv() {
    if command -v uv &>/dev/null; then
        echo "✓ uv already installed: $(uv --version)"
        return 0
    fi
    echo "Installing uv (fast Python package manager)…"
    if command -v curl &>/dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget &>/dev/null; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "ERROR: Need curl or wget to install uv" >&2
        return 1
    fi
    export PATH="$HOME/.local/bin:$PATH"
    command -v uv &>/dev/null || { echo "ERROR: uv install failed" >&2; return 1; }
    echo "✓ uv installed: $(uv --version)"
}

install_python_pipeline() {
    local sp_root="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"
    mkdir -p "$sp_root"
    echo "Setting up SpeechPrint Python environment at $sp_root…"

    cd "$sp_root"

    if [[ ! -d "$sp_root/.venv" ]]; then
        uv venv --python 3.11 "$sp_root/.venv"
    fi

    # shellcheck disable=SC1091
    source "$sp_root/.venv/bin/activate"

    # The launcher GUI is a runtime dep of the venv: install PyQt6 so the
    # bundled lib/main.py can launch from inside this Python.
    echo "Installing PyQt6 (GUI runtime)…"
    uv pip install "PyQt6>=6.6" || echo "⚠ PyQt6 install reported warnings"

    if [[ "$RELEASE_TYPE" == "dev" ]]; then
        SP_REF="main"
    else
        SP_REF="stable"
    fi

    echo "Installing speechprint_pkg (ref=$SP_REF)…"
    if uv pip install "git+https://github.com/SpeechPrint/SpeechPrint.git@${SP_REF}#subdirectory=speechprint_pkg" 2>/dev/null; then
        echo "✓ Installed speechprint_pkg from git"
    elif uv pip install speechprint 2>/dev/null; then
        echo "✓ Installed speechprint from PyPI"
    else
        echo "⚠ Could not fetch speechprint_pkg — install will continue, but pipeline commands will not work until package is available"
    fi

    echo "Installing audio + ASR dependencies…"
    uv pip install \
        "torch>=2.1" \
        "whisperx" \
        "openai-whisper" \
        "montreal-forced-aligner" \
        "praat-parselmouth" \
        "phonemizer" \
        "librosa" \
        "scipy" \
        "numpy" \
        "pandas" \
        "matplotlib" \
        "pympi-ling" \
        "textgrid" \
        "soundfile" \
        || echo "⚠ Some Python dependencies failed — see uv output above"

    deactivate || true

    # Symlink the speechprint CLI launcher into ~/.local/bin
    mkdir -p "$HOME/.local/bin"
    if [[ -n "${SPEECHPRINT_LAUNCHER_DIR:-}" ]] && [[ -f "$SPEECHPRINT_LAUNCHER_DIR/SpeechPrint" ]]; then
        ln -sf "$SPEECHPRINT_LAUNCHER_DIR/SpeechPrint" "$HOME/.local/bin/speechprint"
        echo "✓ Symlinked speechprint → $SPEECHPRINT_LAUNCHER_DIR/SpeechPrint"
    fi
}

# ============================================================================
# MFA ACOUSTIC MODELS (same set as Linux)
# ============================================================================

install_mfa_models() {
    local sp_root="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"
    export MFA_ROOT_DIR="$sp_root/mfa"
    mkdir -p "$MFA_ROOT_DIR"

    # shellcheck disable=SC1091
    source "$sp_root/.venv/bin/activate" 2>/dev/null || true

    if ! command -v mfa &>/dev/null; then
        echo "⚠ mfa command not found — skipping acoustic model download."
        echo "  SpeechPrint will still run ASR + prosody. Install MFA later"
        echo "  by activating $sp_root/.venv and running:"
        echo "      uv pip install montreal-forced-aligner"
        return 0
    fi

    IFS=',' read -ra LANG_ARRAY <<< "$LANGUAGES_CSV"
    for code in "${LANG_ARRAY[@]}"; do
        case "$code" in
            en) model="english_mfa" ;;
            de) model="german_mfa" ;;
            it) model="italian_mfa" ;;
            es) model="spanish_mfa" ;;
            fr) model="french_mfa" ;;
            cs) model="czech_mfa" ;;
            *)  model="${code}_mfa" ;;
        esac
        echo "Downloading MFA acoustic + dictionary for $code ($model)…"
        mfa model download acoustic   "$model" || echo "  ⚠ acoustic $model failed"
        mfa model download dictionary "$model" || echo "  ⚠ dictionary $model failed"
    done

    deactivate || true
}

# ============================================================================
# SHELL ENVIRONMENT (zsh on macOS by default)
# ============================================================================

write_env_setup() {
    local sp_root="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"
    local marker="# >>> SpeechPrint <<<"
    local end_marker="# <<< SpeechPrint >>>"

    # On macOS the user shell is zsh from 10.15 onwards
    local rc="$HOME/.zshrc"
    [[ -n "${ZDOTDIR:-}" && -f "$ZDOTDIR/.zshrc" ]] && rc="$ZDOTDIR/.zshrc"
    if [[ "${SHELL:-}" == *bash* ]]; then
        rc="$HOME/.bashrc"
    fi

    [[ ! -f "$rc" ]] && touch "$rc"

    if grep -q "$marker" "$rc"; then
        echo "✓ SpeechPrint environment already set in $rc"
        return 0
    fi

    cat >> "$rc" <<EOF

$marker
export SPEECHPRINT_ROOT="$sp_root"
export MFA_ROOT_DIR="\$SPEECHPRINT_ROOT/mfa"
export WHISPERX_MODEL="\${WHISPERX_MODEL:-large-v3}"
export PATH="\$HOME/.local/bin:\$PATH"
[[ -f "\$SPEECHPRINT_ROOT/.venv/bin/activate" ]] && source "\$SPEECHPRINT_ROOT/.venv/bin/activate"
$end_marker
EOF
    echo "✓ Added SpeechPrint environment block to $rc"
}

# ============================================================================
# MAIN
# ============================================================================

show_welcome

echo "Platform:           macOS ($(sw_vers -productVersion 2>/dev/null || uname -m))"
echo "Release channel:    $RELEASE_TYPE"
echo "Language modules:   $LANGUAGES_CSV"
echo ""

echo "=== System packages (Homebrew) ==="
install_system_macos

echo ""
echo "=== Python toolchain (uv) ==="
ensure_uv || { echo "✗ uv setup failed"; exit 1; }
install_python_pipeline

echo ""
echo "=== MFA acoustic models ==="
install_mfa_models

echo ""
echo "=== Shell environment ==="
write_env_setup

echo ""
echo "✓ SpeechPrint installation complete"
osa_info "Installation Complete" \
    "SpeechPrint installation complete! 🎉\n\nNext steps:\n1. Restart your terminal (or run: source ~/.zshrc)\n2. Create a corpus from the launcher, or:\n   speechprint new MyCorpus ~/Corpora/"

unset SUDO_PASSWORD
exit 0
