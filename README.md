# notebooklm-cdp-cli

让 NotebookLM 回到你真正工作的浏览器里。
Bring NotebookLM back to the browser you actually work in.

Unofficial NotebookLM CLI with live Chrome identity reuse via CDP.

Language: [中文](#中文) | [English](#english)

---

## 中文

### 是什么

notebooklm-cdp-cli 是一个非官方的 NotebookLM 命令行工具。

它保留 CLI / RPC 的效率，
但把认证思路从 **Playwright 的 storage_state.json**，
换成 **CDP 直连真实 Chrome 登录态**。

一句话概括：命令行负责操作，CDP 负责接入，真实浏览器才是认证锚点。

---

### 为什么要做这个

很多自动化方案默认把 Playwright 的登录态文件当成"身份真相"。

临时脚本，可以。
长期工作，不够。

因为一旦你真的把 NotebookLM 当成办公助手来用，问题就会很明显：

- 真实浏览器是一套身份，自动化环境又是一套身份
- 登录态漂移，维护成本上升
- 你真正工作的浏览器里明明已经登录，自动化这边却还在守着一份状态文件
- 最后，NotebookLM 被锁进了终端，而不是融入你的真实工作流

这个项目不是反对 Playwright。
它反对的是另一件事：不该把离线状态文件，当成长期认证模型。

---

### 适合谁

这个项目主要面向这样的用户：

- 你已经在本地 Chrome / Chromium 中长期登录 Google / NotebookLM
- 你希望复用这套真实身份，而不是维护一份自动化专用登录态
- 你希望 NotebookLM 的主要操作仍然走 CLI / RPC
- 你希望自动化能力尽量贴近真实浏览器，而不是依赖重 DOM 流程

如果你想要的是：

- 完全隔离的自动化专用浏览器
- DOM 自动化优先
- 以 Playwright session 为核心设计

那这可能不是你的主路径。

---

### 当前能力

目前 CLI 覆盖的范围包括：

- browser attach / browser status
- auth check 等认证诊断
- notebook、source、chat、notes、share、research
- artifact 列表与管理
- report / audio / video / slide / infographic 的生成与下载流程
- Gemini Web、Google Flow、Colab 的浏览器命令入口

### 命令矩阵与稳定性

| Product | Command families | Stability |
|---|---|---|
| NotebookLM | `browser`, `auth`, `doctor`, `notebook`, `source`, `chat` / `ask`, `notes`, `share`, `research`, `artifact`, `generate`, `download`, `language` | supported |
| Gemini | `gemini generate text`, `gemini ask`, `gemini generate image`, `gemini generate vision` | supported |
| Gemini | `gemini deep-research`, `gemini generate video`, `gemini chat ...` | experimental |
| Flow | `flow open`, `flow text-to-video`, `flow image-to-video`, `flow screenshot` | experimental |
| Colab | `targets list/select/current/open --product colab`, `colab notebook list/select/current/open/info/summary`, `colab cell count/run/run-file`, `colab runtime status` | supported |
| Colab | `colab file upload/list/download`, `colab artifact list/latest/get/download`, `colab notebook export` | best-effort |

Stability 语义：

- `supported` 表示 CLI contract 和回归测试覆盖稳定输出结构。
- `experimental` 表示依赖浏览器 UI 或弱选择器，输出会显式带 `stability: "experimental"`。
- `best-effort` 表示能力存在，但依赖 Colab 页面内 API、DOM 链接、浏览器 fetch 或 DOM 重建；输出会显式带 `stability: "best_effort"` 或 `stability: "best-effort"` 等价文案时按 JSON 字段为准。

Colab file / artifact / export 的边界：

- 文件上传是浏览器页内 best-effort 提交；大文件传输不承诺稳定。
- 文件和 artifact 下载只支持可从页面上下文 `fetch` 的 HTTP(S) URL；`blob:`、`data:`、缺失 URL 会返回结构化 unsupported error。
- Notebook export 是 DOM 重建的 best-effort 导出，不承诺与 Colab 原生导出完全一致。
- JSON 输出会区分 CLI `status` 和操作状态，例如 `upload.state`、`download.state`、`export.state`，并提供 `evidence` / `uncertainty`。

### 迁移说明

| 旧入口 | 新入口 |
|---|---|
| 独立 NotebookLM CLI | 保持 `notebooklm notebook/source/chat/research/artifact/generate/download ...` |
| `gemini-web-cli generate text` | `notebooklm gemini generate text` |
| `gemini-web-cli ask` | `notebooklm gemini ask` |
| `gemini-web-cli generate image/vision/video` | `notebooklm gemini generate image/vision/video`，其中 video 为 experimental |
| `gemini-web-cli flow ...` | `notebooklm flow ...`，当前 Flow 命令为 experimental |
| `colab-cdp-cli notebook list/select/current/open` | `notebooklm targets ... --product colab`，也可用 `notebooklm colab notebook ...` alias |
| `colab-cdp-cli cell/runtime/file/artifact/notebook export` | `notebooklm colab cell/runtime/file/artifact/notebook export ...` |

旧仓只作为迁移来源；使用本仓不需要安装旧 Gemini/Colab 仓库。

---

### 发布范围

- **Linux**：supported，当前首发目标
- **Windows**：experimental / deferred，当前不承诺稳定可用

这不是一句模糊的"跨平台支持中"，
而是明确的产品边界：

- Linux 已经足够接近发布形态
- Windows 仍在重构与稳定性治理阶段
- 因此当前不把 Windows 当作首发承诺平台

---

### 安装

```bash
uv sync
uv run notebooklm --help
```

---

### 已验证的 Linux 服务器链路

这条链路已经在全新 Linux VPS 上从 0 验证过一遍：

```text
Xvfb :99
  -> 持久 Chrome profile
  -> CDP on 127.0.0.1:9222
  -> x11vnc + noVNC
  -> notebooklm-cdp-cli --host/--port
```

Chrome 的关键启动方式：

```bash
DISPLAY=:99 google-chrome-stable \
  --remote-debugging-port=9222 \
  --user-data-dir=$HOME/.browser-login/google-chrome-user-data \
  --no-sandbox
```

实测建议：

- Linux 是当前稳定主路径
- 主 attach 路径优先 `--host 127.0.0.1 --port 9222`
- 不要依赖 `DevToolsActivePort` 自动发现
- 登录恢复优先走同 profile 的 `noVNC` 接管

完整 runbook 见 [docs/linux-server-runbook.md](docs/linux-server-runbook.md)。

---

### 仓库现在自带的 Linux helper scripts

这版仓库直接附带了服务器侧脚本：

- `scripts/install-base-linux.sh`
- `scripts/start-chrome-cdp-linux.sh`
- `scripts/start-novnc-linux.sh`
- `scripts/verify-linux-host.sh`
- `scripts/harden-ssh-linux.sh`

这些脚本的目标不是替代 CLI，而是把 Linux 服务器上的浏览器身份底座固定下来。

---

### 快速开始

你需要：

- 一个可复用的 Chrome / Chromium profile
- 对应浏览器实例可通过 CDP 连接

**1）显式指定 Chrome profile 路径**

```bash
uv run notebooklm browser attach \
  --user-data-dir "/path/to/your/chrome-profile"

uv run notebooklm auth check
uv run notebooklm notebook list
```

**2）通过环境变量提供 profile 路径**

```bash
export NOTEBOOKLM_CDP_USER_DATA_DIR="/path/to/your/chrome-profile"

uv run notebooklm browser attach
uv run notebooklm auth check
```

**3）直接连接已知的 CDP host / port**

```bash
uv run notebooklm --host 127.0.0.1 --port 9222 browser status
uv run notebooklm --host 127.0.0.1 --port 9222 auth check
```

---

### 示例流程

```bash
uv run notebooklm browser attach --user-data-dir "/path/to/your/chrome-profile"
uv run notebooklm auth check
uv run notebooklm notebook list
uv run notebooklm source list --notebook <notebook-id>
uv run notebooklm ask "Summarize the main ideas in Chinese." --notebook <notebook-id>
```

---

### 报告与生成

`generate report --format` 当前支持的值：

- `briefing_doc`
- `study_guide`
- `blog_post`
- `custom`

当你使用 `--format custom` 时，需要同时提供 `--prompt`。

`summary` 不是合法的 report format。
如果你要 notebook summary，请使用：

```bash
uv run notebooklm notebook summary --notebook <notebook-id>
```

示例：

```bash
uv run notebooklm generate report \
  --notebook <notebook-id> \
  --format briefing_doc \
  --json
```

---

### Pending 生成任务

当一次生成请求已经被接受、但 artifact 仍处于 pending 时，CLI 会做一次短暂的 best-effort 检查：

- 如果已经能识别到新 artifact，会尽量直接返回 artifact id
- 如果还不能确定，则保持 pending，并给出后续命令提示

本地 ledger 路径：`~/.notebooklm-cdp/pending_submissions.json`

常用命令：

```bash
uv run notebooklm artifact pending --json
uv run notebooklm artifact resolve-pending <submission-id> --json
```

`artifact resolve-pending` 只有在当前 artifact 列表里存在唯一强候选时才会自动解析；
否则会返回候选项，而不是假装确定。

---

### 设计取舍

这个项目不是在重新发明 NotebookLM client。
它做的是一层更贴近真实使用的身份对齐：

- 真实浏览器继续是真实浏览器
- CLI 继续是 CLI
- CDP 把两者接起来

而不是再造一个只属于自动化的平行身份世界。

---

### 与 notebooklm-py 的关系

本项目是一个独立 CLI，
但当前 NotebookLM client / RPC 能力建立在 [notebooklm-py](https://github.com/teng-lin/notebooklm-py) 之上。

大致分工如下：

**本仓库负责：**

- live Chrome identity via CDP
- CLI surface
- 本地状态管理

**notebooklm-py 负责：**

- NotebookLM client
- RPC types
- 后端调用能力

本项目刻意不把 notebooklm-py 的 Playwright / `storage_state.json` 登录流
当作主认证模型。

向上游项目致谢。
第三方组件与补充说明见 THIRD_PARTY.md。

---

### License

MIT. See LICENSE.

---

## English

### What this is

notebooklm-cdp-cli is an unofficial NotebookLM CLI.

It keeps the speed of CLI / RPC workflows,
but moves auth away from Playwright's `storage_state.json`
and toward a live Chrome identity over CDP.

In one line:

> CLI for operations. CDP for attachment. Real Chrome as the auth anchor.

---

### Why this exists

Many automation flows effectively treat Playwright auth state as the source of truth.

That works for scripts.
It breaks down for real daily work.

Once NotebookLM becomes part of an actual workflow, the pain becomes obvious:

- your real browser is one identity
- your automation environment is another
- login state drifts
- your browser is already logged in, yet automation still depends on a separate state file
- NotebookLM ends up trapped in a terminal silo instead of living inside your real browser workflow

This project is not anti-Playwright.

Its objection is narrower:

> an offline state file should not be treated as the long-term identity model.

---

### Who this is for

This project is for you if:

- you already have a long-lived Google / NotebookLM login in Chrome or Chromium
- you want to reuse that real identity instead of maintaining a separate automation-only auth state
- you want NotebookLM operations to stay primarily CLI / RPC-driven
- you want automation to stay close to your real browser workflow rather than depend on heavy DOM flows

It is probably not your primary path if you want:

- a fully isolated automation-only browser world
- DOM automation first
- a Playwright-session-first design

---

### Current scope

The CLI currently covers:

- browser attach / browser status
- auth diagnostics such as auth check
- notebook, source, chat, notes, share, research
- artifact listing and management
- generation / download flows for report, audio, video, slide, and infographic
- browser-backed Gemini, Flow, and Colab command entry points

### Command Matrix And Stability

| Product | Command families | Stability |
|---|---|---|
| NotebookLM | `browser`, `auth`, `doctor`, `notebook`, `source`, `chat` / `ask`, `notes`, `share`, `research`, `artifact`, `generate`, `download`, `language` | supported |
| Gemini | `gemini generate text`, `gemini ask`, `gemini generate image`, `gemini generate vision` | supported |
| Gemini | `gemini deep-research`, `gemini generate video`, `gemini chat ...` | experimental |
| Flow | `flow open`, `flow text-to-video`, `flow image-to-video`, `flow screenshot` | experimental |
| Colab | `targets list/select/current/open --product colab`, `colab notebook list/select/current/open/info/summary`, `colab cell count/run/run-file`, `colab runtime status` | supported |
| Colab | `colab file upload/list/download`, `colab artifact list/latest/get/download`, `colab notebook export` | best-effort |

Stability means:

- `supported` commands have stable CLI contracts and regression coverage for their output shape.
- `experimental` commands depend on browser UI behavior or weak selectors and return `stability: "experimental"` in JSON.
- `best-effort` commands exist, but depend on Colab page APIs, DOM links, browser fetch, or DOM reconstruction and return `stability: "best_effort"` in JSON.

Colab file / artifact / export boundaries:

- File upload is a best-effort browser-page submission. Large file transfer is not guaranteed.
- File and artifact download only support HTTP(S) URLs fetchable from the page context. `blob:`, `data:`, and missing URLs return structured unsupported errors.
- Notebook export is a best-effort DOM reconstruction and is not promised to match Colab's native export exactly.
- JSON output distinguishes CLI `status` from operation state, such as `upload.state`, `download.state`, and `export.state`, and includes `evidence` / `uncertainty`.

### Migration Notes

| Old entry point | New entry point |
|---|---|
| Standalone NotebookLM CLI usage | Keep using `notebooklm notebook/source/chat/research/artifact/generate/download ...` |
| `gemini-web-cli generate text` | `notebooklm gemini generate text` |
| `gemini-web-cli ask` | `notebooklm gemini ask` |
| `gemini-web-cli generate image/vision/video` | `notebooklm gemini generate image/vision/video`; video is experimental |
| `gemini-web-cli flow ...` | `notebooklm flow ...`; current Flow commands are experimental |
| `colab-cdp-cli notebook list/select/current/open` | `notebooklm targets ... --product colab`, or the `notebooklm colab notebook ...` aliases |
| `colab-cdp-cli cell/runtime/file/artifact/notebook export` | `notebooklm colab cell/runtime/file/artifact/notebook export ...` |

The old Gemini and Colab repositories are migration sources only. They are not required dependencies for this package.

---

### Release scope

- **Linux**: supported, intended for release use
- **Windows**: experimental / deferred, not currently promised as stable

This is a deliberate product boundary, not a vague "cross-platform in progress" statement.

---

### Install

```bash
uv sync
uv run notebooklm --help
```

---

### Verified Linux server flow

This repository now includes a validated Linux-first server path:

```text
Xvfb :99
  -> persistent Chrome profile
  -> CDP on 127.0.0.1:9222
  -> x11vnc + noVNC
  -> notebooklm-cdp-cli --host/--port
```

Key Chrome launch pattern:

```bash
DISPLAY=:99 google-chrome-stable \
  --remote-debugging-port=9222 \
  --user-data-dir=$HOME/.browser-login/google-chrome-user-data \
  --no-sandbox
```

Practical recommendations:

- Linux is the current stable path
- prefer explicit `--host 127.0.0.1 --port 9222`
- do not depend on `DevToolsActivePort`
- use same-profile noVNC takeover for login recovery

See [docs/linux-server-runbook.md](docs/linux-server-runbook.md) for the full runbook.

---

### Bundled Linux helper scripts

This release now ships server-side helper scripts:

- `scripts/install-base-linux.sh`
- `scripts/start-chrome-cdp-linux.sh`
- `scripts/start-novnc-linux.sh`
- `scripts/verify-linux-host.sh`
- `scripts/harden-ssh-linux.sh`

These are meant to stabilize the Linux browser identity layer around the CLI, not replace the CLI itself.

---

### Quick start

You need:

- a reusable Chrome / Chromium profile
- a browser instance reachable via CDP

**1) Attach with an explicit profile path**

```bash
uv run notebooklm browser attach \
  --user-data-dir "/path/to/your/chrome-profile"

uv run notebooklm auth check
uv run notebooklm notebook list
```

**2) Provide the profile via environment variable**

