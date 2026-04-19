# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog, and version tags follow the repository release flow.

## [Unreleased]

## [2.4.0] - 2026-04-19

Second stable release focused on local-first notes, Obsidian export, and more reliable Douyin handling.

### Added

- Obsidian export mode with vault-ready digest notes, YAML frontmatter, and per-source markdown notes
- `--obsidian`, `--vault`, and `--folder` convenience flags in `scripts/run.sh`
- Douyin QR-login helper flow via `--login-douyin` and direct media URL checks via `--resolve-douyin-url`

### Changed

- README and SKILL now describe local note workflows with Obsidian as a first-class target
- `.env.example` now includes Obsidian output configuration
- Douyin processing now follows `saved auth -> QR login retry -> Playwright fallback`
- Temporary mp4 files used only for transcription are deleted after transcription completes
- Project scope is now explicitly local-first: Feishu / Feishu Wiki upload is not part of the supported output targets

## [2.3.0] - 2026-03-27

First stable release after beta validation.

### Added

- A visible OpenClaw install prompt block near the top of both READMEs
- Clear stable-release validation links from the homepage

### Changed

- Replaced the `shadcn-ui/ui` demo URLs with the more neutral `openai/openai-python`
- Removed the user-specific `吴总今日信息汇总` example title from `SKILL.md`
- Promoted repository messaging from beta-oriented language to stable-release language
- Local git author configuration now uses the GitHub noreply email for contributor attribution
- README now highlights installation checks and live-link validation for stable releases

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
