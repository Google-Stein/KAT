# Architecture

## Boundaries

```mermaid
flowchart LR
  UI[React / TypeScript chat] -->|Tauri invoke: runtime connection| Native[Tauri Rust launcher]
  Native -->|spawn / health / shutdown| Core[FastAPI on 127.0.0.1]
  UI -->|authenticated local HTTP| Core
  Core --> Store[(Local SQLite)]
  Core --> Runtime[Model runtime protocol]
  Runtime --> Providers[Explicit provider registry]
  Providers --> SDK[OpenAI Agents SDK]
  Providers --> Local[Ollama adapter]
  SDK --> OpenAI[OpenAI model]
  Local --> Backend[Loopback Ollama / local weights]
  SDK --> Dispatch[Shared tool dispatcher]
  Local --> Dispatch
  Dispatch --> Registry[Typed tool registry]
  Registry --> Permissions[Risk and approval policy]
  Permissions --> Store
  Permissions -->|approved allowlisted action| OS[Local operating system]
```

The native launcher owns the Core process. It generates an ephemeral bearer token, passes it to the child through its environment, and returns the connection information to the UI through a narrowly scoped native command. The UI holds the token in memory. Core listens only on loopback, on port 42800 by default.

Core is a Python package with separate API, schemas, storage, orchestration, provider runtime, tools, permissions, and configuration responsibilities. The OpenAI Agents SDK is the initial runtime adapter, not a dependency of the desktop or persistence contract. The runtime protocol allows deterministic tests and replaceable providers; the local adapter shares orchestration, permissions and storage with the SDK adapter.

## Data and conversation

SQLite owns sessions, ordered messages, settings, approvals, and audit events. Conversation context is reconstructed from persisted messages for each turn; SDK in-memory state is not the durable source of truth. Timestamps are explicit and machine readable. UI rendering treats transcript text as text, not executable markup.

A turn validates and records the user message, supplies prior context to the model runtime, dispatches requested tools through the registry, and records the assistant response. A per-session concurrency guard prevents overlapping turns from scrambling context. Provider failures are reported explicitly and audited without exposing credentials or raw provider diagnostics.

The registry advertises tool definitions with typed schemas and permission/risk metadata. It rejects unknown tools and malformed arguments before considering execution. Local time is low risk and can execute without approval unless the user enables low-risk approval. Application launch is medium risk and always requires approval.

## Durable approval flow

1. A model tool call passes schema and allowlist validation.
2. Policy either authorizes immediate execution or persists a pending approval.
3. The tool returns a structured approval-required result to the current agent turn. The UI displays pending approvals separately from the model's prose.
4. A user decision calls the approval API. Core atomically claims the persisted request before executing it.
5. The decision, execution outcome, error if any, and a tool message are persisted. The next model turn includes this outcome in context.

An approval does not hold a long-running HTTP/model request open. Pending approvals remain reviewable after restart. Already claimed requests cannot be replayed. A process crash around an external action cannot give an absolute exactly-once guarantee; recovery must avoid automatic retry when the outcome is uncertain.

## Desktop lifecycle and packaging

Development uses the repository's Core virtual environment and Vite. A packaged desktop uses a PyInstaller `--onedir` Core distribution bundled as a Tauri resource at `binaries/kat-core/`. The executable is a fixed resource selected by native code; the webview cannot select programs to run. Core startup is gated on an authenticated health response. A startup failure opens the connection/error screen with an explicit restart control. Closing the desktop shuts down its child. On Windows, a kernel Job Object also terminates Core when the desktop crashes; Core starts suspended and enters the Job Object before its main thread resumes, so Python launcher descendants cannot escape. Only approved user applications explicitly request breakaway and remain open. Linux development uses a parent-death signal with a dedicated creator thread, so a retiring restart worker cannot inadvertently kill Core.

No server process should be assumed to survive a cloud environment snapshot. A standalone Core can be launched for API development using its CLI and a private token file. Browser development supplies that token at runtime through the connection screen; tokens are never compiled into frontend assets.

## API outline

Every endpoint requires `Authorization: Bearer <runtime-token>`, including health.

| Resource | Operations | Responsibility |
| --- | --- | --- |
| `/health` | GET | Service version and provider configuration status |
| `/sessions` | GET, POST | List and create sessions |
| `/sessions/{id}/messages` | GET, POST | Persisted transcript and agent turns |
| `/approvals` | GET | Pending and completed tool requests |
| `/approvals/{id}/decision` | POST | Allow/deny with durable execution claim |
| `/settings` | GET, PUT | Model/provider and low-risk permission preference |
| `/audit` | GET | Bounded tool and application event history |
| `/providers` | GET | Implemented adapter capability descriptors |
| `/providers/probe` | POST | Nonsecret local discovery/status or OpenAI configuration presence |

FastAPI's OpenAPI schema is the authoritative field-level API reference, available with local authentication. React uses typed API models. Version future breaking changes deliberately rather than relying on UI assumptions.

Windows native startup resolves provider credentials before starting the owned
Core. Native Settings commands enter, replace or remove the current user's KAT
vault entry and restart Core; the UI receives status and a fresh Core connection.
The existing suspended-spawn Job Object boundary remains intact. NSIS installs
for the current user and bundles the full PyInstaller Core directory. Uninstall
removes application files and retains `%LOCALAPPDATA%\com.kat.assistant` and the
credential entry, allowing reinstall to recover the workspace. Remove the key
through Settings before uninstall if desired; data deletion is an explicit owner
operation. The installer never installs or downloads model weights.

`VERSION` is the release metadata source. Run `python scripts/version.py` after
changing it; Python/npm/Cargo/Tauri manifests and lockfiles carry generated copies
for their tooling. CI runs `python scripts/version.py --check` to prevent drift.
Only green, validated source commits may receive release tags.

ProviderRegistry resolves an explicit persisted provider to a ModelRuntime.
SelectedRuntime takes a settings snapshot per conversation request; providers
share the same context builder and tool dispatcher. The OpenAI SDK stays inside
its adapter. Ollama uses bounded native `/api/chat` JSON and `/api/show` capability
metadata. Authenticated provider discovery/probe routes expose safe status,
available model names and current tool support, never secret values. A configured
local route can still fail connectivity; Settings probes distinguish a stopped
backend from an uninstalled model. Schema migration 2 adds its nonsecret endpoint
while preserving provider/model/history/permissions and backing up version 1.
