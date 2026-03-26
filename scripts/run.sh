#!/usr/bin/env bash

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP_SCRIPT="$BASE_DIR/scripts/bootstrap.sh"
MAIN_SCRIPT="$BASE_DIR/scripts/process_share_links.py"
VENV_DIR="$BASE_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
AUTO_INSTALL_BINS=0

usage() {
  cat <<'EOF'
Usage: bash scripts/run.sh [--auto-bootstrap] [skill options...] <source>...
       bash scripts/run.sh [--auto-bootstrap] [--title "报告标题"] [--source <url>]...

Options:
  --auto-bootstrap   Also install missing brew dependencies before running
  --title            Alias for --report-title
  --source           Add one source URL or file path explicitly
  -h, --help         Show this message

Notes:
  - Local Python runtime (.venv + Scrapling) will be installed automatically on first run.
  - Local Python dependencies (Scrapling / trafilatura / yt-dlp) are bundled into .venv automatically.
  - System binaries (ffmpeg / whisper-cli / summarize) are not auto-installed
    unless --auto-bootstrap is provided.
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

exec "$PYTHON_BIN" "$MAIN_SCRIPT" "${ARGS[@]}"
