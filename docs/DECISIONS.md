# Decisions

## ADR 001: Small modular vertical slice

**Accepted.** Python 3.12+ Core, FastAPI local API, Tauri 2 + React + TypeScript desktop, and SQLite persistence. Implement text chat and two bounded tools before adding voice or autonomy. These choices separate UI, runtime, storage, and permissions while keeping installation manageable.

## ADR 002: Replaceable model runtime

**Accepted.** Use OpenAI Agents SDK behind an injected runtime protocol. SQLite owns conversation history rather than provider-managed sessions. The first supported provider was OpenAI; ADR 013 adds the independently replaceable Ollama adapter behind the same protocol.

## ADR 003: Explicit allowlist and risk policy

**Accepted.** Models request typed tool calls; Core validates and governs them. Local time defaults to auto-allow, while application launch always requires approval. Executables and arguments come from trusted registrations, never model-supplied paths or command strings. Arbitrary shell execution is excluded.

## ADR 004: Durable approval instead of blocked runs

**Accepted.** Persist approval requests and return their status as a tool result. The UI decides through a separate endpoint; outcomes enter the transcript and audit log. This avoids keeping model runs suspended in volatile memory and supports restart recovery. The model continues on the next turn, rather than automatically generating another reply when the user clicks Allow.

## ADR 005: Local authenticated process lifecycle

**Accepted.** Tauri owns a fixed Core child process, issues an ephemeral bearer token, waits for authenticated health, and cleans up on exit. Core binds only to loopback. The UI cannot choose a native executable or invoke a shell. Standalone API development uses an explicitly protected token file.

## ADR 006: Secrets outside persistence

**Accepted.** Load the initial provider key from environment or an ignored `.env` through an explicit CLI option. Settings store provider/model and permission preferences, never API keys. ADR 012 supersedes the initial environment-only credential boundary with Windows-native vault handling. SDK trace export is disabled.

## ADR 007: Native packaging per target

**Accepted.** Package Python Core with PyInstaller and bundle it as a Tauri resource. Build Windows release artifacts on Windows with Microsoft build tools and WebView2 prerequisites. Linux checks can validate Rust compilation and Linux runtime, but do not establish Windows runtime success.

## ADR 008: Test without pretending external access

**Accepted.** Automated provider tests use injected fakes and mocked SDK transport, with real argument validation, persistence, approval, and API logic. Live OpenAI verification requires a valid key and network access; its absence must be reported. Windows startup requires a Windows runner. All verification claims must identify which environment and integration were actually exercised.

## ADR 009: Certified Python runtime and Windows release gate

**Accepted.** KAT 0.1.x/0.2 use CPython 3.12.x for local setup, dependency installation, tests and PyInstaller packaging. Core retains a 3.12 language minimum, but newer minor interpreters are not certified until an explicit compatibility decision and Windows validation. CI supplies its selected executable; setup rejects incompatible existing environments. Windows launch, authentication, process ownership and both shutdown paths must pass on the packaged executable before the foundation is called Windows validated. Persistent startup logs expose phases and PIDs without bearer credentials.

## ADR 010: Framework build mode and complete Windows process ownership

**Accepted.** Use `tauri::is_dev()` to select development versus packaged resources and navigation policy. Tauri CLI enables `tauri/custom-protocol` directly; checking KAT's similarly named forwarding feature incorrectly selects development Python in a built release. On Windows, start Core suspended, assign it to the lifetime Job Object and then resume it. Ordinary descendants, including the venv redirector's Python process, inherit ownership. Only approved application launches request explicit breakaway. This closes both the spawn/assignment race and unintentional silent breakaway without broadening tool permissions.

## ADR 011: Installed application, local inference, then memory review

**Accepted product direction.** Preserve the validated 0.1 foundation. Prioritize 0.1.1 installation, Windows Credential Manager storage and actionable provider errors; then 0.2 local inference behind the existing runtime abstraction, with OpenAI optional and no silent cloud fallback. After 0.2, stop and present a memory architecture proposal for explicit owner review before implementing 0.3+ personal intelligence. Saved transcripts do not satisfy or bypass that review. ADR 013 records the implemented runtime choice; the memory proposal now awaits owner review. Unrelated major capabilities remain outside this sequence. Scope and acceptance criteria are recorded in [ROADMAP.md](ROADMAP.md).

## ADR 012: Native Windows provider key entry

Use a current-user generic Windows Credential Manager entry and a Windows-native
masked credential dialog. React sees presence/status, never an API key. Existing
environment overrides remain useful for CI/development and are clearly disclosed.
Credential changes restart Core through the stabilized ownership/lifecycle path.
Cancel and vault-write failure preserve the existing process. Windows tests use
unique synthetic entries and never mutate an owner's production credential.

## ADR 013: Explicit local inference through Ollama

Ollama is the first local adapter because it supports Windows/NVIDIA deployment,
model discovery and native function calls. The backend remains independently
installed and owned; KAT neither downloads weights nor terminates its server.
Use loopback-only HTTP origins, literal normalization, no environment proxies,
no redirects, bounded payloads and fixed routes. Models and capabilities are
queried locally. Unsupported tool capabilities are disclosed; text never becomes
a tool call. Native structured requests go through the existing validated,
audited permission dispatcher. OpenAI remains a separate SDK adapter.

Select one provider explicitly in Settings. No retry changes providers and no
local failure sends context to OpenAI. Preserve existing users' OpenAI selection
on upgrade rather than silently changing behavior. Local conversation requires no
provider credential. Runtime capability metadata reports implemented chat/tools;
streaming and structured-answer UI are not implemented. Ollama context is bounded
to 8192 configured tokens with conservative character-bounded history; this is a
transport budget, not a claim about every model's full context capacity.


## ADR 014: Transactional ordered local-data migrations

Use explicit sequential SQLite schema versions, a pre-upgrade backup through the
SQLite backup API (including committed WAL), and one transaction for DDL/data/version
updates. A failed step rolls back; an unknown newer schema fails closed. Preserve
existing OpenAI selection and transcripts during the local-provider upgrade.
Backups and live data remain under the same private account boundary and never
enter source control. Search/semantic-memory schema changes remain unimplemented.

## ADR 015: Production accessibility for installed-app acceptance

Use Windows accessibility and real keyboard/mouse input to exercise installed UI,
including the native masked credential dialog. Read-only database inspection
verifies durable outcomes; it does not replace UI mutations or tool approval.
CDP attachment failed on released builds, so no debugging ports, relaxed navigation
or production test IPC were introduced. Disposable CI uses synthetic keys, an
explicitly downloaded checksum-verified backend and a small actual local model.
GPU performance and live OpenAI accounts remain separately identified validation.

## ADR 016: Memory proposal requires product review

The current release contains transcripts and ordered migrations, not personal
semantic memory. Stop after the validated local-model milestone and bounded UI
polish. [MEMORY_DESIGN_PROPOSAL.md](MEMORY_DESIGN_PROPOSAL.md) recommends explicit
owner confirmation, scoped provenance, inspect/edit/forget, lexical retrieval
before vectors, local processing and no cloud memory context in the first slice.
These are proposals requiring owner decisions, not implementation authorization.
