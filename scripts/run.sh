#!/usr/bin/env bash

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP_SCRIPT="$BASE_DIR/scripts/bootstrap.sh"
MAIN_SCRIPT="$BASE_DIR/scripts/process_share_links.py"
VENV_DIR="$BASE_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
AUTO_INSTALL_BINS=0
LOGIN_DOUYIN=0
RESOLVE_DOUYIN_URL=""
HAS_EXPLICIT_AUTH=0
DOUYIN_COOKIES_FILE="$BASE_DIR/auth/douyin/cookies.txt"
DOUYIN_AUTH_SCRIPT="$BASE_DIR/scripts/douyin_auth.py"

usage() {
  cat <<'EOF'
Usage: bash scripts/run.sh [--auto-bootstrap] [skill options...] <source>...
       bash scripts/run.sh [--auto-bootstrap] [--title "报告标题"] [--source <url>]...
       bash scripts/run.sh [--obsidian] [--vault "/path/to/Vault"] [--folder "Inbox/内容摘要"] [--source <url>]...

Options:
  --auto-bootstrap   Also install missing brew dependencies before running
  --title            Alias for --report-title
  --source           Add one source URL or file path explicitly
  --obsidian         Alias for --output-mode obsidian
  --both             Alias for --output-mode both
  --vault            Alias for --obsidian-vault
  --folder           Alias for --obsidian-folder
  --login-douyin     Open a Chromium window for QR login and save Douyin auth locally
  --resolve-douyin-url <url>
                     Print the resolved real Douyin media URL JSON and exit
  -h, --help         Show this message

Notes:
  - Local Python runtime (.venv + Scrapling) will be installed automatically on first run.
  - Local Python dependencies (Scrapling / trafilatura / yt-dlp) are bundled into .venv automatically.
  - System binaries (ffmpeg / whisper-cli / summarize) are not auto-installed
    unless --auto-bootstrap is provided.
  - Douyin QR auth is optional. When enabled, auth files are saved under auth/douyin/.
  - With --obsidian or --vault, notes are written into your Obsidian vault with frontmatter
    and per-source markdown notes.
EOF
}

ensure_local_runtime() {
  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "[content-processor] First run detected, installing local Python runtime..." >&2
    bash "$BOOTSTRAP_SCRIPT" --install-python
  fi

  if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
from scrapling.fetchers import Fetcher, StealthyFetcher  # noqa: F401
import trafilatura  # noqa: F401
import yt_dlp  # noqa: F401
import playwright  # noqa: F401
PY
  then
    echo "[content-processor] Local runtime is incomplete, repairing..." >&2
    bash "$BOOTSTRAP_SCRIPT" --install-python
  fi

  if [[ ! -x "$VENV_DIR/bin/yt-dlp" ]]; then
    echo "[content-processor] Local yt-dlp wrapper is missing, repairing..." >&2
    bash "$BOOTSTRAP_SCRIPT" --install-python
  fi
}

args_include_douyin_source() {
  local value
  for value in "${ARGS[@]}"; do
    case "$value" in
      *v.douyin.com/*|*www.douyin.com/*|*douyin.com/video/*|*iesdouyin.com/*)
        return 0
        ;;
    esac
  done
  return 1
}

ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --auto-bootstrap)
      AUTO_INSTALL_BINS=1
      ;;
    --title)
      if [[ $# -lt 2 ]]; then
        echo "[content-processor] --title requires a value" >&2
        exit 2
      fi
      ARGS+=("--report-title" "$2")
      shift
      ;;
    --source)
      if [[ $# -lt 2 ]]; then
        echo "[content-processor] --source requires a value" >&2
        exit 2
      fi
      ARGS+=("$2")
      shift
      ;;
    --obsidian)
      ARGS+=("--output-mode" "obsidian")
      ;;
    --both)
      ARGS+=("--output-mode" "both")
      ;;
    --vault)
      if [[ $# -lt 2 ]]; then
        echo "[content-processor] --vault requires a value" >&2
        exit 2
      fi
      ARGS+=("--obsidian-vault" "$2")
      shift
      ;;
    --folder)
      if [[ $# -lt 2 ]]; then
        echo "[content-processor] --folder requires a value" >&2
        exit 2
      fi
      ARGS+=("--obsidian-folder" "$2")
      shift
      ;;
    --login-douyin)
      LOGIN_DOUYIN=1
      ;;
    --resolve-douyin-url)
      if [[ $# -lt 2 ]]; then
        echo "[content-processor] --resolve-douyin-url requires a value" >&2
        exit 2
      fi
      RESOLVE_DOUYIN_URL="$2"
      shift
      ;;
    --cookies-file|--cookies-from-browser|--cookie-header)
      HAS_EXPLICIT_AUTH=1
      ARGS+=("$1")
      if [[ $# -lt 2 ]]; then
        echo "[content-processor] $1 requires a value" >&2
        exit 2
      fi
      ARGS+=("$2")
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      ARGS+=("$1")
      ;;
  esac
  shift
done

ensure_local_runtime

if [[ "$AUTO_INSTALL_BINS" -eq 1 ]]; then
  echo "[content-processor] Checking and installing system dependencies..." >&2
  bash "$BOOTSTRAP_SCRIPT" --install
fi

export PATH="$BASE_DIR/.venv/bin:$PATH"

if [[ -n "$RESOLVE_DOUYIN_URL" ]]; then
  exec "$PYTHON_BIN" "$DOUYIN_AUTH_SCRIPT" resolve "$RESOLVE_DOUYIN_URL"
fi

if [[ "$LOGIN_DOUYIN" -eq 0 && "$HAS_EXPLICIT_AUTH" -eq 0 ]]; then
  if args_include_douyin_source && [[ ! -f "$DOUYIN_COOKIES_FILE" ]] && [[ -t 0 && -t 1 ]]; then
    echo "[content-processor] No saved Douyin auth found. Launching QR login before processing..." >&2
    if ! "$PYTHON_BIN" "$DOUYIN_AUTH_SCRIPT" login; then
      echo "[content-processor] Douyin QR login did not complete cleanly. Continuing with fallback chain..." >&2
    fi
  fi
fi

if [[ "$LOGIN_DOUYIN" -eq 1 ]]; then
  echo "[content-processor] Launching Douyin QR login..." >&2
  "$PYTHON_BIN" "$DOUYIN_AUTH_SCRIPT" login
  LOGIN_EXIT=$?
  if [[ "$LOGIN_EXIT" -ne 0 ]]; then
    exit "$LOGIN_EXIT"
  fi
  if [[ ${#ARGS[@]} -eq 0 ]]; then
    exit 0
  fi
fi

if [[ "$HAS_EXPLICIT_AUTH" -eq 0 && -f "$DOUYIN_COOKIES_FILE" ]]; then
  ARGS=("--cookies-file" "$DOUYIN_COOKIES_FILE" "${ARGS[@]}")
fi

exec "$PYTHON_BIN" "$MAIN_SCRIPT" "${ARGS[@]}"
