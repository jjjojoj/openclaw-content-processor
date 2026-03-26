#!/usr/bin/env bash

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$BASE_DIR/.venv"
REQUIREMENTS_FILE="$BASE_DIR/requirements.txt"
PYTHON_CMD="${CONTENT_PROCESSOR_PYTHON:-python3}"

INSTALL_BINS=0
INSTALL_PYTHON=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install)
      INSTALL_BINS=1
      INSTALL_PYTHON=1
      ;;
    --install-bins)
      INSTALL_BINS=1
      ;;
    --install-python)
      INSTALL_PYTHON=1
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: bash scripts/bootstrap.sh [--install] [--install-bins] [--install-python]" >&2
      exit 1
      ;;
  esac
  shift
done

has_bin() {
  if [[ -x "$1" ]]; then
    return 0
  fi
  command -v "$1" >/dev/null 2>&1
}

print_status() {
  local name="$1"
  local status="$2"
  printf '%-14s %s\n' "$name" "$status"
}

formula_for() {
  case "$1" in
    ffmpeg) echo "ffmpeg" ;;
    whisper-cli) echo "whisper-cpp" ;;
    summarize) echo "steipete/tap/summarize" ;;
    *) echo "" ;;
  esac
}

find_scrapling_bin() {
  if [[ -x "$VENV_DIR/bin/scrapling" ]]; then
    echo "$VENV_DIR/bin/scrapling"
    return 0
  fi
  if command -v scrapling >/dev/null 2>&1; then
    command -v scrapling
    return 0
  fi
  return 1
}

scrapling_health_check() {
  local scrapling_bin="$1"
  local python_bin
  python_bin="$(dirname "$scrapling_bin")/python"
  if [[ ! -x "$python_bin" ]]; then
    return 1
  fi
  "$python_bin" - <<'PY' >/dev/null 2>&1
from scrapling.fetchers import Fetcher, StealthyFetcher  # noqa: F401
import trafilatura  # noqa: F401
import yt_dlp  # noqa: F401
print("ok")
PY
}

install_local_python_runtime() {
  if ! has_bin "$PYTHON_CMD"; then
    echo "Python runtime not found: $PYTHON_CMD" >&2
    exit 1
  fi

  echo "Installing local Python runtime into $VENV_DIR ..."
  echo "Using Python: $PYTHON_CMD"
  "$PYTHON_CMD" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
  "$VENV_DIR/bin/python" -m pip install -r "$REQUIREMENTS_FILE"

  if [[ -x "$VENV_DIR/bin/scrapling" ]]; then
    echo "Running scrapling install ..."
    if ! "$VENV_DIR/bin/scrapling" install; then
      echo "Warning: scrapling install failed. Static get-mode may still work, but stealthy fetch may be unavailable." >&2
    fi
  fi
}

echo "Content Processor dependency check"
echo

MISSING=()
OPTIONAL_MISSING=()

if has_bin "$PYTHON_CMD"; then
  if [[ -x "$PYTHON_CMD" ]]; then
    print_status "python3" "OK ($PYTHON_CMD)"
  else
    print_status "python3" "OK ($(command -v "$PYTHON_CMD"))"
  fi
else
  print_status "python3" "MISSING ($PYTHON_CMD)"
  MISSING+=("python3")
fi

for bin in ffmpeg whisper-cli summarize; do
  if has_bin "$bin"; then
    print_status "$bin" "OK ($(command -v "$bin"))"
  else
    print_status "$bin" "MISSING"
    OPTIONAL_MISSING+=("$bin")
  fi
done

echo

WHISPER_MODEL_PATH="${WHISPER_MODEL:-}"
if [[ -n "$WHISPER_MODEL_PATH" && -f "$WHISPER_MODEL_PATH" ]]; then
  print_status "whisper-model" "OK ($WHISPER_MODEL_PATH)"
else
  MODEL_FOUND=""
  for candidate in \
    "$HOME/.whisper-models/ggml-small.bin" \
    "$HOME/.whisper-models/ggml-base.bin" \
    "/opt/homebrew/share/whisper/models/ggml-small.bin" \
    "/opt/homebrew/share/whisper/models/ggml-base.bin"
  do
    if [[ -f "$candidate" ]]; then
      MODEL_FOUND="$candidate"
      break
    fi
  done

  if [[ -n "$MODEL_FOUND" ]]; then
    print_status "whisper-model" "OK ($MODEL_FOUND)"
  else
    print_status "whisper-model" "MISSING"
    echo "Suggested download:"
    echo "  mkdir -p \"$HOME/.whisper-models\""
    echo "  curl -L -o \"$HOME/.whisper-models/ggml-small.bin\" \\"
    echo "    \"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin\""
  fi
