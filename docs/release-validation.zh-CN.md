# 发布验证说明

最后更新：`2026-04-22`

这个文件现在明确区分两件事：

- 稳定版基线：`v2.4.0`
- 当前 `main` 分支快照：已经包含更多 AI + Obsidian 相关更新

## 稳定版基线：`v2.4.0`

下面这套检查，是切出 `v2.4.0` 时的发布基线，也应该继续作为后续稳定版的最低门槛。

### 安装验证

```bash
bash scripts/bootstrap.sh --install-python
bash scripts/bootstrap.sh
.venv/bin/python -m py_compile scripts/process_share_links.py scripts/run_regression.py
.venv/bin/python -m unittest discover -s tests -v
```

`2026-04-19` 的基线结果：

- `bootstrap.sh --install-python`：通过
- `bootstrap.sh`：通过
- `py_compile`：通过
- `unittest`：通过（当时为 `33` 项）

### 自动化公开样本回归

入口命令：

```bash
.venv/bin/python scripts/run_regression.py --preset extended --analysis-mode heuristic
```

`extended` 预设覆盖：

- GitHub
- 知乎
- CSDN
- 头条
- Bilibili

它的目标是在不依赖私有 cookie、登录态和付费接口的前提下，验证主抽取链路仍能工作。

`2026-04-19` 基线结果：通过（`5/5 success`）

| 平台 | 结果 | 抽取路径 |
| --- | --- | --- |
| GitHub | success | `github api + readme` |
| 知乎 | success | `scrapling fetch [.Post-RichText]` |
| CSDN | success | `scrapling fetch [#article_content]` |
| 头条 | success | `scrapling stealthy-fetch [.article-content]` |
| Bilibili | success | `yt-dlp download + whisper-cli` |

## 当前 `main` 分支快照

下面这些结果描述的是仓库当前 `main` 的真实状态，不等于最近一个 stable tag。

### `2026-04-22` 本地验证

```bash
.venv/bin/python -m py_compile scripts/process_share_links.py scripts/douyin_auth.py scripts/run_regression.py
.venv/bin/python -m unittest discover -s tests -v
```

结果：

- `py_compile`：通过
- `unittest`：通过（`67` 项）

### 当前已经真实生成出的代表性产物

这些不是口头描述，而是当前 Obsidian Vault 里已经存在的真实产物。

| 来源类型 | 结果 | 抽取路径 |
| --- | --- | --- |
| GitHub 仓库 | success | `deepwiki overview` |
| 抖音短视频 | success | `playwright douyin download + whisper-cli` |

当前链路已经真实写出的代表性卡片包括：

- `NousResearch/hermes-agent`
- `OpenCode 保姆级配置与实战指南`

## 手工真实链接回归备注

除了上面的公开预设，这个项目也在 `2026-03-26`、`2026-04-19`、`2026-04-22` 附近的加固周期里，手工验证过几类公开分享链接。

| 平台 | 结果 | 常见抽取路径 |
| --- | --- | --- |
| GitHub | success | `deepwiki overview` 或 `github api + readme` |
| 知乎 | success | 文章正文抽取 |
| CSDN | success | 文章正文抽取 |
| 头条 | success | `scrapling stealthy-fetch [.article-content]` |
| Bilibili | success | `yt-dlp download + whisper-cli` |
| 微信公众号 | success | `scrapling stealthy-fetch [#js_content]` |
| 小红书 | success | `yt-dlp download + whisper-cli` |
| X/Twitter | success | `yt-dlp download + whisper-cli` |
| 微博 | partial | 极短视频可能回退到 `yt-dlp metadata only` |
| 抖音 | success | `playwright douyin download + whisper-cli` |

说明：

- `partial` 是有意保留的诚实结果，不是静默失败
- 社媒平台成功率会随着反爬策略变化而波动
- 如果业务场景需要更稳的访问，当前仓库已经支持 cookie、browser session、saved auth 和 referer
- 飞书 / 飞书知识库上传不在当前版本范围内

## 公共 CI 与自托管 Runner 的测试分层

推荐策略：

- 公共 CI：
  - runtime bootstrap
  - compile 检查
  - 单测
  - 轻量公开链接回归
  - 抖音登录门禁与 fallback 逻辑的 mock 测试
- 自托管 runner / 本地桌面 smoke test：
  - 真实抖音二维码登录
  - 已保存 cookie 的复用验证
  - Playwright 媒体兜底在真实分享链接上的验证

重要说明：

- 公共 CI 不应该真的执行抖音二维码登录
- 真实扫码登录只适合带桌面、VNC 或远程桌面，并且现场有人能扫码的环境
- 如果你确实在这种环境里跑自动化，可以显式设置 `CONTENT_PROCESSOR_ALLOW_NON_TTY_DOUYIN_LOGIN=1`

## 稳定版发布门槛

在发布新的 stable tag 之前，至少要满足：

- 稳定版基线里的安装检查在干净 runtime 上全部通过
- 单测保持绿色
- 至少一条 GitHub、一条文章页、一条动态页、一条媒体链接成功
- 对微博这类天然 mixed outcome 的平台，要如实写进文档，而不是隐藏
