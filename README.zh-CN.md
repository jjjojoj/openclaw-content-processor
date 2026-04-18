# OpenClaw Content Processor

> 把分享链接整理成适合 Obsidian 的本地笔记和信息汇总报告。

[English](./README.md) | 简体中文

[![CI](https://github.com/jjjojoj/openclaw-content-processor/actions/workflows/ci.yml/badge.svg)](https://github.com/jjjojoj/openclaw-content-processor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

`openclaw-content-processor` 是一个 OpenClaw skill，也是一个可独立运行的命令行工具。它会接收一个或多个分享链接，按来源类型自动抓取、清洗、归纳，并输出本地 Markdown + JSON 结果。现在也支持直接写入 Obsidian Vault，自动生成 frontmatter 和单条来源笔记。

![报告预览](./assets/report-preview.svg)

## 用 OpenClaw 安装

如果你想 OpenClaw 直接帮你安装并完成开箱即用配置，可以直接复制这段提示词：

```text
请帮我从 GitHub 安装这个 OpenClaw skill，并配置到可以直接使用：
https://github.com/jjjojoj/openclaw-content-processor.git

安装完成后请继续：
1. 运行它需要的 bootstrap / setup。
2. 检查 ffmpeg、whisper-cli 等依赖是否齐全。
3. 如果我用 Obsidian，告诉我 Vault 路径怎么配，以及现在立刻就能处理链接的命令。
```

如果 OpenClaw 的 skill 列表没有立刻刷新，重启一次即可。

适合处理的来源包括：

- GitHub 仓库
- 普通网页文章
- 微信公众号、知乎、CSDN、头条等动态页面
- Bilibili、小红书、微博、X/Twitter、抖音、YouTube 等视频或社媒分享链接

## 项目定位

这个项目不是“只在聊天里回一句摘要”的链接工具，而是偏向本地工作流：

- 本地优先：先把内容落到本地笔记，Obsidian 也是一级目标
- 多链接批处理：一批链接生成一份报告
- 分层回退：GitHub、网页、动态页、媒体链接分别走不同 extractor
- 自动化友好：同时输出 Markdown 和结构化 JSON

## 当前状态

当前稳定版本：`v2.3.0`

稳定版验证最近一次刷新时间：`2026-03-26`

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
| 抖音 | 基本可用 | 顺序为“已有 cookie -> 扫码登录 -> Playwright 下载兜底” |
| YouTube | 已实现 | 公开视频通常可直接处理 |

## 发布验证

当前稳定版由两层验证支撑：

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
| Obsidian 导出 | 输出 Vault 友好的 frontmatter 笔记，并为每个来源生成独立 markdown |
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

桌面 / 本地报告模式：

```bash
bash scripts/run.sh "https://github.com/openai/openai-python"
```

Obsidian 模式：

```bash
bash scripts/run.sh \
  --obsidian \
  --vault "$HOME/Documents/MyVault" \
  --folder "Inbox/内容摘要" \
  "https://github.com/openai/openai-python"
```

如果也想顺手检查系统依赖：

```bash
bash scripts/run.sh --auto-bootstrap "https://github.com/openai/openai-python"
```

## 使用方式

### 基础命令

```bash
bash scripts/run.sh \
  "https://github.com/openai/openai-python" \
  "https://mp.weixin.qq.com/s/xxxxxxxx"
```

### 显式标题与来源

```bash
bash scripts/run.sh \
  --title "今日链接汇总" \
  --source "https://x.com/..." \
  --source "https://video.weibo.com/show?fid=..."
```

### Obsidian 优先工作流

```bash
bash scripts/run.sh \
  --obsidian \
  --vault "$HOME/Documents/MyVault" \
  --folder "Inbox/内容摘要" \
  --title "AI 链接收件箱" \
  --source "https://github.com/openai/openai-python" \
  --source "https://mp.weixin.qq.com/s/xxxxxxxx"
```

### 带登录态

```bash
bash scripts/run.sh \
  --cookies-from-browser chrome \
  --referer "https://mp.weixin.qq.com/" \
  --source "https://mp.weixin.qq.com/s/xxxxxxxx"
```

### 抖音扫码登录

```bash
bash scripts/run.sh --login-douyin
```

登录成功后，skill 会把认证保存到 `auth/douyin/`，之后处理抖音链接时会自动复用。如果你只是想先确认真实视频地址能不能解析出来，可以运行：

```bash
bash scripts/run.sh --resolve-douyin-url "https://v.douyin.com/xxxxxxxx/"
```

抖音媒体链路的顺序是：

- 先尝试已有 cookie / 登录态
- 认证失败时自动触发一次扫码登录重试
- 仍然失败再回退到 Playwright 网络拦截下载

临时下载用于转写的 mp4 会在转写完成后自动删除，不会留在最终报告目录里。

### 运行轻量回归

```bash
python scripts/run_regression.py --preset core
```

## 输出结果

默认桌面输出根目录：

```text
~/Desktop/内容摘要/YYYY-MM-DD/<timestamp>/
```

桌面模式会生成：

```text
report.md
report.json
items/
  source-1.json
  source-2.json
```

Obsidian 模式会生成：

```text
<Vault>/<Folder>/YYYY-MM-DD/<timestamp_title>/
  <timestamp_title>.md
  report.json
  items/
    01_title.json
  sources/
    01_platform_title.md
```

其中 Obsidian 导出包含：

- 一条整批汇总笔记
- 每个来源一条独立 markdown 笔记
- 适合 Dataview / 过滤 / 标签的 YAML frontmatter
- 汇总笔记和来源笔记之间的相对链接

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
- `CONTENT_PROCESSOR_OUTPUT_MODE`
- `CONTENT_PROCESSOR_OBSIDIAN_VAULT`
- `CONTENT_PROCESSOR_OBSIDIAN_FOLDER`
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
