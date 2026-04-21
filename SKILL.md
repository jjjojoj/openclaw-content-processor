---
name: content-processor
version: 2.4.0
description: 处理用户分享的网页、公众号、知乎、CSDN、头条、YouTube、B站、抖音、小红书、微博、X/Twitter 等链接。当用户提到分享链接、多平台链接、内容摘要、汇总报告、整理链接、保存到 Obsidian 时触发。自动抽取内容并生成写入 Obsidian Vault 的 Markdown + JSON 结果。
metadata:
  clawdbot:
    emoji: "🧾"
    requires:
      bins: [python3, ffmpeg, whisper-cli]
    install:
      - id: ffmpeg-brew
        kind: brew
        formula: ffmpeg
        bins: [ffmpeg]
        label: Install ffmpeg (brew)
      - id: whisper-cpp-brew
        kind: brew
        formula: whisper-cpp
        bins: [whisper-cli]
        label: Install whisper.cpp (brew)
---

# Content Processor

把用户给出的一个或多个分享链接整理成 Obsidian 笔记。这个 skill 的主路径是直接落到 Obsidian Vault：先抓取内容，再生成 Markdown + JSON 结果，并写成 Obsidian 友好的 frontmatter 笔记。

当前正式发布版：`v2.4.0`

本次发布重点：

- Obsidian 导出默认切到 knowledge-card 单笔记，legacy digest 布局仍可兼容启用
- 抖音链路升级为“已有认证 -> 扫码登录 -> Playwright 兜底”
- 仅用于转写的临时 mp4 会在转写后自动清理
- 飞书 / 飞书知识库上传不属于当前 skill 的支持范围，输出目标只有桌面本地报告和 Obsidian Vault

## Quick Start

一键完成推荐安装：

```bash
bash "$SKILL_DIR/scripts/bootstrap.sh" --install
```

如果只是先跑起来，也可以直接执行：

```bash
bash "$SKILL_DIR/scripts/run.sh" "<url1>" "<url2>"
```

如果你已经有 Obsidian Vault，推荐直接这样跑：

```bash
bash "$SKILL_DIR/scripts/run.sh" \
  --obsidian \
  --vault "$HOME/Documents/MyVault" \
  --folder "Inbox/内容摘要" \
  "<url1>" "<url2>"
```

`run.sh` 首次运行会自动补本地 `.venv/`，把 `Scrapling / trafilatura / yt-dlp` 装进 skill 自己的运行时。

想做回归测试时：

```bash
python "$SKILL_DIR/scripts/run_regression.py" --preset core
```

处理一个或多个链接：

```bash
bash "$SKILL_DIR/scripts/run.sh" \
  "https://example.com/article" \
  "https://www.bilibili.com/video/BVxxxxxxxxx"
```

自定义报告标题：

```bash
bash "$SKILL_DIR/scripts/run.sh" \
  --report-title "今日信息汇总" \
  "https://mp.weixin.qq.com/..." \
  "https://v.douyin.com/..."
```

或者用更产品化一点的入口别名：

```bash
bash "$SKILL_DIR/scripts/run.sh" \
  --title "多平台链接汇总" \
  --source "https://mp.weixin.qq.com/..." \
  --source "https://github.com/openai/openai-python"
```

需要登录态时：

```bash
bash "$SKILL_DIR/scripts/run.sh" \
  --cookies-from-browser chrome \
  --referer "https://mp.weixin.qq.com/" \
  "https://mp.weixin.qq.com/..."
```

或者使用导出的 Netscape cookie 文件：

```bash
bash "$SKILL_DIR/scripts/run.sh" \
  --cookies-file ~/Downloads/cookies.txt \
  "https://www.xiaohongshu.com/..."
```

抖音如果浏览器 cookie 不可用，推荐直接用扫码登录把认证保存到 skill 本地：

```bash
bash "$SKILL_DIR/scripts/run.sh" --login-douyin
```