fi

echo

SCRAPLING_STATUS="MISSING"
SCRAPLING_PATH=""
LOCAL_YTDLP_PATH="$VENV_DIR/bin/yt-dlp"
if SCRAPLING_PATH="$(find_scrapling_bin 2>/dev/null)"; then
  if scrapling_health_check "$SCRAPLING_PATH"; then
    SCRAPLING_STATUS="OK ($SCRAPLING_PATH)"
  else
    SCRAPLING_STATUS="BROKEN ($SCRAPLING_PATH)"
  fi
fi
if [[ "$SCRAPLING_STATUS" == OK* ]]; then
  print_status "py-runtime" "OK ($(dirname "$SCRAPLING_PATH")/python)"
else
  print_status "py-runtime" "MISSING"
fi
print_status "scrapling" "$SCRAPLING_STATUS"
if [[ -x "$LOCAL_YTDLP_PATH" ]]; then
  print_status "yt-dlp" "OK ($LOCAL_YTDLP_PATH)"
else
  print_status "yt-dlp" "MISSING ($LOCAL_YTDLP_PATH)"
fi

if [[ ${#MISSING[@]} -eq 0 && "$SCRAPLING_STATUS" == OK* && -x "$LOCAL_YTDLP_PATH" && "$INSTALL_BINS" -eq 0 && "$INSTALL_PYTHON" -eq 0 ]]; then
  echo
  echo "All required runtimes are available."
  exit 0
fi

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo
  echo "Missing binaries: ${MISSING[*]}"
fi

if [[ ${#OPTIONAL_MISSING[@]} -gt 0 ]]; then
  echo
  echo "Optional system binaries missing: ${OPTIONAL_MISSING[*]}"
fi

if [[ "$INSTALL_BINS" -eq 1 ]]; then
  if ! has_bin brew; then
    echo "Homebrew is required for --install or --install-bins mode but was not found." >&2
    exit 1
  fi

  for bin in "${MISSING[@]}" "${OPTIONAL_MISSING[@]}"; do
    [[ -z "$bin" ]] && continue
    formula="$(formula_for "$bin")"
    if [[ -n "$formula" ]]; then
      echo "Installing $bin via brew ($formula)..."
      brew install "$formula"
    else
      echo "No automated installer configured for $bin."
    fi
  done
elif [[ ${#MISSING[@]} -gt 0 || ${#OPTIONAL_MISSING[@]} -gt 0 ]]; then
  echo "Install suggestions:"
  for bin in "${MISSING[@]}" "${OPTIONAL_MISSING[@]}"; do
    [[ -z "$bin" ]] && continue
    formula="$(formula_for "$bin")"
    if [[ -n "$formula" ]]; then
      echo "  brew install $formula"
    fi
  done
  echo
  echo "Or run:"
  echo "  bash \"$0\" --install-bins"
fi

if [[ "$SCRAPLING_STATUS" != OK* || ! -x "$LOCAL_YTDLP_PATH" ]]; then
  echo
  echo "The local Python runtime is required for bundled extractors and media fallback"
  echo "(Scrapling, trafilatura, yt-dlp; used for WeChat, Toutiao, GitHub, Xiaohongshu, Bilibili, etc.)."
fi

if [[ "$INSTALL_PYTHON" -eq 1 && ( "$SCRAPLING_STATUS" != OK* || ! -x "$LOCAL_YTDLP_PATH" ) ]]; then
  install_local_python_runtime
  echo
  if SCRAPLING_PATH="$(find_scrapling_bin 2>/dev/null)" && scrapling_health_check "$SCRAPLING_PATH"; then
    print_status "py-runtime" "OK ($(dirname "$SCRAPLING_PATH")/python)"
    print_status "scrapling" "OK ($SCRAPLING_PATH)"
    print_status "yt-dlp" "OK ($VENV_DIR/bin/yt-dlp)"
  else
    print_status "py-runtime" "BROKEN after install"
    print_status "scrapling" "BROKEN after install"
    print_status "yt-dlp" "BROKEN after install"
  fi
elif [[ "$SCRAPLING_STATUS" != OK* || ! -x "$LOCAL_YTDLP_PATH" ]]; then
  echo "Install local Python runtime:"
  echo "  bash \"$0\" --install-python"
fi
