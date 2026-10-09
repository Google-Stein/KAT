# Decisions

## ADR 001: Small modular vertical slice

**Accepted.** Python 3.12+ Core, FastAPI local API, Tauri 2 + React + TypeScript desktop, and SQLite persistence. Implement text chat and two bounded tools before adding voice or autonomy. These choices separate UI, runtime, storage, and permissions while keeping installation manageable.

## ADR 002: Replaceable model runtime

**Accepted.** Use OpenAI Agents SDK behind an injected runtime protocol. SQLite owns conversation history rather than provider-managed sessions. The first supported provider was OpenAI; ADR 013 adds the independently replaceable Ollama adapter behind the same protocol.

## ADR 003: Explicit allowlist and risk policy

**Accepted.** Models request typed tool calls; Core validates and governs them. Local time defaults to auto-allow, while application launch always requires approval. Executables and arguments come from trusted registrations, never model-supplied paths or command strings. Arbitrary shell execution is excluded.

## ADR 004: Durable approval instead of blocked runs

**Accepted.** Persist approval requests and return their status as a tool result. The UI decides through a separate endpoint; outcomes enter the transcript and audit log. This avoids keeping model runs suspended in volatile memory and supports restart recovery. Approval updates its card without automatically generating another model reply. ADR 017 excludes historical tool outcomes from later inference.

## ADR 005: Local authenticated process lifecycle

**Accepted.** Tauri owns a fixed Core child process, issues an ephemeral bearer token, waits for authenticated health, and cleans up on exit. Core binds only to loopback. The UI cannot choose a native executable or invoke a shell. Standalone API development uses an explicitly protected token file.

## ADR 006: Secrets outside persistence

**Accepted.** Load the initial provider key from environment or an ignored `.env` through an explicit CLI option. Settings store provider/model and permission preferences, never API keys. ADR 012 supersedes the initial environment-only credential boundary with Windows-native vault handling. SDK trace export is disabled.

## ADR 007: Native packaging per target

**Accepted.** Package Python Core with PyInstaller and bundle it as a Tauri resource. Build Windows release artifacts on Windows with Microsoft build tools and WebView2 prerequisites. Linux checks can validate Rust compilation and Linux runtime, but do not establish Windows runtime success.

## ADR 008: Test without pretending external access

**Accepted.** Automated provider tests use injected fakes and mocked SDK transport, with real argument validation, persistence, approval, and API logic. Live OpenAI verification requires a valid key and network access; its absence must be reported. Windows startup requires a Windows runner. All verification claims must identify which environment and integration were actually exercised.

## ADR 009: Certified Python runtime and Windows release gate

**Accepted.** KAT 0.1.x/0.2/0.3 use CPython 3.12.x for local setup, dependency installation, tests and PyInstaller packaging. Core retains a 3.12 language minimum, but newer minor interpreters are not certified until an explicit compatibility decision and Windows validation. CI supplies its selected executable; setup rejects incompatible existing environments. Windows launch, authentication, process ownership and both shutdown paths must pass on the packaged executable before the foundation is called Windows validated. Persistent startup logs expose phases and PIDs without bearer credentials.

## ADR 010: Framework build mode and complete Windows process ownership

**Accepted.** Use `tauri::is_dev()` to select development versus packaged resources and navigation policy. Tauri CLI enables `tauri/custom-protocol` directly; checking KAT's similarly named forwarding feature incorrectly selects development Python in a built release. On Windows, start Core suspended, assign it to the lifetime Job Object and then resume it. Ordinary descendants, including the venv redirector's Python process, inherit ownership. Only approved application launches request explicit breakaway. This closes both the spawn/assignment race and unintentional silent breakaway without broadening tool permissions.

## ADR 011: Installed application, local inference, then memory review

**Accepted product direction.** Preserve the validated 0.1 foundation. Prioritize 0.1.1 installation, Windows Credential Manager storage and actionable provider errors; then 0.2 local inference behind the existing runtime abstraction, with OpenAI optional and no silent cloud fallback. After 0.2, stop and present a memory architecture proposal for explicit owner review before implementing 0.3+ personal intelligence. Saved transcripts do not satisfy or bypass that review. ADR 013 records the implemented runtime choice; the owner has now approved the bounded 0.3 scope in ADRs 018–022. Unrelated major capabilities remain outside this sequence. Scope and acceptance criteria are recorded in [ROADMAP.md](ROADMAP.md).

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
enter source control. Migration 3 implements the explicitly approved memory schema in ADR 018.

## ADR 015: Production accessibility for installed-app acceptance

Use Windows accessibility and real keyboard/mouse input to exercise installed UI,
including the native masked credential dialog. Read-only database inspection
verifies durable outcomes; it does not replace UI mutations or tool approval.
CDP attachment failed on released builds, so no debugging ports, relaxed navigation
or production test IPC were introduced. Disposable CI uses synthetic keys, an
explicitly downloaded checksum-verified backend and a small actual local model.
GPU performance and live OpenAI accounts remain separately identified validation.

## ADR 016: Memory proposal requires product review