登录成功后，后续抖音链接会自动复用 `auth/douyin/cookies.txt`。如果你只是想先验证真实视频地址是否能解析出来，可以单独运行：

```bash
bash "$SKILL_DIR/scripts/run.sh" \
  --resolve-douyin-url "https://v.douyin.com/..."
```

## What The Script Produces

桌面模式默认输出目录：

```text
~/Desktop/内容摘要/YYYY-MM-DD/<timestamp>/
```

桌面模式目录内会生成：

- `report.md` - 给人看的汇总报告
- `report.json` - 结构化数据，包含 `schema_version`、整体状态、tool info 和逐项状态
- `items/*.json` - 每个来源的单独抽取结果

Obsidian 模式默认目录结构（knowledge-card）：

```text
<Vault>/<Folder>/
  _index.md              ← 全局索引（每次处理自动追加，wikilink 指向 digest）
  _log.md                ← 操作日志（可 grep：`## [日期] ingest | 标题`）
  YYYY-MM-DD/
    <timestamp_title>/
      知识卡片主题名.md        ← 单条来源的知识卡片（type: knowledge-card）
      report.json
      items/*.json
```

其中：

- `_index.md` 是全局内容索引，每条记录用 `[[wikilink]]` 指向知识卡片，AI 可先扫这个定位
- `_log.md` 是追加式操作日志，`grep "^## \[" _log.md | tail -10` 查最近10次处理
- 默认一条来源对应一张知识卡片，一个 Obsidian 节点
- 所有笔记都带 YAML frontmatter，适合 Obsidian / Dataview
- 默认不再生成 `sources/` 目录；如需旧版 digest+source，可显式传 `--obsidian-layout digest`

## Dataview 查询示例

在 Obsidian 中用 Dataview 查询已处理的内容：

最近 7 天的知识卡片：
```dataview
TABLE WITHOUT ID file.link AS "卡片", digest_date AS "日期", platform AS "平台"
WHERE type = "knowledge-card"
SORT file.cday DESC
```

按平台筛选：
```dataview
TABLE WITHOUT ID file.link AS "笔记", digest_date AS "日期", platform AS "平台"
FROM "Inbox"
WHERE platform_key = "douyin"
SORT digest_date DESC
```

按关键词跨批次聚合：
```dataview
TABLE WITHOUT ID file.link AS "笔记", digest_date AS "日期", platform AS "平台"
FROM "Inbox"
WHERE contains(keywords, "关键词")
SORT digest_date DESC
```

## Required Workflow

### 1. 收集链接

- 从用户消息中提取全部 URL，保持原顺序。
- 同一批链接只生成一份报告。
- 不要要求用户重复发送已经给过的链接。

### 2. 先保存到本地

- 如果用户给了 Obsidian Vault 路径，优先写入 Obsidian。
- 如果没有 Vault 配置，就回退到桌面本地报告。
- 重点是“先落本地文件”，不是只在聊天里回复摘要。

### 3. 运行主脚本

```bash
bash "$SKILL_DIR/scripts/run.sh" "<url1>" "<url2>" ...
```

脚本会自动选择抓取链路：

- GitHub 仓库：优先 GitHub API + README 解析
- 网页类：优先本地 `trafilatura` 抽取
- 反爬/动态页面：自动尝试 `Scrapling` CLI fallback
- 视频/社媒分享：优先 `yt-dlp` 字幕
- 没字幕的视频：回退到 `ffmpeg + whisper-cli`
- 抖音媒体链路：优先已有 cookie / 登录态；认证失败时先尝试扫码登录一次；仍失败再回退到 Playwright 网络下载
- AI 分析：官方 OpenAI 优先走 `responses`；GLM / MiniMax 等非 OpenAI 服务默认兼容 `chat/completions`；不可用时回退到本地启发式分析
- 实在抽不出正文时：保留元数据并写入告警

### 4. 汇报结果

至少告诉用户：

- 报告保存路径
- 成功处理了几个链接
- 哪些链接只拿到部分内容或失败
- 2 到 5 条最重要的结论

## Rules

- 本 skill 的默认目标是“整理成本地笔记/报告”，不是只返回聊天里的摘要。
- 当前不支持飞书 / 飞书知识库上传，请把结果交付到桌面本地目录或 Obsidian Vault。
- 如果部分链接失败，继续处理其它链接，不要整批放弃。
- 如果用户只给一个链接，也照样生成桌面报告。
- 如果用户要求更深度分析，先读取 `report.json` 再继续扩展，而不是重新抓取。
- 命令退出码约定：`0 = 全部成功`，`2 = 部分成功`，`3 = 全部失败但已生成报告`。
- `--analysis-mode auto` 会优先尝试 `OPENAI_API_KEY`，失败时自动回退到本地分析。
- `--output-mode auto` 在配置了 `--obsidian-vault` 或 `CONTENT_PROCESSOR_OBSIDIAN_VAULT` 时会自动切到 Obsidian。

## Dependency Notes

- 用户感知上这是一个“单 skill 完成”的方案：网页抽取、GitHub 抽取、媒体字幕抓取都已收进本 skill。
- `yt-dlp` 现在作为 skill 自己 `.venv/` 里的 Python 依赖安装，不再要求全局单独安装。
- `ffmpeg + whisper-cli` 是字幕缺失时的视频转写兜底。
- `trafilatura` 是网页正文抽取主引擎，`summarize` 退居为可选 fallback / PDF 辅助工具。
- `Scrapling` 用于公众号、头条、小红书、微博、知乎、CSDN 这类更难抓的页面。
- GitHub 仓库页不再按普通网页处理，而是走 GitHub API + README 专门抽取。
- Python 侧依赖写在 `requirements.txt`，`bootstrap.sh --install-python` 或首次 `run.sh` 会安装到 skill 自己的 `.venv/`。
- 登录态优先顺序：`--cookie-header` > `--cookies-file`；视频平台额外支持 `--cookies-from-browser` 给 `yt-dlp` 使用。
- 抖音额外支持 `--login-douyin` 打开 Chromium 扫码登录，并把认证保存到 `auth/douyin/` 供后续自动复用。
- `--resolve-douyin-url` 可以单独验证抖音真实媒体 URL 是否已经可解析，适合排障。
- 主流程里为转写临时下载的媒体文件会在转写完成后自动删除，避免在本地堆积 mp4。
- 长视频和部分小红书分享可能会触发 `yt-dlp + whisper-cli`，这条链路通常需要几十秒到数分钟，属于正常现象。
- 为避免长转写文本拖慢总结阶段，报告分析默认只对前一段稳定窗口做关键词/高亮抽取，不影响原文保存。
- 如果 `whisper-cli` 已安装但模型不存在，优先把模型放到：

```text
~/.whisper-models/ggml-small.bin
```

也可以通过环境变量指定：

```bash
export WHISPER_MODEL=/absolute/path/to/ggml-small.bin
```

---

## Obsidian 知识卡片模式（v2.5.0 规划）

> 2026-04-20 确认：Obsidian 默认输出已切到 knowledge-card 单笔记模式；旧 digest+source 仅作为兼容布局保留。

### 核心原则

1. **一张卡片 = 一个独立知识点**，标题反映核心价值（不是原始视频/文章标题），永远不合并
2. **知识卡片格式**：适用场景 → 方法（原理/操作/观察点/判断标准）→ 注意事项 → 原始转录折叠
3. **标签做轻量分类**，wikilink 做关联，MOC 做主题聚合（3+ 卡片后创建）
4. **目录按日期扁平归档**，不按主题建子目录

### LLM 分析配置

配置文件：`$SKILL_DIR/.env`

```env
CONTENT_PROCESSOR_USE_OPENCLAW_ZAI=1
CONTENT_PROCESSOR_OPENCLAW_MODEL_REF=zai/glm-4.7
```

**已知限制**：
- 智谱 GLM 不支持 OpenAI Responses API（`/v1/responses` → 404），必须走 `/chat/completions`
- 如果复用 OpenClaw 的 `zai` coding-plan 配置，默认分析模型固定为 `glm-4.7`
- coding-plan 场景默认不再推荐 `flash / flashx` 作为分析模型
- MiniMax API 同样不支持 Responses API
- 术语纠正和专有名词校准目前仍主要依赖 prompt / 人工校对，不是独立的后处理模块

### Obsidian Vault 目录结构

```text
信息流/
├── .obsidian/
├── 00-从这里开始.md
├── Inbox/内容摘要/
│   ├── _index.md            ← 全局索引（按日期，wikilink 指向知识卡片）
│   ├── _log.md              ← 操作日志
│   └── YYYY-MM-DD/
│       └── 知识卡片主题名/     ← 一个知识点一个文件夹，一个节点
│           ├── 知识卡片主题名.md  ← 主笔记（结构化知识卡片）
│           ├── items/*.json      ← 原始抽取数据（备用）
│           └── report.json
├── MOC/                      ← 主题总览页（积累 3+ 卡片后按需创建）
│   ├── 识人技巧.md
│   └── AI 工具箱.md
└── attachments/
```

### 知识卡片模板

```markdown
---
title: "精炼主题名（4-8字）"
type: knowledge-card
created: YYYY-MM-DDTHH:MM
source: 平台 @作者
source_url: 原始链接
tags:
  - 主题标签
  - 细分标签
---

# 主题名

> 一句话概括核心价值

## 适用场景
- 场景1 — 简要说明
- 场景2 — 简要说明

---

## 方法一：方法名

**原理：** 一句话说明为什么有效

**操作步骤：**
1. 具体步骤1
2. 具体步骤2

**判断标准：**

| 健康表现 ✅ | 警惕信号 ❌ |
|---|---|
| ... | ... |

> 💡 原理解释（可选）

---

## 方法二：方法名

（同上结构）

---

## 注意事项

- ⚠️ 容易误判的情况
- ⚠️ 限制条件

---

## 原始转录

<details>
<summary>展开查看完整转录（N字）</summary>

转录内容...

</details>
```

### 知识卡片生成流程

1. **抓取内容**：走 content-processor 正常链路（playwright/yt-dlp/whisper）
2. **GLM 结构化提炼**：优先复用 OpenClaw 本地 `zai` provider，coding-plan 默认使用 `glm-4.7`
3. **写入知识卡片**：按模板写入 Obsidian Vault
4. **更新索引**：追加 `_index.md` 和 `_log.md`
5. **汇报用户**：保存路径 + 核心结论

### LLM 提炼 Prompt 模板

```
你是一个知识内化专家。请将以下视频/文章转录内容转化为一篇「可操作的知识卡片」：

1. 取一个精炼的主题名（4-8字，反映核心价值）
2. 结构化输出：适用场景 → 方法（原理/操作/观察点/判断标准）→ 注意事项
3. 忠于原文，不编造原文没有的方法
4. 如果原文只有2个方法就只写2个，不要凑数
5. 语言简洁有力，像操作手册

对于结构不清晰的内容，也要强制结构化。
对于实操型内容，重点提炼「怎么做」而非「讲了什么」。
对于观点型内容，重点提炼「核心论点+论据+适用边界」。
```

### 待改造清单

- [ ] 把知识卡片专用 prompt 进一步从 3 行分析升级为“适用场景 / 方法 / 注意事项”专用结构化输出
- [ ] 自动检测同类标签，提示是否创建 MOC
- [ ] 为术语纠正补一个显式后处理层，而不是只依赖 prompt
