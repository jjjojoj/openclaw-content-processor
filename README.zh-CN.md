# OpenClaw Content Processor

> 把分享链接整理成落地到桌面的信息汇总报告。

[English](./README.md) | 简体中文

[![CI](https://github.com/jjjojoj/openclaw-content-processor/actions/workflows/ci.yml/badge.svg)](https://github.com/jjjojoj/openclaw-content-processor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

`openclaw-content-processor` 是一个 OpenClaw skill，也是一个可独立运行的命令行工具。它会接收一个或多个分享链接，按来源类型自动抓取、清洗、归纳，并输出本地 `report.md + report.json`。

![报告预览](./assets/report-preview.svg)

适合处理的来源包括：

- GitHub 仓库
- 普通网页文章
- 微信公众号、知乎、CSDN、头条等动态页面
- Bilibili、小红书、微博、X/Twitter、抖音、YouTube 等视频或社媒分享链接

## 项目定位

这个项目不是“只在聊天里回一句摘要”的链接工具，而是偏向本地工作流：

- 本地优先：先把报告保存到磁盘
- 多链接批处理：一批链接生成一份报告
- 分层回退：GitHub、网页、动态页、媒体链接分别走不同 extractor
- 自动化友好：同时输出 Markdown 和结构化 JSON

## 当前状态

当前建议作为 `beta` 发布。

已在 `2026-03-26` 做过真实回归的平台：

| 平台 | 状态 | 说明 |
| --- | --- | --- |
| GitHub | 稳定 | 走 GitHub API + README 专项抽取 |
| 普通网页 | 稳定 | 主链路为 `trafilatura` |
| 微信公众号 | 稳定 | 通常由 `Scrapling` 处理 |
| 知乎 / CSDN | 稳定 | 已完成真实链接验证 |
| 头条 | 基本可用 | 成功率依赖页面结构和反爬状态 |
| Bilibili | 基本可用 | 优先字幕，拿不到字幕就转写 |
| 小红书 | 基本可用 | 可能需要媒体转写 |
| X/Twitter | 条件可用 | 公开视频常可处理，但质量受转写影响 |
| 微博 | 条件可用 | 极短视频可能退化为 `metadata-only partial` |
| 抖音 / YouTube | 已实现 | 建议用真实业务链接继续验证 |

## 发布前验证

在切 `v2.3.0` 正式版前，这个仓库按两层方式做验证：

- 安装验证：`bash scripts/bootstrap.sh --install-python`、`bash scripts/bootstrap.sh`、`.venv/bin/python -m py_compile ...`、`.venv/bin/python -m unittest discover -s tests -v`
- 真实链接验证：`2026-03-26` 已对 GitHub、知乎、CSDN、头条、Bilibili、微信公众号、小红书、X/Twitter、微博做过公开样本回归

详细结果、命令和平台备注见 [docs/release-validation.zh-CN.md](./docs/release-validation.zh-CN.md)。

## 功能概览

| 能力 | 说明 |
| --- | --- |
| GitHub 抽取 | 提取仓库描述、stars、topics、默认分支、README |
| 网页正文抽取 | 通过 `trafilatura` 获取文章正文 |
| 动态页 fallback | 通过 `Scrapling` 处理更难抓的页面 |
| 媒体处理链路 | 优先 `yt-dlp` 字幕，无字幕则 `ffmpeg + whisper-cli` |
| 本地分析 | 生成 summary、highlights、keywords、analysis |
| 结构化输出 | 保存 `report.md`、`report.json` 和逐项 JSON |
| 批处理容错 | 单条失败不会拖垮整批 |

## 快速开始

### 1. 安装系统依赖

macOS:

```bash
brew install ffmpeg whisper-cpp
```

### 2. 安装本地 Python runtime

```bash
bash scripts/bootstrap.sh --install-python
```

这一步会把下面这些依赖装进 skill 自己的 `.venv/`：

- `yt-dlp`
- `trafilatura`
- `Scrapling`

### 3. 直接运行

```bash
bash scripts/run.sh "https://github.com/shadcn-ui/ui"
```

如果也想顺手检查系统依赖：

```bash
bash scripts/run.sh --auto-bootstrap "https://github.com/shadcn-ui/ui"
```

## 使用方式

### 基础命令

```bash
bash scripts/run.sh \
  "https://github.com/shadcn-ui/ui" \
  "https://mp.weixin.qq.com/s/xxxxxxxx"
```

### 显式标题与来源

```bash
bash scripts/run.sh \
  --title "今日链接汇总" \
  --source "https://x.com/..." \
  --source "https://video.weibo.com/show?fid=..."
```

### 带登录态

```bash
bash scripts/run.sh \
  --cookies-from-browser chrome \
  --referer "https://mp.weixin.qq.com/" \
  --source "https://mp.weixin.qq.com/s/xxxxxxxx"
```

### 运行轻量回归

```bash
python scripts/run_regression.py --preset core
```

## 输出结果

默认输出根目录：

```text
~/Desktop/内容摘要/YYYY-MM-DD/<timestamp>/
```

每次运行会生成：

```text
report.md
report.json
items/
  source-1.json
  source-2.json
```

`report.json` 里会包含：

- 整体状态
- 成功 / 部分成功 / 失败计数
- 工具与分析元信息
- 每个来源的摘要、告警、抽取方式和内容统计

CLI 结束时会输出一个 JSON 概览，例如：

```json
{
  "schema_version": "1.0.0",
  "status": "success",
  "report_title": "GitHub validation",
  "output_dir": "/Users/you/Desktop/内容摘要/2026-03-26/20260326_024343_GitHub验证",
  "report_md": "/Users/you/Desktop/内容摘要/2026-03-26/20260326_024343_GitHub验证/report.md",
  "report_json": "/Users/you/Desktop/内容摘要/2026-03-26/20260326_024343_GitHub验证/report.json",
  "item_count": 1,
  "success_count": 1,
  "partial_count": 0,
  "failed_count": 0
}
```

## 抽取策略

不同来源会走不同管线：

- GitHub 仓库：`GitHub API + README`
- 普通网页：`trafilatura`
- 动态 / 反爬页面：`Scrapling`
- 媒体链接：优先 `yt-dlp` 字幕
- 没有可用字幕：回退 `ffmpeg + whisper-cli`
- 分析层：优先 OpenAI-compatible responses，失败时回退本地 heuristic

## 配置说明

完整配置见 [.env.example](./.env.example)。

最常用的环境变量包括：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `CONTENT_PROCESSOR_ANALYSIS_MODE`
- `CONTENT_PROCESSOR_ANALYSIS_MODEL`
- `CONTENT_PROCESSOR_COOKIES_FILE`
- `CONTENT_PROCESSOR_COOKIES_FROM_BROWSER`
- `CONTENT_PROCESSOR_COOKIE_HEADER`
- `CONTENT_PROCESSOR_REFERER`
- `WHISPER_MODEL`

## OpenClaw 集成

仓库里同时包含给人看的文档和给 OpenClaw 用的 skill 文件：

- [README.md](./README.md)：英文说明
- [README.zh-CN.md](./README.zh-CN.md)：中文说明
- [SKILL.md](./SKILL.md)：OpenClaw skill 指令
- [agents/openai.yaml](./agents/openai.yaml)：OpenClaw UI 元数据

如果你只把它当命令行工具使用，`agents/openai.yaml` 不是必需文件。

## 仓库结构

```text
.
├── assets/
│   └── report-preview.svg
├── docs/
│   ├── release-validation.md
│   └── release-validation.zh-CN.md
├── README.md
├── README.zh-CN.md
├── CHANGELOG.md
├── LICENSE
├── SKILL.md
├── .env.example
├── .github/workflows/ci.yml
├── agents/openai.yaml
├── scripts/
│   ├── bootstrap.sh
│   ├── run.sh
│   ├── process_share_links.py
│   └── run_regression.py
└── tests/
    └── test_process_share_links.py
```

## 开发与验证

本地检查：

```bash
python3 -m py_compile scripts/process_share_links.py scripts/run_regression.py
python3 -m unittest discover -s tests -v
python3 scripts/run_regression.py --preset github
```

GitHub Actions 当前会跑：

- 本地 runtime bootstrap
- Python compile check
- 单测

CI 不会跑所有真实平台的 live regression。

## 已知限制

- 最慢的路径通常是媒体转写，单次运行几分钟都可能是正常现象
- 某些平台需要 cookie、browser session 或 referer 才能更稳定
- 极短、无语音或纯音乐视频，可能只有 `metadata-only partial`
- 社媒平台反爬策略会变化，成功率会随时间波动

## 贡献方式

见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## License

MIT，详见 [LICENSE](./LICENSE)。
