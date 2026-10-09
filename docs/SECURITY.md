# Security model

## Bounded weather, system and file capabilities (0.4)

Weather contacts only fixed Open-Meteo HTTPS geocoding/forecast endpoints, with
redirects disabled, no proxy-environment inheritance, no retries, bounded
responses and deadlines. The owner explicitly resolves/confirms a city; no OS
geolocation is read. The configured coordinates and place query go to that
external non-AI provider, even with local inference.

System status uses psutil and fixed Win32 APIs. No shell, process command lines,
environment, hostname, credential or arbitrary registry contents are exposed.
CPU model and GPU VRAM may be unavailable rather than invoking vendor commands.

Root registration is an authenticated owner action through Settings, with native
folder selection on Windows and explicit Add. Models and memories cannot register
roots or grant content permission. Arguments expose only root IDs and relative
paths. Local fixed-drive roots are allowed; drive roots, UNC/network/device
namespaces, traversal, ADS, reserved device names and path aliases are rejected.
Every path component is checked. POSIX uses anchored no-follow descriptors.
Windows pins directory handles without delete-sharing, rejects reparse points and
compares handle-resolved paths to each exact component before reading the same
opened handle. String-prefix checks are not used as containment authority.

Listing and filename search never read bodies. Content reads always require a
fresh specific approval, including when risk settings allow other medium-risk
tools. Removal revokes pending reads. Only bounded UTF-8 files with allowlisted
text extensions are read; binaries, oversized files and special files are rejected.
Returned text is rendered as escaped text. Files cannot be written, renamed or
deleted through tools. File audit stores metadata/byte counts, not bodies; the
normal local transcript and approval record retain the text. No implicit model
continuation or automatic memory extraction occurs after approval. Review
[CAPABILITIES.md](CAPABILITIES.md) for limits and the same-user threat boundary.

## Trust boundaries

The model, its replies, and all proposed tool arguments are untrusted. Validation, risk classification, authorization, and execution happen inside Core. Model prose cannot grant permission. The webview has only narrow native lifecycle commands; arbitrary shell access is absent.

This is a personal local application, not a multiuser network service. Core binds to loopback and requires a bearer token. Explicit CORS origins and native content security policy restrict the desktop's HTTP surface. These controls do not protect against malware or another process already running with the same user's privileges.

## Tools

Every registered tool has a description, a structured argument schema, and permission/risk metadata. Unknown names, extra arguments, invalid application IDs, and paths supplied by the model are rejected. `get_local_time` is low risk. `open_application` is medium risk, requires approval, and resolves a configured ID to a fixed executable and argument vector. It uses direct process creation without a shell.

High-risk, destructive, and security-sensitive tools are unavailable in this release. Adding a tool requires tests for validation, policy, audit records, and denial behavior. New capabilities must define a deliberate policy; they must not inherit a permissive default merely because the model requests them.

Approval is durable and specific to the stored action/arguments. A decision is claimed atomically, and duplicate decisions cannot launch the action again. If the process crashes after claiming execution, KAT does not automatically repeat the action. The audit log records uncertainty or failure rather than asserting an unobserved outcome.

## Secrets and privacy

Normal Windows use stores OpenAI keys in Windows Credential Manager through a native masked dialog. For development, optional `OPENAI_API_KEY` (or preferred `KAT_OPENAI_API_KEY`) environment overrides and an explicitly loaded ignored `.env` file are supported. Do not commit it, put it in a frontend build, save it in SQLite, or include it in logs. Core reports only whether the key is configured. SDK tracing is disabled so chat content is not additionally exported to a trace service.

OpenAI requests transmit conversation context and tool descriptions/results needed for that turn. Local Ollama selection uses installed local weights without OpenAI; cloud-backed Ollama models are rejected before context is sent. Review the model provider's data handling separately. There is no telemetry integration in this bootstrap.

The native launcher creates a fresh local API token each run, passes it to the child through the process environment, and holds it in memory. The browser development token input is memory-only. A standalone CLI may use a private token file; protect it as a secret and do not put it in a shared directory.

SQLite data and local logs are sensitive user data and are not encrypted in this release. Store them under the user's local application data directory. Windows account permissions and disk encryption are the initial protection. Backups must protect both the database and any associated SQLite WAL state; shut down Core before copying the database for the simplest consistent backup.

## Audit and observability

Tool requests, approval requirements/decisions, execution results, timestamps, and errors are recorded locally. Provider and startup failures use useful error codes without echoing secret-bearing raw exceptions. Production file/stream handlers filter raw provider/SDK HTTP diagnostics at every level; KAT emits sanitized categories and timing/status metadata instead. Audit events are application records, not a tamper-proof forensic store: another process with access to the user's files can alter them.