**Historical gate, satisfied by the owner’s explicit 0.3 directive.** At 0.2 the
release contained transcripts and ordered migrations, not personal memory. Stop after the validated local-model milestone and bounded UI
polish. [MEMORY_DESIGN_PROPOSAL.md](MEMORY_DESIGN_PROPOSAL.md) recommends explicit
owner confirmation, scoped provenance, inspect/edit/forget, lexical retrieval
before vectors, local processing and no cloud memory context in the first slice.
These are proposals requiring owner decisions, not implementation authorization.

## ADR 017: Historical tool outcomes are transcript data, not inference evidence

**Accepted for 0.2.1.** The shared history builder omits persisted `role="tool"`
messages instead of disguising them as user assertions. These records have no
matching assistant tool-call event; transient timestamps and completed side effects
must not be reused to satisfy a new request. Keep the full SQLite transcript,
approval state, audit and UI unchanged. Real Ollama regression showed that keeping
the old assistant's timestamp also permits stale reuse. Replace assistant content
from historical user turns containing a tool record with a fixed, result-free
historical marker, including pending-approval replies before execution. This keeps
turn structure so old requests do not appear to be unanswered work. Keep user
messages and replies from ordinary conversation
turns. Shared instructions require a fresh time/action call for each new request
and treat older user requests as history rather than queued work.

OpenAI SDK and Ollama continue receiving real tool results inside the active loop
with their corresponding calls. Approval still runs outside that loop, updates
the UI, and requires a new approval for a later action. No result cache, intent
heuristic, provider-specific workaround or database migration is introduced.
Regression tests reproduce the old stale-time answer on both wire protocols and
cover fresh time results and repeated Notepad/Calculator approvals. Actual installed
Ollama validation separately tests model selection, execution and window creation.

## ADR 018: Explicit structured memory and immutable revisions

**Accepted for 0.3.** Owner entry or reviewed conversation selection only. Store
kind/scope/status/origin/normal sensitivity, dates, importance/pin, provenance
references and revision in authoritative items. Keep immutable revision snapshots
for inspection and exact usage evidence. Require expected revision on edits/status
changes to prevent silent lost updates. Supersession is explicit, same-scope and
never inferred from repetition. Schema 3 uses the existing backed-up migration.

## ADR 019: Bounded FTS5 retrieval with abstention

**Accepted.** Structured eligibility plus safely quoted literal FTS terms; no
embeddings/services. Maximum 12 query terms, 50 candidates, four whole records and
4,000 serialized characters. Require meaningful overlap and 25% query coverage;
pins only rank relevant records. Zero is valid. FTS is rebuildable from items.

## ADR 020: Local-only, untrusted memory context

**Accepted.** Retrieval off by default; manage while off. Shared conversation
policy retrieves once per local turn and supplies data outside privileged system
instructions. Transport adapters retain current live tool results. OpenAI performs
no retrieval, receives no memory payload and records no usage. Normal chat history
is still sent when explicitly selected; this supersedes the proposal to block a
cloud switch merely because transcript wording overlaps a memory source. No fallback.

## ADR 021: Forget wording, keep safe references

**Accepted.** Delete item, all revision content and derived FTS artifacts; rebuild
the index and enable SQLite secure deletion. Never copy memory wording into audit
or usage. Keep identifier-only historical usage, with a forgotten marker. Original
transcripts and old backups are separate; physical erasure and encrypted sensitive
storage are not claimed. No provenance evidence text is duplicated.

## ADR 022: Minimal stable project scopes

**Accepted.** A project is ID/name/created/updated only; a session optionally selects
one project. Relevant personal plus that project are eligible. Wrong-project
records are excluded. Scope is immutable on an item; changing it means a new
explicit entry, preventing an ordinary edit from broadening project privacy.
No tasks, planner or project management engine is introduced.

## ADR 023: Identical SQLite stemming for search and relevance

**Accepted for 0.3.1.** Owner testing reproduced a stored “named” record failing
the new-conversation “name” query. The unicode61 index and raw overlap gate both
lacked morphological normalization; changing the index alone would leave a
second rejection path. Use SQLite's actual `porter unicode61` for both. A bounded
RAM-only FTS5/fts5vocab probe scores distinct stems without a duplicate Python
stemmer, persistent normalized copies, raw operator interpolation or private caches.

Measured SQLite behavior covers name/named/naming, prefer/preference, remembered,
working and plurals, accented Latin and literal Unicode. It does not equate every
form (focus/focused), synonyms (car/automobile) or Straße/STRASSE, and can collide
(universe/university). Keep multiword overlap/coverage and generic-only abstention;
pins cannot override them. Sparse collision ambiguity remains a documented limit.
No identity-intent or owner-name branches exist in production. Existing indexed
12-term/50-candidate/4-record/4,000-character bounds stay in place.

Ordered migration 4 atomically replaces/rebuilds only FTS and its triggers, preserving
schema-3 authoritative data and WAL-inclusive backup/rollback. Forget removes the
same derived index artifacts; there is no new durable search store. Operational
diagnostics log counts, selected IDs/revisions and duration without private words.
Synthetic 5,000-record benchmark query-pair median/p95 changed from 0.592/0.763 ms
to 1.504/1.981 ms on the same cloud host. The bounded cost is acceptable for this
quality correction. Keep gathering owner relevance/abstention feedback before
considering embeddings or model-generated rewriting as a separate design decision.
