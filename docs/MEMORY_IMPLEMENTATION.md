# Bounded memory in KAT 0.3

The owner's 0.3 directive approves explicit memory creation and local-only
retrieval. Automatic extraction, embeddings, planning and autonomy remain deferred.

Transcript, authoritative memory and working context stay separate. Migration 3
adds stable projects, structured memory items, immutable revision snapshots,
rebuildable SQLite FTS5, and response usage links. Existing migration backup,
rollback and downgrade protection apply. Sessions may select one stable project;
personal memory is eligible alongside that project, never another project.

Retrieval defaults off. Before each local user turn, structured eligibility and
lexical relevance select at most four whole records within a 4,000-character
serialized budget. Candidate reads are bounded and unrelated queries return zero.
One immutable set enters the active tool loop as explicitly untrusted data outside
the system prompt. OpenAI gets no memory context or usage records; normal selected
conversation history can still contain the same information. Tools remain governed
by their existing schemas, allowlist and approvals.

An owner edit creates a revision and requires the expected current revision,
preventing silent concurrent overwrite. Supersession is explicit. Usage links
identify the actual inserted revision, so later edits do not misrepresent evidence.
Forget deletes the current record, every revision and the FTS index entries;
usage/audit retain only safe identifiers. It does not erase original transcripts,
old migration backups or copies outside the memory subsystem. SQLite is not an
encrypted vault; only normal sensitivity is accepted and identifiable credentials
are rejected. Provenance stores references, never copied evidence text.

The desktop offers a Memory workspace, explicit Add/Remember review forms,
revision/provenance/usage inspection and a per-response memory inspector. Memory
management works while retrieval is off. This document records the implementation
contract; validation results belong in VALIDATION.md after checks execute.
