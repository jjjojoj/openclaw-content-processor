# Content Processor

`content-processor` 是一个面向 OpenClaw 和命令行用户的内容汇总 skill：把一个或多个分享链接抓取、清洗、归纳后，输出为桌面上的 `report.md + report.json`。

它适合处理：

- GitHub 仓库链接
- 普通网页文章
- 微信公众号、知乎、CSDN、头条等页面
- YouTube、Bilibili、抖音、小红书、微博、X/Twitter 等视频/社媒分享链接

## Status

当前推荐作为 `beta` 发布。

- 对公开网页、GitHub、知乎、CSDN、微信公众号的支持相对稳定
- 对 X/Twitter、微博、小红书、Bilibili 这类视频/社媒链接，通常可用，但成功率会受到字幕、平台限流、登录态和反爬策略影响
- 对极短、几乎无有效语音的社媒视频，系统可能回退到 `metadata-only partial`，这是刻意保留的诚实结果，而不是 bug

## What It Produces

默认输出目录：

```text
~/Desktop/内容摘要/YYYY-MM-DD/<timestamp>/
```

目录内包含：

- `report.md`: 给人看的汇总报告
- `report.json`: 结构化输出，适合后续自动化
- `items/*.json`: 每个来源的单独结果

## Requirements

推荐环境：

- macOS 或 Linux
- Python 3.11+
- `ffmpeg`
- `whisper-cli`

可选但推荐：

- `OPENAI_API_KEY`
  - 用于生成更自然的分析段落
  - 不配置也能运行，会自动回退到本地 heuristic 分析

说明：

- `yt-dlp`、`trafilatura`、`Scrapling` 都会安装到 skill 自己的 `.venv/` 中
- `summarize` 不再是主流程硬依赖，仅用于可选 PDF 提取 / fallback

## Quick Start

先安装系统依赖：

```bash
brew install ffmpeg whisper-cpp
```

然后安装 skill 本地 Python runtime：

```bash
bash scripts/bootstrap.sh --install-python
```

或者直接运行，首次会自动补本地 `.venv/`：

```bash
bash scripts/run.sh "https://github.com/shadcn-ui/ui"
```

如果你也想让脚本顺手检查系统依赖：

```bash
bash scripts/run.sh --auto-bootstrap "https://github.com/shadcn-ui/ui"
```

## Usage

最简单的方式：

```bash
bash scripts/run.sh \
  "https://github.com/shadcn-ui/ui" \
  "https://mp.weixin.qq.com/s/xxxxxxxx"
```

带标题：

```bash
bash scripts/run.sh \
  --title "今日内容汇总" \
  --source "https://x.com/..." \
  --source "https://video.weibo.com/show?fid=..."
```

带登录态：

```bash
bash scripts/run.sh \
  --cookies-from-browser chrome \
  --referer "https://mp.weixin.qq.com/" \
  --source "https://mp.weixin.qq.com/s/xxxxxxxx"
```

运行轻量回归：

```bash
python scripts/run_regression.py --preset core
```

## Example Output

成功执行后，CLI 会输出一个 JSON 摘要，例如：

```json
{
  "schema_version": "1.0.0",
  "status": "success",
  "report_title": "GitHub专项验证",
  "output_dir": "/Users/you/Desktop/内容摘要/2026-03-26/20260326_024343_GitHub专项验证",
  "report_md": "/Users/you/Desktop/内容摘要/2026-03-26/20260326_024343_GitHub专项验证/report.md",
  "report_json": "/Users/you/Desktop/内容摘要/2026-03-26/20260326_024343_GitHub专项验证/report.json",
  "item_count": 1,
  "success_count": 1,
  "partial_count": 0,
  "failed_count": 0
}
```

## How It Works

主链路大致如下：

1. 识别来源类型
2. 针对 GitHub、网页、动态页面、视频平台分别走不同 extractor
3. 生成 `summary / highlights / keywords`
4. 生成 `report.md` 和 `report.json`

核心策略：

- GitHub：`GitHub API + README`
- 普通网页：`trafilatura`
- 动态/反爬页面：`Scrapling`
- 视频/社媒：优先 `yt-dlp` 字幕，拿不到字幕时回退 `ffmpeg + whisper-cli`
- 分析层：优先 OpenAI-compatible responses，失败时回退本地 heuristic

## Platform Support

| Platform | Current State | Notes |
| --- | --- | --- |
| GitHub | Stable | 专项抽取仓库描述、stars、topics、README |
| Generic web pages | Stable | 主链路为 `trafilatura` |
| WeChat | Stable | 通常走 `Scrapling` |
| Zhihu / CSDN | Stable | 已做真实回归 |
| Toutiao | Usually works | 依赖页面结构和反爬状态 |
| Bilibili | Usually works | 字幕优先，无字幕则转写 |
| Xiaohongshu | Usually works | 可能需要转写，作者名不一定总能取到昵称 |
| Weibo | Mixed | 短视频可能只有 metadata-only partial |
| X/Twitter | Mixed | 视频内容通常可抽取，但可能依赖转写质量 |
| Douyin / YouTube | Untested in CI | 支持路径已实现，建议用真实链接验证 |

## Environment Variables

完整列表见 [.env.example](./.env.example)。

最常用的是：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `CONTENT_PROCESSOR_ANALYSIS_MODE`
- `CONTENT_PROCESSOR_ANALYSIS_MODEL`
- `CONTENT_PROCESSOR_COOKIES_FILE`
- `CONTENT_PROCESSOR_COOKIES_FROM_BROWSER`
- `WHISPER_MODEL`

## OpenClaw Integration

- [SKILL.md](./SKILL.md) 是给 OpenClaw agent 读的机器说明
- [agents/openai.yaml](./agents/openai.yaml) 是 OpenClaw UI 的展示配置
  - 定义了 display name、short description 和默认提示词
  - 对纯命令行用户来说不是必须文件

## Testing

本地运行：

```bash
python3 -m py_compile scripts/process_share_links.py
python3 -m unittest discover -s tests -v
python3 scripts/run_regression.py --preset github
```

GitHub Actions 会跑最基础的 Python 侧检查，但不会在 CI 中执行所有真实平台的 live regression。

## Limitations

- 视频平台最慢的路径是 `yt-dlp + whisper-cli`，一次运行几十秒到数分钟都可能是正常现象
- 部分平台需要 cookie / referer / browser session 才能稳定抓取
- 超短、无语音或纯音乐视频，即使成功拿到元数据，也可能没有可用正文

## Contributing

见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## License

This repository uses the MIT License.

- Commercial use is allowed
- Modification and redistribution are allowed
- The software is provided without warranty

See [LICENSE](./LICENSE).
