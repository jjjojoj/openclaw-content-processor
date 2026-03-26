---
name: content-processor
version: 2.3.0
description: 处理用户分享的网页、公众号、知乎、CSDN、头条、YouTube、B站、抖音、小红书、微博、X/Twitter 等链接。当用户提到分享链接、多平台链接、内容摘要、汇总报告、整理链接、保存到桌面时触发。自动抽取内容并在桌面生成 Markdown + JSON 汇总报告。
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

把用户给出的一个或多个分享链接整理成桌面报告。这个 skill 的主路径是本地落地：先抓取内容，再生成 `report.md` 和 `report.json`，最后把路径返回给用户。

## Quick Start

一键完成推荐安装：

```bash
bash "$SKILL_DIR/scripts/bootstrap.sh" --install
```

如果只是先跑起来，也可以直接执行：

```bash
bash "$SKILL_DIR/scripts/run.sh" "<url1>" "<url2>"
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
  --report-title "吴总今日信息汇总" \
  "https://mp.weixin.qq.com/..." \
  "https://v.douyin.com/..."
```

或者用更产品化一点的入口别名：

```bash
bash "$SKILL_DIR/scripts/run.sh" \
  --title "吴总今日信息汇总" \
  --source "https://mp.weixin.qq.com/..." \
  --source "https://github.com/shadcn-ui/ui"
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

## What The Script Produces

默认输出目录：

```text
~/Desktop/内容摘要/YYYY-MM-DD/<timestamp>/
```

目录内会生成：

- `report.md` - 给人看的汇总报告
- `report.json` - 结构化数据，包含 `schema_version`、整体状态、tool info 和逐项状态
- `items/*.json` - 每个来源的单独抽取结果

## Required Workflow

### 1. 收集链接

- 从用户消息中提取全部 URL，保持原顺序。
- 同一批链接只生成一份报告。
- 不要要求用户重复发送已经给过的链接。

### 2. 先保存到桌面

- 默认优先级是本地桌面报告。
- 任何外部上传都是可选能力，只有用户明确要求时才做。

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
- AI 分析：优先走 OpenAI-compatible `responses`，不可用时回退到本地启发式分析
- 实在抽不出正文时：保留元数据并写入告警

### 4. 汇报结果

至少告诉用户：

- 报告保存路径
- 成功处理了几个链接
- 哪些链接只拿到部分内容或失败
- 2 到 5 条最重要的结论

## Rules

- 本 skill 的默认目标是“整理成报告”，不是只返回聊天里的摘要。
- 如果部分链接失败，继续处理其它链接，不要整批放弃。
- 如果用户只给一个链接，也照样生成桌面报告。
- 如果用户要求更深度分析，先读取 `report.json` 再继续扩展，而不是重新抓取。
- 命令退出码约定：`0 = 全部成功`，`2 = 部分成功`，`3 = 全部失败但已生成报告`。
- `--analysis-mode auto` 会优先尝试 `OPENAI_API_KEY`，失败时自动回退到本地分析。

## Dependency Notes

- 用户感知上这是一个“单 skill 完成”的方案：网页抽取、GitHub 抽取、媒体字幕抓取都已收进本 skill。
- `yt-dlp` 现在作为 skill 自己 `.venv/` 里的 Python 依赖安装，不再要求全局单独安装。
- `ffmpeg + whisper-cli` 是字幕缺失时的视频转写兜底。
- `trafilatura` 是网页正文抽取主引擎，`summarize` 退居为可选 fallback / PDF 辅助工具。
- `Scrapling` 用于公众号、头条、小红书、微博、知乎、CSDN 这类更难抓的页面。
- GitHub 仓库页不再按普通网页处理，而是走 GitHub API + README 专门抽取。
- Python 侧依赖写在 `requirements.txt`，`bootstrap.sh --install-python` 或首次 `run.sh` 会安装到 skill 自己的 `.venv/`。
- 登录态优先顺序：`--cookie-header` > `--cookies-file`；视频平台额外支持 `--cookies-from-browser` 给 `yt-dlp` 使用。
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
