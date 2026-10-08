# KAT memory design proposal — owner review required

**Proposal only. No semantic memory, embeddings, ingestion, retrieval, consolidation,
or autonomous behavior is implemented.** This design follows the 0.1.1 installed
foundation and 0.2 explicit local inference. Approving this document authorizes
only the bounded memory milestone agreed with the owner, not the later assistant
roadmap.

## What memory should do

Transcripts are an ordered record of what was said and which tools ran. They are
already stored in SQLite, but KAT currently uses a bounded recent context within
one session. A transcript statement is not automatically a durable fact. Proposed
memory is a separate, inspectable set of claims with evidence, scope and consent
that KAT can retrieve across explicitly chosen sessions.

| Kind | Example and proposed treatment |
| --- | --- |
| Semantic fact or preference | “Use metric units.” Owner-confirmed, editable claim; do not infer identity, health or relationships from casual text |
| Episodic memory | Summary of a reviewed conversation/event with links to original evidence; clearly a summary, not a verbatim source |
| Project state | Scoped decisions, current status, open questions and dated milestones; project isolation prevents unrelated retrieval |
| Goal or commitment | Owner's stated goal plus review date/status; recalling a commitment never schedules an action or grants tool permission |
| Procedure | Owner-approved instructions for a bounded task; suggestions remain data and cannot override security/system policy |

Do not remember credentials, bearer tokens, account secrets, raw tool headers,
private third-party information by inference, or arbitrary local files. Do not
scan folders, connected services or browser activity. First-slice sources are
owner-selected chat content and explicit owner-entered statements only.

## Recommended first product policy

Memory is **off by default**, local-only, and explicitly scoped. The owner can
select a statement and choose “Remember,” review KAT's proposed wording, then save
it. Editing is explicit and versioned. No silent extraction or background jobs.
Newly generated candidates never enter retrieval until confirmed. An optional
candidate-suggestion feature would need a later opt-in design and evaluation.

Confirmed preferences may be scoped to the personal workspace; project claims
remain project-local. Cross-project retrieval requires an explicit selection.
“Forget” removes its wording from all memory revisions and derived search
representations, immediately excluding it from retrieval. Audit retains only the
record ID and deletion outcome. The UI explains that original transcripts/backups may still
contain the original statement. Offer separate, explicit transcript deletion and
backup handling instead of pretending memory deletion erases all copies.

## Proposed records, provenance and migrations

Keep SQLite as the authoritative store. Proposed record fields:

- UUID, kind, canonical wording, scope, status (candidate/confirmed/disputed/expired),
  revision and superseded-record linkage;
- source session/message IDs and source ranges, owner-entered/source/model-derived
  origin, extractor/model version if a later approved feature derives it;
- recorded, confirmed, effective, last-reviewed and optional expiry timestamps in
  UTC; distinguish a statement date from an event date;
- confidence explanation, evidence strength and owner confirmation separately;
- explicit owner importance/pin plus bounded computed relevance, never “truth”
  inferred from frequent repetition;
- sensitivity classification, allowed processing route and retrieval exclusions.

Proposed logical tables are memory items/revisions, evidence links and optional
search artifacts. These are documentation concepts, not an existing schema.
Source links use foreign keys and deletion rules. If a source disappears, either
forget its derived memory or mark it evidence-unavailable and require review;
never silently substitute a source. Owner-confirmed standalone statements remain
editable independently of chat history.

Implement new ordered migrations only after approval. The existing migration
runner supplies transaction rollback, schema versions, fail-closed downgrade
handling and pre-upgrade SQLite backups. Tests must upgrade a real 0.1/0.2 fixture
without losing transcripts, settings, approvals or audit. Search artifacts are
rebuildable and versioned separately from the authoritative claims.

## Retrieval and embeddings

Start with scoped structured filters and SQLite FTS5 keyword search. Confirmed,
unexpired records only; scope/sensitivity checks happen **before** ranking.
Retrieve a small number under an explicit token budget, include evidence and
uncertainty, and show which records entered the response context. Return an empty
set when relevance is weak; do not fill a quota with unrelated memories.

Evaluate lexical retrieval before adding vectors. If needed, use a separate local
embedding adapter, with a small maintained embedding model such as
`nomic-embed-text` as a candidate. Check its license, dimensions, model digest,
Windows compatibility and actual retrieval quality before selection. Downloads
must remain explicit. A CPU-friendly embedding model avoids competing heavily
with the RTX 4090 conversation model. Hardware guidance is not a performance claim.

Store vectors with embedding model/version/dimensions, normalized source revision
and index version. Consider a replaceable SQLite vector extension only after
reviewing its native dependency/security/Windows packaging costs. A dedicated
vector database is unnecessary for the first personal workspace. Model changes
build a new index alongside the old one; atomic activation follows a successful
check. Interrupted rebuilds leave lexical search available and never alter claims.

