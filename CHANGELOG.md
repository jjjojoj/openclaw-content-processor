# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog, and version tags follow the repository release flow.

## [Unreleased]

### Added

- Default Obsidian `knowledge-card` layout with one markdown note per source/link
- Automatic `.env` loading from the skill directory
- `chat/completions` compatibility for non-OpenAI-compatible LLM providers
- `--knowledge-card` and `--digest` wrapper flags in `scripts/run.sh`
- Optional reuse of OpenClaw's local `zai` / GLM Coding Plan provider config via `CONTENT_PROCESSOR_USE_OPENCLAW_ZAI=1`
- Fail-fast LLM availability checks that stop the run instead of silently falling back when analysis is explicitly required
- Explicit non-TTY Douyin QR-login override for self-hosted runners and remote desktop environments via `CONTENT_PROCESSOR_ALLOW_NON_TTY_DOUYIN_LOGIN=1`
- GitHub-specific knowledge-card routing in Obsidian, with `MOC/GitHub` root navigation and automatic category pages such as `AI Agent`, `SaaS`, and `FastAPI`

### Changed

- Obsidian output now defaults to knowledge-card mode, while the legacy digest layout remains available via `--obsidian-layout digest`
- Obsidian output now keeps only `_index.md` as the root entry point; `_log.md` and per-run `items/` JSON folders are no longer generated
- Unit tests now cover chat-completions parsing and knowledge-card note generation
- Coding-plan analysis now defaults to `glm-4.7`, instead of probing `glm-5` first
- BigModel / z.ai `chat/completions` summary requests now disable `thinking` by default so `glm-4.7` returns final answer text instead of reasoning-only payloads
- GitHub cards now use the exact repository name as the note title, plus a DeepWiki-inspired breakdown: what problem the repo solves, how the system is layered, which paths to read first, and how to start digging into the code
- Knowledge-card notes no longer dump full raw content for high-confidence web / GitHub captures; folded evidence is only shown for lower-confidence fallback cases or transcript-style media
- Obsidian knowledge indexes now insert new cards under the correct date heading instead of appending entries into the wrong day block
- README and `.env.example` now clarify that Feishu is unsupported and that `auto` output switches to Obsidian as soon as a vault path is configured

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