## Reporting

Report a security issue privately to the repository owner. Avoid including API keys, runtime tokens, or real transcripts in an issue. Include the affected version and a minimized reproduction. This release has no public vulnerability-reporting endpoint.

## Windows provider credentials

Windows Settings uses a native credential dialog and the current user's Windows
Credential Manager generic entry `KAT/OpenAI`. Provider keys never cross React IPC,
enter SQLite, or appear in logs. Native commands expose booleans only, plus the
existing authenticated Core connection after restart. Key buffers are zeroized
where Rust/Win32 APIs permit. Core necessarily receives the provider key in its
private child environment and the SDK holds it in memory; same-user malware or
administrators are outside this process-isolation boundary.

Explicit nonempty `KAT_OPENAI_API_KEY`, then `OPENAI_API_KEY`, override the vault
for development; Settings identifies this override. Development `.env` remains
explicitly opt-in. Save/replace validates before writing; cancel preserves the
old key and Core. Remove needs explicit UI confirmation. A failed vault operation
does not restart Core. Successful changes restart the owned Core and refresh its
in-memory bearer token; conversations and approvals remain in SQLite. Unsupported
platforms report that native storage is unavailable rather than storing plaintext.

## Database upgrades

Ordered schema migrations execute in one exclusive SQLite transaction. Failed
steps roll back DDL, data and `user_version`; unsupported newer schemas fail
closed. Before upgrading existing data, SQLite's backup API creates a uniquely
named restricted-permission `.backup-vN-*` sibling containing committed WAL data.
Backups contain personal transcripts: protect them like the original database.
Restore only while KAT is stopped, preserving the failed original for diagnosis.
There is no downgrade or automatic destructive recovery.

## Local inference trust boundary

A loopback URL does not alone prove local inference: Ollama can advertise cloud
models. KAT filters remote/cloud tags and rejects `remote_host`, `remote_model`,
cloud capabilities and remote manifests before sending conversation context.
Known cloud-suffixed tags are also rejected. Disable Ollama cloud features
(`OLLAMA_NO_CLOUD=1` for its server) and use installed local weights. KAT trusts the
owner-controlled local backend to report metadata honestly; it cannot sandbox an
independently configured inference server or stop a malicious same-user service
from transmitting data. Native local outputs have the same untrusted status as
OpenAI outputs. Model prose is never parsed into executable actions.

## Explicit memory boundary (0.3)

Only owner-confirmed entry/selection creates memory; retrieval defaults off and
only normal sensitivity is accepted. Conservative deterministic patterns reject
identifiable API keys, bearer tokens, private PEM keys and obvious password/token
assignments. This is not exhaustive secret detection or an encrypted vault. Never
save highly sensitive data, even if a pattern fails to recognize it. Scope changes
require a new explicit item; ordinary edits cannot broaden project evidence into
personal scope. All memory APIs require the same authenticated local connection.

Stored procedures remain untrusted evidence. Tests simulate a model obeying
poisoned memory: unknown shell tools and PowerShell IDs are rejected, and even an
allowlisted application remains pending approval. No new execution capability,
permission elevation, provider change or autonomous action comes from memory.

OpenAI retrieves zero records, serializes no memory-record payload and records
no usage. Local failure has no cloud fallback. This does not redact ordinary
transcript history or remembered information in a prior assistant reply; those
can leave the device when the owner explicitly selects OpenAI. The loopback
backend trust limitations above also apply to injected memory.

Edits preserve private revisions until Forget. Forget deletes current content,
all revisions and FTS search structures; search is rebuilt to discard old postings.
SQLite secure deletion is enabled for active database cells. Provenance copies
no evidence text. Operational audit/usage retain only safe IDs/categories, not
forgotten wording. This is logical removal from the memory system, not forensic
erasure of WAL/filesystem snapshots, older backups or original transcripts.
Forgetting cannot revoke context already supplied to an in-progress model run;
its later usage contains IDs only if the record was forgotten in the meantime.

In 0.3.1 migration 4 rebuilds the existing derived FTS index with Porter/unicode61;
authoritative wording and revisions are unchanged. Relevance normalization uses a
separate RAM-only SQLite probe, closes after retrieval and caches no private terms.
Forget deletes/rebuilds the same persistent FTS artifacts; it creates no additional
durable normalized store. Pre-upgrade backups still contain the original private
data and require the same protection. Diagnostics contain counts, selected memory
IDs/revisions and duration, never query words, candidate text or rejected IDs.
Stemming can increase lexical ambiguity; conservative relevance and project/date/
status filters remain. Retrieved text still cannot authorize an action.