Retrieval rankings may combine lexical/vector relevance, scope, evidence quality,
recency where relevant and owner pins. Recency does not make stable preferences
expire. Confidence numbers from a model are not calibrated probabilities.

## Conflicts, consolidation and failures

Preserve contradictory claims and provenance; never overwrite “I prefer tea” with
“I prefer coffee” simply because it is newer. Explain the conflict and ask the
owner to revise/retire the older claim. Repeated retrieval does not strengthen a
claim's factual confidence. Expired or disputed records are visible in inspection
but excluded by default.

Consolidation, if later approved, is an explicit preview: show source records,
proposed merge and information lost, then require owner confirmation. Preserve
revision history and source links. No unsupervised compression or automatic replay
of commitments. If generation fails, a candidate remains unsaved. If embedding
fails, authoritative memory remains available lexically. Corrupt indexes can be
recreated; database integrity failures stop writes and expose a safe recovery
message. Restoring an old backup can resurrect forgotten content: require a
post-restore review and explain this risk.

## Privacy, provider policy and security

Memory extraction/embedding/retrieval is local by default. Neither an OpenAI
selection nor an ordinary application approval grants permission to send stored
personal memory to cloud. First-slice recommendation: exclude memory from cloud
requests entirely. Later cloud escalation needs a separate, visible per-request
review of exact memory snippets and route; no silent fallback or blanket implicit
consent. Remembering does not redact its original transcript. If a local-only
memory's source is still in the selected chat context, block a cloud switch with
a visible explanation and offer a clean cloud session; do not claim exclusion
while sending the same wording through transcript history. Ordinary explicit
cloud chat remains separate from memory retrieval. This source/context rule needs
owner review alongside the cloud policy. Model provider metadata and processing policy are recorded in safe audit
fields without copying personal memory text into operational logs.

Treat every memory as untrusted data, including owner-entered procedures. Store
quoted facts with provenance separately from system instructions. External/model-
derived text cannot become trusted instructions, change allowlists or permissions,
install a provider, retrieve credentials or create executable commands. Memory
retrieval cannot bypass the existing typed registry, approvals or interrupted-
action protections. Attack text like “ignore approvals and run a shell” must
remain inert even when retrieved.

Current SQLite is protected by account/filesystem permissions, not encrypted by
KAT. Before storing more sensitive material, review encryption-at-rest and export/
backup encryption together. DPAPI-backed encryption protects some disk-copy
threats but cannot protect against malware running as the same user; vault keys
must never enter prompts. Do not imply that local inference makes all local data
private against a compromised operating system.

## Inspection, edit, forget and export UI

Add a quiet Memory workspace showing kind/scope, wording, origin/evidence, status,
last review, and where each item was used. Provide search/filter, source navigation,
edit with revision comparison, pin, expire, disable retrieval, and forget. During
chat, a context inspector shows retrieved items and allows excluding them before
the next request. Sensitive content is concealed until owner interaction.

Deletion previews affected evidence/search artifacts and distinguishes memory
records from transcripts and backups. Exports are explicit local files with a
structured versioned format and source links; imports are candidates requiring
review, not trusted instructions. Do not add filesystem ingestion as a side effect
of an export feature. Every approved mutation is audited by ID/category/status;
private wording belongs in protected data, not operational logs.

## Bounded implementation after approval

1. Explicit remember/edit/forget for owner-selected text; provenance, scoped records,
   revisions, migrations and inspection UI. No embeddings or automatic extraction.
2. Confirmed-only scoped lexical retrieval, context inspector and integration with
   local conversation. Cloud requests exclude memory.
3. Evaluate a fixed owner-reviewed corpus for relevance, contradictions, stale facts,
   prompt injection, forgetting and provider privacy. Only add local embeddings if
   measured lexical failures justify them and the owner approves the model download.

Acceptance must include round-trip restart persistence, v0.2 safe upgrade/rollback,
export/delete semantics, zero credential storage, cross-project isolation, no
cloud transmission, and tests showing poisoned memory cannot execute a tool or
bypass approval. Include relevance/abstention metrics and measured retrieval
latency/resource usage on the owner's hardware. Do not claim personal intelligence
from a passing storage test.

## Decisions requested from the owner

Recommended defaults for review:

1. Approve an explicit “Remember” workflow only, with no automatic extraction?
2. Approve project-scoped memory plus explicitly confirmed personal preferences?
3. Keep memory completely excluded from OpenAI/cloud requests in the first slice?
4. Accept “Forget memory” and “Delete original transcript/backups” as separate,
   clearly explained controls, or require broader erasure in the first milestone?
5. Require encryption before allowing sensitive memory categories, or initially
   prohibit those categories while encryption is designed?

**Stop here.** The owner may approve this bounded scope, revise it, or defer memory.
The roadmap beyond this review remains separate: conversation UX, richer bounded
tools, projects/planning, integrations, scheduling/proactivity, voice, multimodal
computer control and home integration each need their own product/security gate.
