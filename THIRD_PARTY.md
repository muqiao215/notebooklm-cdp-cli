# Third-Party Components

## notebooklm-py

- Project: `teng-lin/notebooklm-py`
- Repository: <https://github.com/teng-lin/notebooklm-py>
- License: MIT

This project depends on `notebooklm-py` for NotebookLM client access,
RPC types and enums, and backend API call implementation.

This project does not use `notebooklm-py`'s Playwright `storage_state.json`
login flow as its primary auth model. Instead, it uses a live Chrome/CDP-based
identity layer and exposes a separate CLI and product surface on top.

If future revisions vendor or copy upstream source code directly, the copied
files should retain the original copyright and license notices.
