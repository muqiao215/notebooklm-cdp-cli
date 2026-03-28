# notebooklm-cdp-cli

`notebooklm-cdp-cli` is an unofficial NotebookLM CLI focused on one specific
tradeoff: reusing a live Chrome identity through CDP instead of treating
Playwright `storage_state.json` as the source of truth.

The project exposes an independent CLI surface for NotebookLM workflows such as
notebook management, source import, chat, artifact generation, sharing, notes,
and research operations.

## Why This Exists

The main goal is to make NotebookLM automation more usable in environments where
the real Google login state already lives in a persistent local Chrome profile.

Compared with browser-first automation, this project is designed to:

- reuse a live Chrome/CDP session for identity bootstrap
- keep NotebookLM business operations on an RPC/client path
- avoid DOM-driven text input as the primary execution path
- keep a standalone CLI/product surface separate from browser-extension stacks

## Current Status

The CLI currently covers:

- browser attach/status and auth diagnostics
- notebook, source, chat, notes, share, and research commands
- artifact listing/management
- report/audio/video/slide/infographic and related download flows

This repository is still early-stage and should be treated as experimental.

## Relationship to notebooklm-py

This project is an independent CLI, but it currently builds on top of
[`notebooklm-py`](https://github.com/teng-lin/notebooklm-py) for NotebookLM
client/RPC functionality.

In practice, that means:

- this repo owns the CDP/live-Chrome identity layer
- this repo owns the CLI surface and local state behavior
- `notebooklm-py` currently provides the NotebookLM client and RPC types/backend

This project deliberately does **not** use `notebooklm-py`'s
Playwright/`storage_state.json` flow as its primary auth/session model.

See [THIRD_PARTY.md](THIRD_PARTY.md) for the third-party component note.

## Installation

```bash
uv sync
uv run notebooklm-cdp --help
```

## Configuration

There is no single built-in profile path that works across machines.

Use one of these patterns instead:

### 1. Attach with an explicit Chrome profile path

```bash
uv run notebooklm-cdp browser attach \
  --user-data-dir "/path/to/your/chrome-profile"

uv run notebooklm-cdp auth check
uv run notebooklm-cdp notebook list
```

### 2. Configure the profile path through an environment variable

```bash
export NOTEBOOKLM_CDP_USER_DATA_DIR="/path/to/your/chrome-profile"

uv run notebooklm-cdp browser attach
uv run notebooklm-cdp auth check
```

### 3. Connect to an already-known CDP host/port directly

```bash
uv run notebooklm-cdp --host 127.0.0.1 --port 9222 browser status
uv run notebooklm-cdp --host 127.0.0.1 --port 9222 auth check
```

## Example Workflow

```bash
uv run notebooklm-cdp browser attach --user-data-dir "/path/to/your/chrome-profile"
uv run notebooklm-cdp auth check
uv run notebooklm-cdp notebook list
uv run notebooklm-cdp source list --notebook <notebook-id>
uv run notebooklm-cdp ask "Summarize the main ideas in Chinese." --notebook <notebook-id>
```

## Report Generation

Valid `generate report --format` values are:

- `briefing_doc`
- `study_guide`
- `blog_post`
- `custom`

Use `--prompt` together with `--format custom`.

`summary` is not a valid report format. If you want the notebook summary, use:

```bash
uv run notebooklm-cdp notebook summary --notebook <notebook-id>
```

Example:

```bash
uv run notebooklm-cdp generate report \
  --notebook <notebook-id> \
  --format briefing_doc \
  --json
```

When a generation submit is accepted but still returns `pending`, the CLI now does
a short best-effort artifact check and may surface a newly visible artifact ID
immediately. If no artifact is visible yet, the response stays normalized as
`pending` and includes concrete follow-up commands.

The CLI also records pending generation submissions locally in
`~/.notebooklm-cdp/pending_submissions.json` so they can be re-resolved later.
This ledger captures the notebook, artifact kind, submit time, task ID state,
source/language/options, baseline artifact IDs, and a stable prompt fingerprint.

Useful follow-up commands:

```bash
uv run notebooklm-cdp artifact pending --json
uv run notebooklm-cdp artifact resolve-pending <submission-id> --json
```

`artifact resolve-pending` only auto-resolves when there is exactly one strong
candidate in the current artifact list for the same notebook and kind, newer
than the submission, and not present in the recorded baseline. Otherwise it
returns ranked candidates without claiming certainty.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This is an unofficial project. It is not affiliated with or endorsed by Google,
NotebookLM, OpenAI, OpenCLI, or the `notebooklm-py` project.
