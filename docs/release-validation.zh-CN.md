# 发布验证说明

最后更新：`2026-03-26`

这个文件记录的是在切 `v2.3.0` 这类稳定版之前，我们会执行的验证动作。

## 安装验证

当前建议的发布前检查命令：

```bash
bash scripts/bootstrap.sh --install-python
bash scripts/bootstrap.sh
.venv/bin/python -m py_compile scripts/process_share_links.py scripts/run_regression.py
.venv/bin/python -m unittest discover -s tests -v
```

`2026-03-26` 本地最新结果：

- `bootstrap.sh --install-python`：通过
- `bootstrap.sh`：通过
- `py_compile`：通过
- `unittest`：通过（`15` 项）

## 自动化真实链接回归

轻量公开样本回归入口：

```bash
.venv/bin/python scripts/run_regression.py --preset extended --analysis-mode heuristic
```

`extended` 预设覆盖：

- GitHub
- 知乎
- CSDN
- 头条
- Bilibili

这套预设的目标，是在不依赖私有 cookie 或付费接口的前提下，验证分层抽取链路本身还能正常工作。

`2026-03-26` 最新结果：通过（`5/5 success`）

| 平台 | 结果 | 抽取路径 |
| --- | --- | --- |
| GitHub | success | `github api + readme` |
| 知乎 | success | `scrapling fetch [.Post-RichText]` |
| CSDN | success | `scrapling fetch [#article_content]` |
| 头条 | success | `scrapling stealthy-fetch [.article-content]` |
| Bilibili | success | `yt-dlp download + whisper-cli` |

## 手工真实链接回归

除了上面的预设，我们还在 `2026-03-26` 手工验证了几类公开分享链接：

| 平台 | 结果 | 抽取路径 |
| --- | --- | --- |
| GitHub | success | `github api + readme` |
| 知乎 | success | 文章正文抽取 |
| CSDN | success | 文章正文抽取 |
| 头条 | success | `scrapling stealthy-fetch [.article-content]` |
| Bilibili | success | `yt-dlp download + whisper-cli` |
| 微信公众号 | success | `scrapling stealthy-fetch [#js_content]` |
| 小红书 | success | `yt-dlp download + whisper-cli` |
| X/Twitter | success | `yt-dlp download + whisper-cli` |
| 微博 | partial | 极短视频回退到 `yt-dlp metadata only` |

说明：

- `partial` 是有意保留的诚实结果，不是静默失败。对极短、少语音或纯噪声视频，元数据往往比错误正文更可靠。
- 社媒平台的成功率会随着反爬策略变化而波动。
- 如果业务场景需要更稳定的访问，当前仓库已经支持 cookie、browser session 和 referer。

## `v2.3.0` 正式版前的门槛

在发布稳定 tag 之前，至少要满足：

- 上面的安装检查在干净本地 runtime 上全部通过
- 单测保持绿色
- live regression 里至少有一条 GitHub、一条文章页、一条动态页、一条媒体链接成功
- 对微博这类天然有 mixed outcome 的平台，要在文档里如实说明，而不是隐藏边界
