# OpenClaw Content Processor

> 面向 OpenClaw 和 Obsidian 的 AI 链接处理管道。把 GitHub 仓库、文章和短视频链接，沉淀成你 Vault 里的可复用知识卡片。

[English](./README.md) | 简体中文

[![CI](https://github.com/jjjojoj/openclaw-content-processor/actions/workflows/ci.yml/badge.svg)](https://github.com/jjjojoj/openclaw-content-processor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

`openclaw-content-processor` 既是一个 OpenClaw skill，也是一个可独立运行的 CLI 工具。它现在的主线任务，已经不是“在聊天里回一句摘要”，而是“抓取来源 -> 用 AI 做结构化理解 -> 写进 Obsidian 形成知识卡片”。桌面报告仍然保留，但只作为兼容路径。

![Obsidian 关系图预览](./assets/obsidian-graph-preview.svg)

## 为什么这个仓库现在更像一个产品

- Obsidian 优先：一条来源对应一张知识卡片，而不是一次性聊天回复
- GitHub 专项链路：仓库内容会自动挂到 `MOC/GitHub` 分支下
- AI 分析层是主角：支持 OpenAI `responses`，也支持 GLM / MiniMax 这类 `chat/completions`
- 抓取链路分层明确：DeepWiki / GitHub API / README / `trafilatura` / `Scrapling` / `yt-dlp` / `whisper-cli` / Playwright
- 交付范围清晰：当前不做飞书 / 飞书知识库，只做本地和 Obsidian

## main 分支当前状态

当前稳定 tag：`v2.4.0`

但仓库 `main` 已经包含了几项比 `v2.4.0` 更新的能力：

- GitHub 卡片改成 DeepWiki 优先，GitHub API + README 只做兜底和证据补充
- GitHub 卡片默认按“学生怎么学这个仓库”来组织结构
- 短视频卡片的标题、作者、要点渲染更干净
- skill 目录下的 `.env` 会自动加载
- `2026-04-22` 最新本地验证：`py_compile` 通过，`67` 项测试全绿

## 用 OpenClaw 安装

如果你想 OpenClaw 直接帮你安装并完成开箱即用配置，可以直接复制这段提示词：

```text
请帮我从 GitHub 安装这个 OpenClaw skill，并配置到可以直接使用：
https://github.com/jjjojoj/openclaw-content-processor.git

安装完成后请继续：
1. 运行它需要的 bootstrap / setup。
2. 检查 ffmpeg、whisper-cli 等依赖是否齐全。
3. 如果我用 Obsidian，帮我配置 Vault 路径，并告诉我立刻就能运行的命令。
4. 如果可以复用我本地 OpenClaw 的 GLM / z.ai provider，也一起启用。
```

如果 OpenClaw 的 skill 列表没有立刻刷新，重启一次即可。

## 它现在适合做什么

- 处理 GitHub 仓库
- 处理普通网页文章
- 处理微信公众号、知乎、CSDN、头条等动态页面
- 处理抖音、B 站、小红书、微博、X/Twitter、YouTube 等视频或社媒链接
- 把最终结果沉淀到 Obsidian；桌面输出只保留为 fallback / compatibility

## 链路怎么走

### 1. 收集来源

一批链接一次跑完，保留输入顺序，当成一个批次处理。

### 2. 抽取层

- GitHub：`DeepWiki overview -> GitHub API 元数据 -> README / headings`
- 文章页：`trafilatura`
- 更难抓的动态页：`Scrapling`
- 视频 / 媒体：优先字幕，没有字幕就 `ffmpeg + whisper-cli`
- 抖音：`已有认证 -> 扫码登录重试 -> Playwright 下载兜底`

### 3. 分析层

- 官方 OpenAI：`responses`
- GLM / MiniMax / 兼容服务：`chat/completions`
- 如果 OpenClaw 本地已经配好 `zai`，这个 skill 可以直接复用

### 4. 交付层

- 推荐：Obsidian knowledge-card 单卡片
- 兼容：桌面 `report.md` / `report.json`
- 结构化元数据始终保留在同级 `*.report.json`

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

### 3. 配置 Obsidian 输出

最省心的方式，是把 Vault 配置直接写进 `.env`：

```env
CONTENT_PROCESSOR_OUTPUT_MODE=obsidian
CONTENT_PROCESSOR_OBSIDIAN_VAULT=/absolute/path/to/your/vault
CONTENT_PROCESSOR_OBSIDIAN_FOLDER=Inbox/内容摘要
CONTENT_PROCESSOR_OBSIDIAN_LAYOUT=knowledge-card
```

如果你已经在 OpenClaw 里配好了 GLM Coding Plan，也可以直接复用：

```env
CONTENT_PROCESSOR_USE_OPENCLAW_ZAI=1
CONTENT_PROCESSOR_OPENCLAW_MODEL_REF=zai/glm-4.7
```

完整配置项见 [`.env.example`](./.env.example)。

### 4. 直接运行

推荐先用 GitHub 仓库试：

```bash
bash scripts/run.sh "https://github.com/NousResearch/hermes-agent"
```

显式 Obsidian 模式：

```bash
bash scripts/run.sh \
  --knowledge-card \
  --vault "$HOME/Documents/MyVault" \
  --folder "Inbox/内容摘要" \
  "https://github.com/NousResearch/hermes-agent"
```

如果也想顺手做依赖检查：

```bash
bash scripts/run.sh --auto-bootstrap "https://github.com/NousResearch/hermes-agent"
```

## 使用示例

### GitHub + 文章

```bash
bash scripts/run.sh \
  --title "AI 阅读收件箱" \
  --source "https://github.com/NousResearch/hermes-agent" \
  --source "https://mp.weixin.qq.com/s/xxxxxxxx"
```

### Obsidian 优先工作流

```bash
bash scripts/run.sh \
  --obsidian \
  --vault "$HOME/Documents/MyVault" \
  --folder "Inbox/内容摘要" \
  --title "今日知识卡片" \
  --source "https://github.com/anomalyco/opencode" \
  --source "https://v.douyin.com/xxxxxxxx/"
```

### 带浏览器登录态

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

登录成功后，skill 会把认证保存到 `auth/douyin/`，后续处理抖音链接时自动复用。如果你只是想先确认真实视频地址能不能解析出来：

```bash
bash scripts/run.sh --resolve-douyin-url "https://v.douyin.com/xxxxxxxx/"
```

如果你是在自托管 runner、VNC 会话或远程桌面环境里，并且现场确实有人能扫码，也可以显式放开“非 TTY 允许扫码登录”：

```bash
CONTENT_PROCESSOR_ALLOW_NON_TTY_DOUYIN_LOGIN=1 \
bash scripts/run.sh --login-douyin
```

## Obsidian 里会生成什么

推荐的 knowledge-card 布局：

```text
<Vault>/Inbox/内容摘要/
  _index.md
  MOC/
    GitHub/
      GitHub 仓库.md
      AI Agent.md
      Developer Tool.md
  YYYY-MM-DD/
    NousResearch_hermes-agent.md
    OpenCode_保姆级配置与实战指南.md
    20260422_205925_OpenCode全攻略.report.json
```

几个关键点：

- 一条来源对应一张 markdown 卡片
- GitHub 卡片标题直接使用仓库名
- GitHub 卡片会自动挂到 `MOC/GitHub` 分类分支
- `_index.md` 是总入口
- `_log.md` 和 per-run `items/` 文件夹已经不再生成

## 输出风格示例

当前这套链路已经真实生成过这两类卡片：

- `NousResearch/hermes-agent`：GitHub 学习卡片，会拆成“这个项目在解决什么”“系统怎么拆”“先看哪些文件”
- `OpenCode 保姆级配置与实战指南`：抖音视频转写后，再整理成适合学习和回看的知识卡片

这就是这套 skill 想要的效果：对人类可读，对 Obsidian 图谱和 Dataview 友好，同时又尽量基于抓取证据，而不是空口编摘要。

## 平台支持

当前稳定 tag：`v2.4.0`

| 平台 | 状态 | 说明 |
| --- | --- | --- |
| GitHub | 稳定 | 当前 `main` 已改成 DeepWiki 优先，GitHub API + README 做兜底与证据补充 |
| 普通网页 | 稳定 | 主链路为 `trafilatura` |
| 微信公众号 | 稳定 | 通常由 `Scrapling` 处理 |
| 知乎 / CSDN | 稳定 | 已完成真实链接验证 |
| 头条 | 基本可用 | 成功率依赖页面结构和反爬状态 |
| Bilibili | 基本可用 | 优先字幕，拿不到字幕就转写 |
| 小红书 | 基本可用 | 可能需要媒体转写 |
| X/Twitter | 条件可用 | 公开视频常可处理，但质量受转写影响 |
| 微博 | 条件可用 | 极短视频可能退化为 `metadata-only partial` |
| 抖音 | 基本可用 | 顺序为 `已有认证 -> 扫码登录 -> Playwright 下载兜底` |
| YouTube | 已实现 | 公开视频通常可直接处理 |

## 验证状态

仓库首页文档尽量保持“可核验”，不是只写好听的话。当前可以确认的是：

- 稳定发布基线：`v2.4.0`
- `2026-04-22` 最新 `main` 本地验证：`py_compile` 通过，`67` 项测试通过
- GitHub 代表样本：`deepwiki overview`
- 抖音代表样本：`playwright douyin download + whisper-cli`

更完整的稳定版门槛、公共 CI 与自托管 runner 测试策略、手工回归备注，见 [docs/release-validation.zh-CN.md](./docs/release-validation.zh-CN.md)。

## 范围与边界

- Obsidian 是一级输出目标
- 桌面输出只作为兼容路径
- 不支持飞书 / 飞书知识库上传
- 当你要求 `--analysis-mode llm` 且模型不可用时，可以直接 fail-fast，而不是假装成功

## License

MIT，详见 [LICENSE](./LICENSE)。
