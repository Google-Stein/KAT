# Security model

## Trust boundaries

The model, its replies, and all proposed tool arguments are untrusted. Validation, risk classification, authorization, and execution happen inside Core. Model prose cannot grant permission. The webview has only narrow native lifecycle commands; arbitrary shell access is absent.

This is a personal local application, not a multiuser network service. Core binds to loopback and requires a bearer token. Explicit CORS origins and native content security policy restrict the desktop's HTTP surface. These controls do not protect against malware or another process already running with the same user's privileges.

## Tools

Every registered tool has a description, a structured argument schema, and permission/risk metadata. Unknown names, extra arguments, invalid application IDs, and paths supplied by the model are rejected. `get_local_time` is low risk. `open_application` is medium risk, requires approval, and resolves a configured ID to a fixed executable and argument vector. It uses direct process creation without a shell.

High-risk, destructive, and security-sensitive tools are unavailable in this release. Adding a tool requires tests for validation, policy, audit records, and denial behavior. New capabilities must define a deliberate policy; they must not inherit a permissive default merely because the model requests them.

Approval is durable and specific to the stored action/arguments. A decision is claimed atomically, and duplicate decisions cannot launch the action again. If the process crashes after claiming execution, KAT does not automatically repeat the action. The audit log records uncertainty or failure rather than asserting an unobserved outcome.

## Secrets and privacy

Keep `OPENAI_API_KEY` (or the preferred `KAT_OPENAI_API_KEY` alias) in a process environment or an ignored `.env` file. Do not commit it, put it in a frontend build, save it in SQLite, or include it in logs. Core reports only whether the key is configured. SDK tracing is disabled so chat content is not additionally exported to a trace service.

OpenAI requests transmit conversation context and tool descriptions/results needed for that turn. This is not an offline assistant. Review the model provider's data handling separately. There is no telemetry integration in this bootstrap.

The native launcher creates a fresh local API token each run, passes it to the child through the process environment, and holds it in memory. The browser development token input is memory-only. A standalone CLI may use a private token file; protect it as a secret and do not put it in a shared directory.

SQLite data and local logs are sensitive user data and are not encrypted in this release. Store them under the user's local application data directory. Windows account permissions and disk encryption are the initial protection. Backups must protect both the database and any associated SQLite WAL state; shut down Core before copying the database for the simplest consistent backup.

## Audit and observability

Tool requests, approval requirements/decisions, execution results, timestamps, and errors are recorded locally. Provider and startup failures use useful error codes without echoing secret-bearing raw exceptions. Audit events are application records, not a tamper-proof forensic store: another process with access to the user's files can alter them.

## Reporting

Report a security issue privately to the repository owner. Avoid including API keys, runtime tokens, or real transcripts in an issue. Include the affected version and a minimized reproduction. This release has no public vulnerability-reporting endpoint.
