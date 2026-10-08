# KAT product foundation

KAT is a persistent, local-first personal AI assistant for Windows. The human owner is the product designer and director; implementation, tests, documentation, and tooling are agent responsibilities.

## This release

KAT provides desktop text conversation backed by an authenticated local Python service and an explicitly selected OpenAI or local Ollama model. Users create and revisit sessions, change their model settings, ask for the local time, and request an allowlisted application such as Notepad. Application launch requires an explicit approval. Users can inspect the audit trail and pending requests.

Conversation history, settings, approval state, and audit events survive restarts. OpenAI keys come from current-user Windows Credential Manager or optional development environment overrides, never SQLite or React. The desktop controls its own authenticated Core process and reports startup failures.

"Local-first" describes ownership and persistence of data. The OpenAI adapter sends conversation context and tool descriptions to OpenAI. The Ollama adapter sends them only to an independently installed loopback backend and never falls back to cloud. Offline conversation requires installed local weights and a running local backend. The service and stored history remain usable for viewing without a model key.

## Interaction principles

- Keep the chat interface calm, readable, and keyboard accessible.
- Show failures as actionable errors; never substitute a fabricated model reply.
- Show the requested action and validated arguments before approval.
- Remember sessions locally without inventing a separate memory system.
- Keep permission decisions under the owner's control.

## Explicit exclusions

Voice, wake-word detection, background autonomy, scheduling, email/calendar integrations, browser automation, arbitrary shell access, destructive tools, and semantic long-term memory are excluded. SQLite conversation history is the persistence layer for this slice.

## Acceptance criteria

The desktop connects to an authenticated local Core; explicit local or OpenAI conversations use persisted context; session history can be recovered after a restart; tools are validated and governed by risk; application launches require approval; requests, decisions, outcomes, and errors are auditable. Automated deterministic tests and production build checks must pass. The real installed Windows/local-backend sequence is automated in CI. Live OpenAI account access and owner GPU performance are separate manual validations; see VALIDATION.md.

## Approved release sequence

The validated 0.1 foundation is followed by 0.1.1 installed-application readiness, secure credential storage and better provider errors. Release 0.2 adds local AI inference with OpenAI optional. Then implementation stops for owner review of a memory architecture proposal. Persistent personal intelligence in 0.3+ requires explicit approval at that gate. See [ROADMAP.md](ROADMAP.md) for scope and acceptance criteria. The initial transcript storage remains distinct from personal memory.
