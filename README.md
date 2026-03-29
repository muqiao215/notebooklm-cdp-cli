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

### Disclaimer

这是一个非官方项目。
与 Google、NotebookLM 及其关联方没有官方关系，也未获得其背书。

---

## English

### What this is

notebooklm-cdp-cli is an unofficial NotebookLM CLI.

It keeps the efficiency of CLI / RPC,
but replaces **Playwright's storage_state.json** with
**CDP direct access to your real Chrome login session**.

In one sentence: the CLI handles operations, CDP handles identity,
and the real browser is the authentication anchor.

---

### Why this exists

Most automation solutions treat Playwright's login state file as the "source of truth."

Fine for a quick script.
Not enough for long-term workflows.

Because once you actually start using NotebookLM as an office assistant, the problems become obvious:

- Your real browser has one identity, your automation environment has another
- Login state drifts, maintenance cost rises
- Your real browser is already logged in, but your automation is still holding onto a state file
- NotebookLM ends up locked in the terminal instead of fitting into your real workflow

This project isn't against Playwright.
It's against something else: treating an offline state file as a long-term authentication model.

---

### Who this is for

This project is mainly for users who:

- Already have a long-running Chrome / Chromium profile with Google / NotebookLM logged in
- Want to reuse that real identity instead of maintaining a separate automation login
- Still want NotebookLM operations to go through CLI / RPC
- Want automation that stays close to a real browser instead of relying on heavy DOM automation

If what you want is:

- A fully isolated automation-only browser
- DOM automation first
- Playwright session as the core design

Then this may not be your main path.

---

### Current capabilities

The CLI currently covers:

- browser attach / browser status
- auth check and authentication diagnostics
- notebook, source, chat, notes, share, research commands
- artifact listing and management
- report / audio / video / slide / infographic generation and download flows

---

### Release scope

- **Linux**: supported, current release target
- **Windows**: experimental / deferred, stability not currently promised

This is not a vague "cross-platform support in progress."
It's a clear product boundary:

- Linux is close enough to release shape
- Windows is still under refactoring and stability governance
- Therefore Windows is not currently promised as a launch-supported platform

---

### Installation

```bash
uv sync
uv run notebooklm --help
```

---

### Quick start

Prerequisites:

- A reusable Chrome / Chromium profile
- The browser instance reachable via CDP

**1) Explicit Chrome profile path**

```bash
uv run notebooklm browser attach \
  --user-data-dir "/path/to/your/chrome-profile"

uv run notebooklm auth check
uv run notebooklm notebook list
```

**2) Profile path via environment variable**

```bash
export NOTEBOOKLM_CDP_USER_DATA_DIR="/path/to/your/chrome-profile"

uv run notebooklm browser attach
uv run notebooklm auth check
```

**3) Connect to a known CDP host / port directly**

```bash
uv run notebooklm --host 127.0.0.1 --port 9222 browser status
uv run notebooklm --host 127.0.0.1 --port 9222 auth check
```

---

### Example workflow

```bash
uv run notebooklm browser attach --user-data-dir "/path/to/your/chrome-profile"
uv run notebooklm auth check
uv run notebooklm notebook list
uv run notebooklm source list --notebook <notebook-id>
uv run notebooklm ask "Summarize the main ideas in Chinese." --notebook <notebook-id>
```

---

### Reports and generation

Valid `generate report --format` values:

- `briefing_doc`
- `study_guide`
- `blog_post`
- `custom`

Use `--prompt` with `--format custom`.

`summary` is not a valid report format.
For notebook summary, use:

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

### Pending generation tasks

When a generation request has been accepted but the artifact is still pending, the CLI performs a brief best-effort check:

- If the new artifact is already identifiable, it returns the artifact id directly
- If it can't be determined yet, it stays pending and provides follow-up command hints

Local ledger path: `~/.notebooklm-cdp/pending_submissions.json`

Common follow-up commands:

```bash
uv run notebooklm artifact pending --json
uv run notebooklm artifact resolve-pending <submission-id> --json
```

`artifact resolve-pending` only auto-resolves when there is a unique strong candidate in the current artifact list;
otherwise it returns the candidates without pretending certainty.

---

### Design tradeoffs

This project is not reinventing the NotebookLM client.
It's adding a layer of identity alignment that stays closer to real usage:

- The real browser stays the real browser
- The CLI stays the CLI
- CDP connects the two

Instead of building a parallel identity world that only belongs to automation.

---

### Relationship with notebooklm-py

This project is a standalone CLI,
but the NotebookLM client / RPC capability is built on top of [notebooklm-py](https://github.com/teng-lin/notebooklm-py).

Rough division of responsibility:

**This repository handles:**

- live Chrome identity via CDP
- CLI surface
- local state management

**notebooklm-py handles:**

- NotebookLM client
- RPC types
- backend call capability

This project intentionally does not treat notebooklm-py's Playwright / `storage_state.json` login flow
as its primary authentication model.

Credit to the upstream project.
Third-party components and supplementary notes are in THIRD_PARTY.md.

---

### License

MIT. See LICENSE.

---

### Disclaimer

This is an unofficial project.
It is not affiliated with, endorsed by, or connected to Google or NotebookLM.
