<#
.SYNOPSIS
    SpeechPrint corpus creator (Windows).

.DESCRIPTION
    Mirrors lib/scripts/create_corpus.sh:
        - copies templates from $SPEECHPRINT_TEMPLATE_DIR (or relative to this script)
        - substitutes @CORPUS_NAME@, @LANGUAGE@, @AUTO_ENSEMBLE@ placeholders
        - creates data/, out/, optional .vscode/

.PARAMETER Command
    Must be "new".

.PARAMETER Name
    Corpus / project name.

.PARAMETER Destination
    Parent directory to create the corpus inside. Default: current directory.

.PARAMETER Language
    Default language code (en, de, it, …). Default: en.

.PARAMETER NoVSCode
    Skip the .vscode/ scaffold.

.PARAMETER AutoEnsemble
    Set auto_ensemble = true in corpus.toml.

.EXAMPLE
    create_corpus.ps1 new MyCorpus C:\Users\me\Corpora -Language en -AutoEnsemble
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true, Position=0)][string]$Command,
    [Parameter(Position=1)][string]$Name,
    [Parameter(Position=2)][string]$Destination = ".",
    [string]$Language = "en",
    [switch]$NoVSCode,
    [switch]$AutoEnsemble
)

$ErrorActionPreference = "Stop"

function Write-Log($msg)    { Write-Host "[SpeechPrint] $msg" }
function Write-Err($msg)    { Write-Error "[SpeechPrint ERROR] $msg"; exit 1 }

if ($Command -ne "new") {
    Write-Err "Unknown command: $Command. Use 'new <name>'."
}
if (-not $Name) {
    Write-Err "Corpus name required."
}

# Resolve templates dir
if ($env:SPEECHPRINT_TEMPLATE_DIR -and (Test-Path $env:SPEECHPRINT_TEMPLATE_DIR)) {
    $TemplatesDir = $env:SPEECHPRINT_TEMPLATE_DIR
} else {
    $scriptDir = Split-Path -Parent $PSCommandPath
    $TemplatesDir = Resolve-Path (Join-Path $scriptDir "..\templates")
}

if (-not (Test-Path $TemplatesDir)) {
    Write-Err "Templates not found at $TemplatesDir"
}

# Resolve destination
$Destination = $Destination -replace '^~', "$env:USERPROFILE"
if (-not (Test-Path $Destination)) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
}
$Destination = (Resolve-Path $Destination).Path
$CorpusDir = Join-Path $Destination $Name

if (Test-Path $CorpusDir) {
    if (Test-Path (Join-Path $CorpusDir "corpus.toml")) {
        Write-Log "Corpus '$Name' already exists at $CorpusDir."
        Write-Log "Nothing to do."
        exit 0
    } else {
        Write-Err "Directory already exists and is not a SpeechPrint corpus: $CorpusDir"
    }
}

# ----- check required templates ------------------------------------------
foreach ($t in @("corpus.toml", "README.md", "gitignore")) {
    if (-not (Test-Path (Join-Path $TemplatesDir $t))) {
        Write-Err "Required template missing: $t at $TemplatesDir\$t"
    }
}

# ----- create structure --------------------------------------------------
Write-Log "Creating corpus: $Name"
New-Item -ItemType Directory -Path $CorpusDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $CorpusDir "data") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $CorpusDir "out") -Force | Out-Null
New-Item -ItemType File -Path (Join-Path $CorpusDir "data\.gitkeep") -Force | Out-Null
New-Item -ItemType File -Path (Join-Path $CorpusDir "out\.gitkeep") -Force | Out-Null
if (-not $NoVSCode) {
    New-Item -ItemType Directory -Path (Join-Path $CorpusDir ".vscode") -Force | Out-Null
    Write-Log "  ✓ Created .vscode directory"
}
Write-Log "  ✓ Created corpus structure"

# ----- placeholder substitution helper -----------------------------------
function Expand-Template($srcPath, $dstPath) {
    $content = Get-Content -Raw -Path $srcPath
    $content = $content -replace '@CORPUS_NAME@', $Name
    $content = $content -replace '@LANGUAGE@', $Language
    $content = $content -replace '@AUTO_ENSEMBLE@', $(if ($AutoEnsemble) {"true"} else {"false"})
    # Preserve a sensible default encoding (UTF-8 without BOM works in VS Code).
    [System.IO.File]::WriteAllText($dstPath, $content, [System.Text.UTF8Encoding]::new($false))
}

# ----- corpus.toml -------------------------------------------------------
Write-Log "Generating corpus.toml"
Expand-Template `
    (Join-Path $TemplatesDir "corpus.toml") `
    (Join-Path $CorpusDir "corpus.toml")
Write-Log "  ✓ Generated corpus.toml (default language: $Language)"

# ----- vscode config -----------------------------------------------------
if (-not $NoVSCode) {
    $vscodeSrc = Join-Path $TemplatesDir "vscode"
    if (Test-Path $vscodeSrc) {
        Write-Log "Generating VS Code configuration"
        foreach ($f in @("settings.json", "tasks.json", "launch.json")) {
            $s = Join-Path $vscodeSrc $f
            if (Test-Path $s) {
                Expand-Template $s (Join-Path $CorpusDir ".vscode\$f")
            }
        }
        Write-Log "  ✓ Generated VS Code configuration"
    } else {
        Write-Log "  ⚠ VS Code templates not found, skipping"
    }
}

# ----- gitignore + README ------------------------------------------------
Write-Log "Generating .gitignore"
Copy-Item -Path (Join-Path $TemplatesDir "gitignore") -Destination (Join-Path $CorpusDir ".gitignore") -Force
Write-Log "  ✓ Generated .gitignore"

Write-Log "Generating README.md"
Expand-Template `
    (Join-Path $TemplatesDir "README.md") `
    (Join-Path $CorpusDir "README.md")
Write-Log "  ✓ Generated README.md"

# ----- summary -----------------------------------------------------------
Write-Host ""
Write-Host "=========================================="
Write-Host "  ✓ Corpus '$Name' created!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Location: $CorpusDir"
Write-Host "Default language: $Language"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. cd `"$CorpusDir`""
Write-Host "  2. Drop WAV files in data\"
if (-not $NoVSCode) {
    Write-Host "  3. code .                    # Open in VS Code"
    Write-Host "  4. speechprint annotate data\<file>.wav --language $Language"
} else {
    Write-Host "  3. speechprint annotate data\<file>.wav --language $Language"
}
Write-Host "  5. speechprint ensemble"
Write-Host ""
exit 0