```bash
export NOTEBOOKLM_CDP_USER_DATA_DIR="/path/to/your/chrome-profile"

uv run notebooklm browser attach
uv run notebooklm auth check
```

**3) Connect to an existing CDP host / port**

```bash
uv run notebooklm --host 127.0.0.1 --port 9222 browser status
uv run notebooklm --host 127.0.0.1 --port 9222 auth check
```

---

### Example flow

```bash
uv run notebooklm browser attach --user-data-dir "/path/to/your/chrome-profile"
uv run notebooklm auth check
uv run notebooklm notebook list
uv run notebooklm source list --notebook <notebook-id>
uv run notebooklm ask "Summarize the main ideas in Chinese." --notebook <notebook-id>
```

---

### Reports and generation

Valid values for `generate report --format`:

- `briefing_doc`
- `study_guide`
- `blog_post`
- `custom`

When using `--format custom`, you must also provide `--prompt`.

`summary` is not a valid report format.
If you want the notebook summary, use:

```bash
uv run notebooklm notebook summary --notebook <notebook-id>
```

Example:

```bash
uv run notebooklm generate report \
  --notebook <notebook-id> \
  --format briefing_doc \
  --json
```

---

### Pending submissions

When a generation request has been accepted but the artifact is still pending, the CLI performs a short best-effort lookup:

