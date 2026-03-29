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
