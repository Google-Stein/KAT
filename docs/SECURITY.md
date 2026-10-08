# Security model

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
