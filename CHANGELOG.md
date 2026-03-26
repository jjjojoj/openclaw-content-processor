# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog, and version tags follow the repository release flow.

## [Unreleased]

### Added

- README preview asset for the GitHub homepage
- Detailed release validation notes in English and Chinese

### Changed

- Local git author configuration now uses the GitHub noreply email for contributor attribution
- README now highlights pre-release installation checks and live-link validation

## [2.3.0-beta.1] - 2026-03-26

Initial public beta release.

### Added

- GitHub-ready repository structure with `README.md`, `.env.example`, `CONTRIBUTING.md`, and GitHub Actions CI
- Dedicated GitHub extractor using repository metadata and README content
- Skill-local runtime for `yt-dlp`, `trafilatura`, and `Scrapling`
- Structured output pipeline with `report.md`, `report.json`, and per-item JSON results
- OpenAI-compatible analysis layer with local heuristic fallback
- Lightweight regression runner and unit test coverage
- Chinese README: `README.zh-CN.md`

### Changed

- `summarize` is no longer a hard dependency for the main path; it now acts as an optional fallback / PDF helper
- `run.sh` now supports friendlier aliases such as `--title` and `--source`
- Bootstrap and runtime checks now validate the full local Python runtime, not just one dependency
- README was rewritten for public GitHub release, with validated platform status and usage guidance

### Fixed

- Batch processing no longer aborts when one external extractor times out
- Dynamic-page title fallback no longer collapses to bare hostnames as easily
- Long transcript analysis now uses bounded analysis budgets to avoid slowdowns
- Social video transcript cleanup now removes URL noise and stage-direction noise such as music cues
- Metadata-only fallback now behaves more predictably for short or low-speech videos