- if a newly created artifact can already be identified, it tries to return the artifact id directly
- otherwise it keeps the result as pending and points you to follow-up commands

Local ledger path: `~/.notebooklm-cdp/pending_submissions.json`

Useful commands:

```bash
uv run notebooklm artifact pending --json
uv run notebooklm artifact resolve-pending <submission-id> --json
```

`artifact resolve-pending` only auto-resolves when there is a single strong candidate.
Otherwise it returns candidates instead of pretending certainty.

---

### Design choice

This project is not trying to reinvent the NotebookLM client.
It focuses on a more realistic identity alignment layer:

- real browser stays real browser
- CLI stays CLI
- CDP connects the two

instead of creating a second automation-only identity world.

---

### Relationship with notebooklm-py

This repository is an independent CLI,
but its current NotebookLM client / RPC capability builds on top of [notebooklm-py](https://github.com/teng-lin/notebooklm-py).

Roughly speaking:

**this repo handles:**

- live Chrome identity via CDP
- CLI surface
- local state management

**notebooklm-py handles:**

- NotebookLM client
- RPC types
- backend capability

This project intentionally does not treat the Playwright / `storage_state.json` login flow in notebooklm-py as its primary auth model.

With thanks to the upstream project.
See THIRD_PARTY.md for third-party notices and additional details.

---

### License

MIT. See LICENSE.
