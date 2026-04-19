# Release Validation

Last updated: `2026-04-19`

This document records the checks used to cut `v2.4.0` and should remain the baseline for future stable releases.

## Installation Validation

The current release-ready checklist is:

```bash
bash scripts/bootstrap.sh --install-python
bash scripts/bootstrap.sh
.venv/bin/python -m py_compile scripts/process_share_links.py scripts/run_regression.py
.venv/bin/python -m unittest discover -s tests -v
```

Latest local outcome on `2026-04-19`:

- `bootstrap.sh --install-python`: passed
- `bootstrap.sh`: passed
- `py_compile`: passed
- `unittest`: passed (`33` tests)

## Automated Live Regression

The lightweight public-link regression entrypoint is:

```bash
.venv/bin/python scripts/run_regression.py --preset extended --analysis-mode heuristic
```

The `extended` preset covers:

- GitHub
- Zhihu
- CSDN
- Toutiao
- Bilibili

This preset is intended to verify the layered extraction chain without requiring private cookies or paid APIs.

Latest local outcome on `2026-04-19`: passed (`5/5 success`)

| Platform | Result | Extraction path |
| --- | --- | --- |
| GitHub | success | `github api + readme` |
| Zhihu | success | `scrapling fetch [.Post-RichText]` |
| CSDN | success | `scrapling fetch [#article_content]` |
| Toutiao | success | `scrapling stealthy-fetch [.article-content]` |
| Bilibili | success | `yt-dlp download + whisper-cli` |

## Manual Real-Link Regression

In addition to the preset above, we manually verified representative public share links during the `2026-03-26` and `2026-04-18` hardening cycles:

| Platform | Result | Extraction path |
| --- | --- | --- |
| GitHub | success | `github api + readme` |
| Zhihu | success | article extraction |
| CSDN | success | article extraction |
| Toutiao | success | `scrapling stealthy-fetch [.article-content]` |
| Bilibili | success | `yt-dlp download + whisper-cli` |
| WeChat | success | `scrapling stealthy-fetch [#js_content]` |
| Xiaohongshu | success | `yt-dlp download + whisper-cli` |
| X/Twitter | success | `yt-dlp download + whisper-cli` |
| Weibo | partial | `yt-dlp metadata only` on a very short clip |
| Douyin | success | `playwright douyin download + whisper-cli` |

Notes:

- `partial` is an honest outcome, not a silent failure. For short or low-speech clips, metadata may be the only reliable result.
- Social-platform success rates can change over time because anti-bot behavior changes.
- Cookie, browser-session, and referer support exist for users who need stronger access stability.
- Feishu / Feishu Wiki upload is not part of the release gate. Supported delivery targets in `v2.4.0` are local desktop output and Obsidian export.

## Stable Release Gate

Before publishing a stable tag:

- all installation checks above should pass on a clean local runtime
- unit tests should remain green
- at least one GitHub, one article page, one dynamic page, and one media link should succeed in live regression
- mixed-outcome platforms such as Weibo should be documented honestly instead of being hidden
