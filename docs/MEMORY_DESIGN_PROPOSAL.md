# Memory design — bounded 0.3 approved

The owner's explicit 0.3 implementation directive approves only the scope below.
The former STOP/REVIEW gate is satisfied for this milestone. Implementation and
validation are separate: actual test/release evidence belongs in VALIDATION.md.

## Approved / implemented scope

- Explicit Add memory and Remember review/edit/confirm; no model needed to save.
- Retrieval off by default; records can be managed while it is off.
- Personal and stable project scopes; one active project per conversation.
- Semantic facts/preferences, events, project state, commitments and working
  procedures. These are owner statements/data, never truth scores or authorization.
- UUIDs, dates/effective/expiry/review metadata, status, origin, normal sensitivity,
  pin/importance, source references, revision history and explicit supersession.
- Structured eligibility plus bounded FTS5 lexical retrieval with abstention,
  at most four whole records within 4,000 serialized characters.
- Local-only, once-per-turn untrusted context outside system instructions.
- OpenAI receives zero memory records and zero usage, while explicitly selected
  ordinary transcript context may already contain the same information. No cloud
  switch is blocked merely because that transcript overlaps remembered wording.
- Per-response exact-revision inspector and persisted where-used references.
- Inspect/edit/status/supersede/forget; no autonomous conflict resolution.
- Forget removes current/revision/FTS wording, not original transcripts/backups.
- Existing backed-up atomic migrations, rebuildable search and safe audit IDs.
- Normal sensitivity only; deterministic credential rejection. SQLite is local
  storage, not encrypted by KAT and not a sensitive-data vault.

See ARCHITECTURE.md, SECURITY.md, DECISIONS.md ADRs 018–022 and
MEMORY_IMPLEMENTATION.md for the concrete contracts and limitations.

## Tested versus manual acceptance

Deterministic tests exercise lifecycle, scope, retrieval, cloud HTTP exclusion,
credential rejection, poisoned-memory tool requests and v0.2.1 stale-tool behavior.
Installed Windows accessibility tests run the reviewed creation, enable, restart,
new local conversation, exact usage, edit and forget journey with actual Ollama.
VALIDATION.md records results; configured tests alone do not establish success.
Owner GPU/model quality and a live OpenAI account remain separate manual checks.

## Future proposals — not authorized or implemented

Automatic extraction, candidate suggestions, consolidation, embeddings/vector
search, automatic contradiction resolution, automatic forgetting, encrypted
sensitive categories, cloud memory sharing, full project management, planning,
scheduling and autonomous memory-driven actions require new owner review.
Gather real-world lexical relevance, abstention and scope feedback first. A future
retrieval design must show measured benefit, exact context transparency, local
ownership, reproducible migrations and no weakening of tool/privacy boundaries.
