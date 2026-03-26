# Contributing

## Local Setup

Install the local Python runtime:

```bash
bash scripts/bootstrap.sh --install-python
```

Recommended system dependencies:

```bash
brew install ffmpeg whisper-cpp
```

## Test Before Sending Changes

```bash
python3 -m py_compile scripts/process_share_links.py
python3 -m unittest discover -s tests -v
python3 scripts/run_regression.py --preset github
```

## Adding Support For A New Platform

1. Update source classification in `scripts/process_share_links.py`
2. Add platform labels / selectors / fallback strategy
3. Prefer a platform-specific extractor when generic web extraction is not enough
4. Add at least one unit test
5. Add or update a regression example in `scripts/run_regression.py`
6. Document the platform status in `README.md`

## Design Principles

- Prefer local output over external uploads
- Keep partial results instead of failing the whole batch
- Treat `metadata-only partial` as a valid fallback for short or noisy videos
- Keep human-facing docs in `README.md` and OpenClaw-facing docs in `SKILL.md`

## What Not To Commit

- `.venv/`
- `__pycache__/`
- `*.pyc`
- local `.env` files
- generated desktop reports
