# KAT product foundation

KAT is a persistent, local-first personal AI assistant for Windows. The human owner is the product designer and director; implementation, tests, documentation, and tooling are agent responsibilities.

## This release

KAT provides desktop text conversation backed by an authenticated local Python service and an explicitly selected OpenAI or local Ollama model. Users create and revisit sessions, change their model settings, ask for the local time, and request an allowlisted application such as Notepad. Application launch requires an explicit approval. Users can inspect the audit trail and pending requests.

Conversation history, settings, approval state, and audit events survive restarts. OpenAI keys come from current-user Windows Credential Manager or optional development environment overrides, never SQLite or React. The desktop controls its own authenticated Core process and reports startup failures.

"Local-first" describes ownership and persistence of data. The OpenAI adapter sends conversation context and tool descriptions to OpenAI. The Ollama adapter sends them only to an independently installed loopback backend and never falls back to cloud. Offline conversation requires installed local weights and a running local backend. The service and stored history remain usable for viewing without a model key.

The owner-approved 0.4 milestone adds external weather using an explicitly
configured city, fresh read-only system metrics, and registered local folders.
Owners choose folders through native UI and explicitly add them; each content
read requires separate approval. Listing and filename search stay inside those
roots. Returned text stays in the transcript, with metadata-only operational
audit and no automatic memory. Weather internet access is separate from AI
provider selection. See [CAPABILITIES.md](CAPABILITIES.md) for bounds.

## Interaction principles

- Keep the chat interface calm, readable, and keyboard accessible.
- Show failures as actionable errors; never substitute a fabricated model reply.
- Show the requested action and validated arguments before approval.
- Keep transcripts separate from explicitly confirmed personal/project memory.
- Keep permission decisions under the owner's control.

## Explicit exclusions

Voice, wake-word detection, background autonomy, scheduling, email/calendar integrations, browser automation, arbitrary shell access, destructive tools, automatic memory extraction, embeddings and cloud memory injection are excluded. Explicit owner-confirmed memory is approved for 0.3.

## Acceptance criteria

The desktop connects to an authenticated local Core; explicit local or OpenAI conversations use persisted context; session history can be recovered after a restart; tools are validated and governed by risk; application launches require approval; requests, decisions, outcomes, and errors are auditable. Automated deterministic tests and production build checks must pass. The real installed Windows/local-backend sequence is automated in CI. Live OpenAI account access and owner GPU performance are separate manual validations; see VALIDATION.md.

## Approved release sequence

The validated 0.1 foundation is followed by 0.1.1 installed-application readiness, secure credential storage and better provider errors. Release 0.2 adds local AI inference with OpenAI optional. The owner reviewed and approved the bounded 0.3 explicit-memory milestone. Further personal intelligence requires a new product decision. See [ROADMAP.md](ROADMAP.md) for scope and acceptance criteria. The initial transcript storage remains distinct from personal memory.

## Explicit memory in 0.3

Memory retrieval is off by default. Owners may manage records while it is off.
Add memory or choose Remember on a user/assistant message, review/edit the wording,
choose a kind and personal/project scope, then explicitly confirm the save. No
model call, extraction, candidate generation or background work creates memory.
Facts/preferences, events, project state, commitments and working preferences are
owner statements, not objective truth or authorization. Commitments schedule nothing.

Enable local retrieval to use relevant confirmed, unexpired memories with Ollama.
A conversation selects at most one project; personal records remain broadly
eligible. Other projects are excluded. Unrelated questions can retrieve nothing.
Memories used shows the exact inserted revision, not an invented explanation.
Edits preserve history; explicit supersession stops old evidence being retrieved.
Forget removes all memory wording, revisions and FTS search artifacts, while
transcripts/backups remain separate. Credentials and highly sensitive categories
are unsupported; local SQLite memory is not encrypted by KAT. OpenAI gets no
memory-record payload, but ordinary chat history can contain the same words.
