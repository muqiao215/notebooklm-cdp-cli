# notebooklm-cdp-cli

Language: [中文](#中文说明) | [English](#english)

## 中文说明

`notebooklm-cdp-cli` 是一个非官方的 NotebookLM 命令行工具。

它的核心取舍很明确：**复用真实 Chrome 的登录态与 CDP 会话**，而不是把 Playwright 的 `storage_state.json` 当作唯一真源。

## 当前发布口径

**首发仅支持 Linux。**

当前平台状态：

- `Linux`: supported，作为当前发布目标
- `Windows`: experimental / deferred，不承诺当前可用性与稳定性

这不是泛泛而谈的“跨平台支持中”，而是明确的产品边界：

- Linux 已经足够接近产品形态，可以先发布使用
- Windows 仍在重构与稳定性治理阶段，不应被当作首发支持平台

## 这个项目解决什么问题

这个项目主要面向这样一种场景：

- 真实 Google / NotebookLM 登录态已经存在于本地长期使用的 Chrome profile 中
- 你希望直接复用这套真实身份
- 你希望 NotebookLM 的主要操作仍然走 RPC / CLI，而不是以 DOM 自动化为主

项目目前提供的 CLI 范围包括：

- browser attach/status 和 auth diagnostics
- notebook、source、chat、notes、share、research 命令
- artifact 管理
- report / audio / video / slide / infographic 等生成与下载流程

## 与 notebooklm-py 的关系

这个仓库是一个独立 CLI，但当前 NotebookLM 客户端 / RPC 能力仍然建立在
[`notebooklm-py`](https://github.com/teng-lin/notebooklm-py) 之上。

分工大致是：

- 本仓库负责：CDP / live Chrome identity layer
- 本仓库负责：CLI surface 和本地状态管理
- `notebooklm-py` 负责：NotebookLM client、RPC types、后端调用能力

这个项目**刻意不把** `notebooklm-py` 的 Playwright / `storage_state.json`
登录流当成主认证模型。

第三方组件说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 安装

```bash
uv sync
uv run notebooklm-cdp --help
```

## Linux 使用方式

当前推荐的使用前提是：

- 你已经在 Linux 上准备好了可复用的 Chrome / Chromium profile
- 该浏览器实例对 CDP 可见

### 1. 显式指定 Chrome profile 路径

```bash
uv run notebooklm-cdp browser attach \
  --user-data-dir "/path/to/your/chrome-profile"

uv run notebooklm-cdp auth check
uv run notebooklm-cdp notebook list
```

### 2. 通过环境变量提供 profile 路径

```bash
export NOTEBOOKLM_CDP_USER_DATA_DIR="/path/to/your/chrome-profile"

uv run notebooklm-cdp browser attach
uv run notebooklm-cdp auth check
```

### 3. 直接连接已知的 CDP host / port

```bash
uv run notebooklm-cdp --host 127.0.0.1 --port 9222 browser status
uv run notebooklm-cdp --host 127.0.0.1 --port 9222 auth check
```

## 示例流程

```bash
uv run notebooklm-cdp browser attach --user-data-dir "/path/to/your/chrome-profile"
uv run notebooklm-cdp auth check
uv run notebooklm-cdp notebook list
uv run notebooklm-cdp source list --notebook <notebook-id>
uv run notebooklm-cdp ask "Summarize the main ideas in Chinese." --notebook <notebook-id>
```

## 报告生成

`generate report --format` 当前支持的值：

- `briefing_doc`
- `study_guide`
- `blog_post`
- `custom`

当你使用 `--format custom` 时，需要同时提供 `--prompt`。

`summary` 不是合法的 report format。如果你想拿 notebook summary，请用：

English note: `summary` is not a valid report format.

```bash
uv run notebooklm-cdp notebook summary --notebook <notebook-id>
```

示例：

```bash
uv run notebooklm-cdp generate report \
  --notebook <notebook-id> \
  --format briefing_doc \
  --json
```

当生成提交已被接受但仍处于 `pending` 时，CLI 会做一次短暂的 best-effort artifact 检查；
如果已经能看到新 artifact，就会尽量直接返回 artifact id。否则仍保持 `pending`，
并给出后续命令提示。

CLI 还会把 pending 生成提交记录到本地：

`~/.notebooklm-cdp/pending_submissions.json`

这个 ledger 会记录：

- notebook
- artifact kind
- submit time
- task ID 状态
- source / language / options
- baseline artifact IDs
- prompt fingerprint

常用后续命令：

```bash
uv run notebooklm-cdp artifact pending --json
uv run notebooklm-cdp artifact resolve-pending <submission-id> --json
```

`artifact resolve-pending` 只有在当前 artifact 列表里存在**唯一强候选**时才会自动解析；
否则会返回候选项而不假装确定。

## Windows 说明

Windows 目前**不属于首发支持范围**。

当前结论是：

- 可以继续研究和重构
- 可以保留实验性分支与本地方案
- 但当前不应对外承诺“Windows 现在可稳定使用”

如果后续要支持 Windows，方向会是：

- 长驻 daemon
- 稳定 browser pairing
- direct CDP page execution 为主数据面
- extension 降级为配对 / 发现层，而不是主执行层

## License

MIT。见 [LICENSE](LICENSE)。

## Disclaimer

这是一个非官方项目，与 Google、NotebookLM、OpenAI、OpenCLI 或
`notebooklm-py` 项目无官方关联，也未获得其背书。

## English

`notebooklm-cdp-cli` is an unofficial NotebookLM CLI that reuses a live Chrome
identity through CDP instead of treating Playwright `storage_state.json` as the
source of truth.

Current release scope:

- `Linux`: supported and intended for release use
- `Windows`: experimental / deferred, not currently promised as stable

The project currently covers:

- browser attach/status and auth diagnostics
- notebook, source, chat, notes, sharing, and research commands
- artifact listing/management
- report/audio/video/slide/infographic generation and downloads

Recommended Linux usage:

```bash
uv sync
uv run notebooklm-cdp browser attach --user-data-dir "/path/to/your/chrome-profile"
uv run notebooklm-cdp auth check
uv run notebooklm-cdp notebook list
```

Valid `generate report --format` values are:

- `briefing_doc`
- `study_guide`
- `blog_post`
- `custom`

Use `--prompt` with `--format custom`.

`summary` is not a valid report format.
