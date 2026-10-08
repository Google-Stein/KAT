# Decisions

## ADR 001: Small modular vertical slice

**Accepted.** Python 3.12+ Core, FastAPI local API, Tauri 2 + React + TypeScript desktop, and SQLite persistence. Implement text chat and two bounded tools before adding voice or autonomy. These choices separate UI, runtime, storage, and permissions while keeping installation manageable.

## ADR 002: Replaceable model runtime

**Accepted.** Use OpenAI Agents SDK behind an injected runtime protocol. SQLite owns conversation history rather than provider-managed sessions. The first supported provider is OpenAI; the abstraction is an extension point, not a claim that additional providers already work.

## ADR 003: Explicit allowlist and risk policy

**Accepted.** Models request typed tool calls; Core validates and governs them. Local time defaults to auto-allow, while application launch always requires approval. Executables and arguments come from trusted registrations, never model-supplied paths or command strings. Arbitrary shell execution is excluded.

## ADR 004: Durable approval instead of blocked runs

**Accepted.** Persist approval requests and return their status as a tool result. The UI decides through a separate endpoint; outcomes enter the transcript and audit log. This avoids keeping model runs suspended in volatile memory and supports restart recovery. The model continues on the next turn, rather than automatically generating another reply when the user clicks Allow.

## ADR 005: Local authenticated process lifecycle

**Accepted.** Tauri owns a fixed Core child process, issues an ephemeral bearer token, waits for authenticated health, and cleans up on exit. Core binds only to loopback. The UI cannot choose a native executable or invoke a shell. Standalone API development uses an explicitly protected token file.

## ADR 006: Secrets outside persistence

**Accepted.** Load the initial provider key from environment or an ignored `.env` through an explicit CLI option. Settings store provider/model and permission preferences, never API keys. Windows Credential Manager integration is a follow-up milestone. SDK trace export is disabled.

## ADR 007: Native packaging per target

**Accepted.** Package Python Core with PyInstaller and bundle it as a Tauri resource. Build Windows release artifacts on Windows with Microsoft build tools and WebView2 prerequisites. Linux checks can validate Rust compilation and Linux runtime, but do not establish Windows runtime success.

## ADR 008: Test without pretending external access

**Accepted.** Automated provider tests use injected fakes and mocked SDK transport, with real argument validation, persistence, approval, and API logic. Live OpenAI verification requires a valid key and network access; its absence must be reported. Windows startup requires a Windows runner. All verification claims must identify which environment and integration were actually exercised.

## ADR 009: Certified Python runtime and Windows release gate

**Accepted.** KAT 0.1 uses CPython 3.12.x for local setup, dependency installation, tests and PyInstaller packaging. Core retains a 3.12 language minimum, but newer minor interpreters are not certified until an explicit compatibility decision and Windows validation. CI supplies its selected executable; setup rejects incompatible existing environments. Windows launch, authentication, process ownership and both shutdown paths must pass on the packaged executable before the foundation is called Windows validated. Persistent startup logs expose phases and PIDs without bearer credentials.

## ADR 010: Framework build mode and complete Windows process ownership

**Accepted.** Use `tauri::is_dev()` to select development versus packaged resources and navigation policy. Tauri CLI enables `tauri/custom-protocol` directly; checking KAT's similarly named forwarding feature incorrectly selects development Python in a built release. On Windows, start Core suspended, assign it to the lifetime Job Object and then resume it. Ordinary descendants, including the venv redirector's Python process, inherit ownership. Only approved application launches request explicit breakaway. This closes both the spawn/assignment race and unintentional silent breakaway without broadening tool permissions.
