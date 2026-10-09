# Bounded memory in KAT 0.3 / 0.3.1

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

## 0.3.1 retrieval-quality correction

Owner testing stored “main user is named Luis” correctly, but a brand-new local
conversation asking “What is my name?” retrieved nothing. An automated regression
failed against the unchanged 0.3.0 implementation before the fix. Storage survived
restart; unicode61 indexed “named” separately from “name”, and raw-word relevance
had the same mismatch. Historical transient tool handling was unrelated.

Migration 4 replaces the external-content index and its triggers with SQLite
`porter unicode61`, then rebuilds from authoritative records. Historical migration
3 keeps its original definition. Representative schema-3 upgrade tests compare
all records/revisions/usage/projects/transcripts/settings/approvals/audit exactly,
including committed WAL in the backup. Injected migration failure restores the
old index, actual postings, version and data. A newer database still fails closed
in older KAT. Stop Core before manually restoring a protected pre-upgrade backup.

Search uses safely quoted alphanumeric terms: at most 12 unique terms from the
first 2,000 query characters. There are no raw operators or broad wildcard rules.
For scoring, SQLite FTS5 plus fts5vocab in a fresh RAM-only database normalize the
query and at most 50 indexed candidates with the **same actual tokenizer**. The
probe contains one input at a time, is closed afterward and adds no persistent
artifacts. No private normalized terms are cached; only a static generic-word set
is cached. Passing raw terms to FTS avoids applying the non-idempotent stemmer twice.

Distinct-stem overlap must be at least two, or one for a single-stem query, and
cover at least 25% of query stems. Queries consisting entirely of general weak
words (current/information/main/model/owner/project/setup/style/thing/user) abstain;
those words can contribute when accompanied by other evidence. Ranking, eligibility,
four-record/4,000-character budget and the active tool-loop snapshot are unchanged.
OpenAI exclusion and all approval/allowlist checks remain independent of retrieval.

| Stored wording | New-conversation question | Regression result |
| --- | --- | --- |
| main user is named Luis | What is my name? | Selected |
| The owner's name is Luis. | What am I named? | Selected |
| KAT should prefer local models when practical. | Which model setup do I prefer? | Selected |
| The user prefers local inference for KAT. | Do I normally prefer cloud or local inference? | Selected |
| The KAT project is currently focused on persistent memory. | What is the current focus of the KAT project? | Selected only in that project |
| I prefer concise responses. | What response style do I prefer? | Selected without synonyms |

Production code has no Luis/name-question special case; alternate names and other
domains are covered. Weather/name, cooking/model preference, generic-only queries,
unrelated pins and cross-project cases abstain. Unicode tests cover café/cafe,
Cyrillic case and literal German/Chinese terms. Porter is chiefly English stemming:
it leaves focus/focused different and does not equate Straße/STRASSE or segment
Chinese semantically. Synonyms such as car/automobile still miss. Additional query
words can fail overlap (for example “Which name was recorded?” against the short
named record). Sparse queries can conflate universe/university; a campus query
rejects the universe record through the two-stem gate. These are lexical limits,
not claims of semantic disambiguation. Inspect response evidence and continue
real-world relevance testing before proposing embeddings.

Safe diagnostics report term counts, candidate/relevance/budget counts, selected
ID/revision pairs and duration, with no private query/candidate wording or rejected
identifiers. Forget removes current/revision/stemmed-index wording, including old
postings; no new persistent probe store needs deletion. Original transcripts and
migration backups remain separate, as before.

The existing 5,000-record/100-iteration benchmark measures one matching plus one
unrelated query per sample. On the same cloud host, baseline median/p95 were
0.592/0.763 ms and 0.3.1 measured 1.504/1.981 ms. This roughly 0.9 ms median increase
per query pair buys consistent normalization while keeping indexed, bounded reads.
It is neither model inference nor GPU timing. Actual installed Windows acceptance
and exact-source release evidence are recorded in VALIDATION.md.
