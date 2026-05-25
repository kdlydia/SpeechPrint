#!/usr/bin/env python3
"""CLI: `speechprint new <name> <location>` and passthrough to speechprint_pkg.

Cross-platform analogue of the Linux lib/cli.py:
    * `new`     → spawns create_corpus.sh (macOS) or create_corpus.ps1 (Windows)
    * `gui`     → launches the PyQt6 launcher (lib.main)
    * `annotate / linguist / ensemble / …` → passthrough to speechprint_pkg.cli
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

_cli_dir = Path(__file__).resolve().parent
_lib_dir = _cli_dir.parent
if str(_lib_dir) not in sys.path:
    sys.path.insert(0, str(_lib_dir))

try:
    from lib.config import get_config
except ImportError as e:
    print(
        "Error: Cannot import lib.config\n"
        f"sys.path: {sys.path}\n"
        f"Expected lib at: {_lib_dir}\n"
        f"Error: {e}",
        file=sys.stderr,
    )
    sys.exit(1)


def _passthrough_to_pipeline(args_list):
    try:
        cfg = get_config()
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env.update(cfg.get_env_vars())
    try:
        result = subprocess.run(
            [sys.executable, "-m", "speechprint_pkg.cli"] + args_list, env=env
        )
        return result.returncode
    except FileNotFoundError:
        print(
            "Error: speechprint_pkg not found.\n"
            "Run the installer first.",
            file=sys.stderr,
        )
        return 1


def _build_create_cmd(cfg, name, location, language, no_vscode, auto_ensemble):
    """Build the per-platform corpus-creation command."""
    scripts_dir = Path(cfg.scripts_dir)
    if sys.platform == "win32":
        script = scripts_dir / "create_corpus.ps1"
        if not script.exists():
            return None, f"create_corpus.ps1 not found at {script}"
        cmd = [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(script),
            "new", name, location,
            "-Language", language,
        ]
        if no_vscode:
            cmd.append("-NoVSCode")
        if auto_ensemble:
            cmd.append("-AutoEnsemble")
    else:
        script = scripts_dir / "create_corpus.sh"
        if not script.exists():
            return None, f"create_corpus.sh not found at {script}"
        try:
            script.chmod(0o755)
        except Exception:
            pass
        cmd = [
            "/bin/bash", str(script),
            "new", name, location,
            "--language", language,
        ]
        if no_vscode:
            cmd.append("--no-vscode")
        if auto_ensemble:
            cmd.append("--auto-ensemble")
    return cmd, None


def main():
    parser = argparse.ArgumentParser(
        prog="speechprint",
        description="SpeechPrint corpus creator and annotator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  speechprint new MyCorpus ~/Corpora/
  speechprint new FieldRecordings . --language it
  speechprint annotate data/recording.wav --language de
  speechprint ensemble
  speechprint gui
        """,
    )
    subparsers = parser.add_subparsers(dest="cmd", help="Commands")

    new_parser = subparsers.add_parser("new", help="Create a new corpus")
    new_parser.add_argument("name", help="Corpus name")
    new_parser.add_argument("location", nargs="?", default=".", help="Corpus location")
    new_parser.add_argument("--language", default="en", help="Default corpus language")
    new_parser.add_argument("--no-vscode", action="store_true")
    new_parser.add_argument("--auto-ensemble", action="store_true")

    subparsers.add_parser("gui", help="Launch graphical installer / project picker")

    for name, desc in [
        ("annotate", "Annotate a WAV file (full pipeline, steps 1–10)"),
        ("linguist", "Interactive annotation — drop a WAV, pick language"),
        ("ensemble", "Aggregate verified per-recording outputs"),
        ("transcribe", "Run WhisperX transcription only"),
        ("align", "Run MFA forced alignment only"),
        ("prosody", "Extract prosody (F0, intensity, jitter, formants)"),
        ("export", "Export to TextGrid / EAF / CSV / JSON"),
        ("corpus", "Batch-annotate a directory of WAVs"),
    ]:
        subparsers.add_parser(name, help=desc, add_help=False)

    parser.add_argument("--version", action="version", version="%(prog)s 0.3.0")
    parser.add_argument("--config", action="store_true", help="Show configuration and exit")

    PASSTHROUGH = {
        "annotate", "linguist", "ensemble", "transcribe",
        "align", "prosody", "export", "export-zip", "corpus",
    }
    if len(sys.argv) >= 2 and sys.argv[1] in PASSTHROUGH:
        return _passthrough_to_pipeline(sys.argv[1:])

    args = parser.parse_args()

    if args.config:
        try:
            cfg = get_config()
            print("SpeechPrint Configuration")
            print("=========================")
            print(f"Root:                {cfg.root}")
            print(f"Scripts:             {cfg.scripts_dir}")
            print(f"Templates:           {cfg.templates_dir}")
            print(f"Default language:    {cfg.default_language}")
            print(f"Supported languages: {', '.join(cfg.supported_languages)}")
            print("\nEnvironment variables:")
            for key, value in cfg.get_env_vars().items():
                print(f"  {key}={value}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return 0

    if args.cmd == "new":
        try:
            cfg = get_config()
        except Exception as e:
            print(f"Error loading configuration: {e}", file=sys.stderr)
            sys.exit(1)
        cmd, err = _build_create_cmd(
            cfg, args.name, args.location, args.language,
            args.no_vscode, args.auto_ensemble,
        )
        if err:
            print(f"Error: {err}", file=sys.stderr)
            return 1
        env = os.environ.copy()
        env.update(cfg.get_env_vars())
        try:
            return subprocess.run(cmd, env=env).returncode
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.cmd == "gui":
        try:
            from lib.main import main as gui_main
            return gui_main()
        except ImportError:
            print(
                "Error: GUI dependencies not installed.\n"
                "Run the installer or `pip install PyQt6`.",
                file=sys.stderr,
            )
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
