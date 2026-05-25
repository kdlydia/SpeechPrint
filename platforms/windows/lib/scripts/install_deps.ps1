<#
.SYNOPSIS
    SpeechPrint dependency installer for Windows.

.DESCRIPTION
    Mirrors the Linux/macOS install_deps.sh in shape and output:
        1. install system packages (winget when available, else direct download)
        2. install uv (fast Python package manager) and create venv
        3. install PyQt6 + speechprint_pkg + WhisperX, torch, MFA, etc.
        4. download MFA acoustic models for the requested languages
        5. write per-user environment variables

.PARAMETER ReleaseType
    'stable' (default) or 'dev' — which speechprint_pkg branch to install.

.PARAMETER Languages
    Comma-separated language codes (e.g. "en,de,it"). Default "en".

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install_deps.ps1 stable en,de
#>

[CmdletBinding()]
param(
    [string]$ReleaseType = "stable",
    [string]$Languages = "en"
)

$ErrorActionPreference = "Stop"

function Write-Section($label) {
    Write-Host ""
    Write-Host "=== $label ==="
}

function Test-Command($name) {
    return [bool](Get-Command -Name $name -ErrorAction SilentlyContinue)
}

function Show-Info($title, $message) {
    try {
        Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue
        [System.Windows.MessageBox]::Show($message, $title, 'OK', 'Information') | Out-Null
    } catch {
        # Fall back to plain stdout if Windows.Forms / PresentationFramework
        # is unavailable (rare on Win10+).
        Write-Host "[$title] $message"
    }
}

# ============================================================================
# 1. SYSTEM PACKAGES (winget — built into Win10 1809+ / Win11)
# ============================================================================

