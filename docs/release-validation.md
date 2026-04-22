# Release Validation

Last updated: `2026-04-22`

This document keeps two truths separate:

- the stable release baseline (`v2.4.0`)
- the current `main` branch snapshot, which already contains newer AI + Obsidian improvements

## Stable release baseline: `v2.4.0`

The checks used to cut `v2.4.0` remain the minimum baseline for future stable tags.

### Installation validation

```bash
bash scripts/bootstrap.sh --install-python
bash scripts/bootstrap.sh
.venv/bin/python -m py_compile scripts/process_share_links.py scripts/run_regression.py
.venv/bin/python -m unittest discover -s tests -v
```

Latest stable-baseline outcome on `2026-04-19`:

- `bootstrap.sh --install-python`: passed
- `bootstrap.sh`: passed
- `py_compile`: passed
- `unittest`: passed (`33` tests at the time)

### Automated live regression

Public-link regression entrypoint:

```bash
.venv/bin/python scripts/run_regression.py --preset extended --analysis-mode heuristic
```

`extended` covers:

- GitHub
- Zhihu
- CSDN
- Toutiao
- Bilibili

Stable-baseline outcome on `2026-04-19`: passed (`5/5 success`)

| Platform | Result | Extraction path |
| --- | --- | --- |
| GitHub | success | `github api + readme` |
| Zhihu | success | `scrapling fetch [.Post-RichText]` |
| CSDN | success | `scrapling fetch [#article_content]` |
| Toutiao | success | `scrapling stealthy-fetch [.article-content]` |
| Bilibili | success | `yt-dlp download + whisper-cli` |

## Current `main` branch snapshot

These checks describe the repository as it exists on `main`, not the last stable tag.

### Local verification on `2026-04-22`

```bash
.venv/bin/python -m py_compile scripts/process_share_links.py scripts/douyin_auth.py scripts/run_regression.py
.venv/bin/python -m unittest discover -s tests -v
```

Outcome:

- `py_compile`: passed
- `unittest`: passed (`67` tests)

### Representative real outputs currently present

These are not abstract claims; they correspond to real notes / reports already generated in a working vault.

| Source type | Result | Extraction path |
| --- | --- | --- |
| GitHub repo | success | `deepwiki overview` |
| Douyin short video | success | `playwright douyin download + whisper-cli` |

Representative notes already written by the current pipeline:

- `NousResearch/hermes-agent`
- `OpenCode 保姆级配置与实战指南`

## Manual real-link regression notes

In addition to the public preset above, the project has manually verified representative public share links during the hardening cycles around `2026-03-26`, `2026-04-19`, and `2026-04-22`.

| Platform | Result | Typical extraction path |
| --- | --- | --- |
| GitHub | success | `deepwiki overview` or `github api + readme` |
| Zhihu | success | article extraction |
| CSDN | success | article extraction |
| Toutiao | success | `scrapling stealthy-fetch [.article-content]` |
| Bilibili | success | `yt-dlp download + whisper-cli` |
| WeChat | success | `scrapling stealthy-fetch [#js_content]` |
| Xiaohongshu | success | `yt-dlp download + whisper-cli` |
| X/Twitter | success | `yt-dlp download + whisper-cli` |
| Weibo | partial | `yt-dlp metadata only` on very short clips |
| Douyin | success | `playwright douyin download + whisper-cli` |

Notes:

- `partial` is an honest outcome, not a hidden failure.
- social-platform success rates can change over time because anti-bot behavior changes
- browser cookies, saved auth, and referer support exist for users who need stronger access stability
- Feishu / Feishu Wiki upload is intentionally outside the current release scope

## Public CI vs self-hosted runner

Recommended split:

- public CI:
  - runtime bootstrap
  - compile checks
  - unit tests
  - lightweight public-link regression
  - mocked Douyin auth gating and fallback logic
- self-hosted runner / desktop smoke test:
  - real Douyin QR login
  - saved-cookie reuse
  - Playwright media fallback on a real share link

Important note:

- public CI should not attempt real Douyin QR login
- real QR login only makes sense in a self-hosted runner, VNC session, or remote desktop where a human can actually scan the code
- if you intentionally use such an environment, open the gate explicitly with `CONTENT_PROCESSOR_ALLOW_NON_TTY_DOUYIN_LOGIN=1`

## Stable release gate

Before publishing a new stable tag:

- the stable-baseline installation checks should pass on a clean runtime
- unit tests should remain green
- at least one GitHub link, one article page, one dynamic page, and one media link should succeed
- mixed-outcome platforms such as Weibo should be documented honestly instead of being hidden
