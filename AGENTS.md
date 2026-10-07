# Working on KAT

Read `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, and `docs/DECISIONS.md` before significant changes. The owner directs the product; agents implement and validate it.

Use the existing checkout: cloud tasks are already isolated. Do not create Git worktrees unless the owner requests one. Preserve user changes. Never commit secrets, local databases, virtual environments, build outputs, or API tokens.

Keep Python Core (`core/`), React (`desktop/src/`), and native lifecycle (`desktop/src-tauri/`) modular. Model access belongs behind the runtime protocol; tool capabilities belong in the registry with typed argument schemas and explicit risk metadata. Every API operation requires local authentication. Models never choose executable paths or shell commands.

Run the relevant checks from README.md for changes. Use test fakes for deterministic provider tests; do not present fake-model results as live OpenAI validation. Windows binaries must be built and exercised on Windows. Keep docs and API contracts consistent with changes.

Do not expand this slice into autonomous scheduling, voice, browser automation, arbitrary shell execution, email/calendar access, or long-term semantic memory without a new product decision.