function Install-SystemPackages {
    Write-Section "System packages"

    if (Test-Command "winget") {
        Write-Host "Using winget to install Python, ffmpeg, git, Praat…"

        $packages = @(
            "Python.Python.3.11",
            "Gyan.FFmpeg",
            "Git.Git",
            "PraatProject.Praat"
        )

        foreach ($pkg in $packages) {
            Write-Host "→ winget install $pkg"
            try {
                winget install --id $pkg --silent --accept-package-agreements `
                    --accept-source-agreements --disable-interactivity 2>&1 |
                    ForEach-Object { Write-Host "  $_" }
            } catch {
                Write-Host "  ⚠ $pkg install reported warnings: $_"
            }
        }
    } else {
        Write-Host "⚠ winget not found. Please install:"
        Write-Host "    • Python 3.11   https://python.org/downloads/"
        Write-Host "    • ffmpeg        https://ffmpeg.org/download.html"
        Write-Host "    • git           https://git-scm.com/download/win"
        Write-Host "    • Praat         https://praat.org/"
        Write-Host ""
        Write-Host "Then re-run this installer."
    }
}

# ============================================================================
# 2. uv + Python venv
# ============================================================================

function Get-PythonExe {
    foreach ($cand in @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "C:\Python311\python.exe"
    )) {
        if (Test-Path $cand) { return $cand }
    }
    if (Test-Command "py") {
        return "py -3.11"
    }
    if (Test-Command "python") {
        return "python"
    }
    return $null
}

function Install-Uv {
    if (Test-Command "uv") {
        Write-Host "✓ uv already installed: $(uv --version)"
        return
    }
    Write-Host "Installing uv via official PowerShell installer…"
    try {
        $script = Invoke-RestMethod -Uri "https://astral.sh/uv/install.ps1"
        Invoke-Expression $script
    } catch {
        Write-Host "ERROR: uv install failed: $_"
        return
    }
    # uv's PowerShell installer drops to %USERPROFILE%\.local\bin
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Test-Command "uv")) {
        Write-Host "ERROR: uv installed but not on PATH. Restart your terminal."
        throw "uv not on PATH"
    }
    Write-Host "✓ uv installed: $(uv --version)"
}

function Install-PythonPipeline {
    Write-Section "Python toolchain (uv)"

    $spRoot = $env:SPEECHPRINT_ROOT
    if (-not $spRoot) {
        $spRoot = Join-Path $env:USERPROFILE "SpeechPrint"
    }
    if (-not (Test-Path $spRoot)) {
        New-Item -ItemType Directory -Path $spRoot | Out-Null
    }

    Install-Uv

    $venv = Join-Path $spRoot ".venv"
    if (-not (Test-Path $venv)) {
        Write-Host "Creating venv at $venv …"
        uv venv --python 3.11 $venv
    }

    $venvPy = Join-Path $venv "Scripts\python.exe"

    Write-Host "Installing PyQt6 (GUI runtime)…"
    & uv pip install --python $venvPy "PyQt6>=6.6" 2>&1 |
        ForEach-Object { Write-Host "  $_" }

    $ref = if ($ReleaseType -eq "dev") { "main" } else { "stable" }

    Write-Host "Installing speechprint_pkg (ref=$ref)…"
    $gitOk = $false
    try {
        & uv pip install --python $venvPy `
            "git+https://github.com/SpeechPrint/SpeechPrint.git@$ref#subdirectory=speechprint_pkg" 2>&1 |
            ForEach-Object { Write-Host "  $_" }
        $gitOk = $true
    } catch {
        Write-Host "  ⚠ git install failed: $_"
    }
    if (-not $gitOk) {
        Write-Host "Falling back to PyPI…"
        try {
            & uv pip install --python $venvPy "speechprint" 2>&1 |
                ForEach-Object { Write-Host "  $_" }
        } catch {
            Write-Host "  ⚠ PyPI install also failed: $_"
            Write-Host "  Pipeline commands won't work until speechprint_pkg is reachable."
        }
    }

    Write-Host "Installing audio + ASR dependencies…"
    $deps = @(
        "torch>=2.1", "whisperx", "openai-whisper",
        "montreal-forced-aligner", "praat-parselmouth",
        "phonemizer", "librosa", "scipy", "numpy",
        "pandas", "matplotlib", "pympi-ling", "textgrid", "soundfile"
    )
    foreach ($d in $deps) {
        try {
            & uv pip install --python $venvPy $d 2>&1 |
                ForEach-Object { Write-Host "  $_" }
        } catch {
            Write-Host "  ⚠ $d failed: $_"
        }
    }
}

# ============================================================================
# 3. MFA ACOUSTIC MODELS
# ============================================================================

function Install-MfaModels {
    Write-Section "MFA acoustic models"

    $spRoot = $env:SPEECHPRINT_ROOT
    if (-not $spRoot) {
        $spRoot = Join-Path $env:USERPROFILE "SpeechPrint"
    }
    $env:MFA_ROOT_DIR = Join-Path $spRoot "mfa"
    if (-not (Test-Path $env:MFA_ROOT_DIR)) {
        New-Item -ItemType Directory -Path $env:MFA_ROOT_DIR | Out-Null
    }

    $mfa = Join-Path $spRoot ".venv\Scripts\mfa.exe"
    if (-not (Test-Path $mfa)) {
        Write-Host "⚠ mfa command not found in venv — skipping acoustic model download."
        Write-Host "  SpeechPrint will still run ASR, prosody, corpus creation, and exports."
        return
    }

    $modelMap = @{
        "en" = "english_mfa"
        "de" = "german_mfa"
        "it" = "italian_mfa"
        "es" = "spanish_mfa"
        "fr" = "french_mfa"
        "cs" = "czech_mfa"
    }

    foreach ($code in $Languages.Split(",")) {
        $code = $code.Trim()
        if (-not $code) { continue }
        $model = if ($modelMap.ContainsKey($code)) { $modelMap[$code] } else { "${code}_mfa" }
        Write-Host "Downloading MFA acoustic + dictionary for $code ($model)…"
        try {
            & $mfa model download acoustic   $model 2>&1 | ForEach-Object { Write-Host "  $_" }
        } catch {
            Write-Host "  ⚠ acoustic $model failed: $_"
        }
        try {
            & $mfa model download dictionary $model 2>&1 | ForEach-Object { Write-Host "  $_" }
        } catch {
            Write-Host "  ⚠ dictionary $model failed: $_"
        }
    }
}

# ============================================================================
# 4. ENVIRONMENT VARIABLES (per-user, persistent)
# ============================================================================

function Set-PersistentEnv {
    Write-Section "Environment variables"

    $spRoot = $env:SPEECHPRINT_ROOT
    if (-not $spRoot) {
        $spRoot = Join-Path $env:USERPROFILE "SpeechPrint"
    }

    [Environment]::SetEnvironmentVariable("SPEECHPRINT_ROOT", $spRoot, "User")
    [Environment]::SetEnvironmentVariable("MFA_ROOT_DIR", (Join-Path $spRoot "mfa"), "User")
    if (-not [Environment]::GetEnvironmentVariable("WHISPERX_MODEL", "User")) {
        [Environment]::SetEnvironmentVariable("WHISPERX_MODEL", "large-v3", "User")
    }

    # Extend user PATH with the venv Scripts dir so `speechprint`,
    # `mfa`, etc. are on the path in new terminals.
    $scriptsDir = Join-Path $spRoot ".venv\Scripts"
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if (-not $userPath) { $userPath = "" }
    if ($userPath -notlike "*$scriptsDir*") {
        $newPath = if ($userPath) { "$userPath;$scriptsDir" } else { $scriptsDir }
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Host "✓ Added $scriptsDir to user PATH"
    }
    Write-Host "✓ User environment set:"
    Write-Host "    SPEECHPRINT_ROOT = $spRoot"
    Write-Host "    MFA_ROOT_DIR     = $spRoot\mfa"
    Write-Host "    WHISPERX_MODEL   = large-v3 (default)"
}

# ============================================================================
# MAIN
# ============================================================================

Show-Info "SpeechPrint Installer" `
    "Welcome to SpeechPrint Installer!`n`nThis will install Python, ffmpeg, Praat, and the SpeechPrint analysis pipeline. You may be prompted to confirm Windows package installs.`n`nRelease channel: $ReleaseType`nLanguage modules: $Languages"

Write-Host "Platform:         Windows $([Environment]::OSVersion.Version)"
Write-Host "Release channel:  $ReleaseType"
Write-Host "Language modules: $Languages"

Install-SystemPackages
Install-PythonPipeline
Install-MfaModels
Set-PersistentEnv

Write-Host ""
Write-Host "✓ SpeechPrint installation complete"
Show-Info "Installation Complete" `
    "SpeechPrint installation complete!`n`nNext steps:`n1. Close and reopen any terminal so new env variables take effect.`n2. Run SpeechPrint again and choose New Project / Corpus."

exit 0
