"""Bounded lexical retrieval and exact per-response evidence mapping."""

import json
import re
from uuid import uuid4

from kat_core.memory_schemas import MemoryContextItem
from kat_core.memory_store import MemoryStore
from kat_core.schemas import AuditEntry
from kat_core.storage import Store, timestamp

MAX_MEMORIES = 4
MEMORY_CHARACTER_BUDGET = 4000
MAX_CANDIDATES = 50
STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "should",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "us",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "tell",
        "please",
        "remember",
        "practical",
    ]
)


def terms(query: str, limit: int = 12) -> list[str]:
    # Quoting only letters/numbers makes arbitrary input inert FTS syntax.
    tokens = re.findall(r"[^\W_]+", query[:2000].casefold(), re.UNICODE)
    return list(
        dict.fromkeys(token for token in tokens if len(token) >= 3 and token not in STOP_WORDS)
    )[:limit]


def fts_query(query: str) -> str | None:
    tokens = terms(query)
    return " OR ".join('"' + token + '"' for token in tokens) if tokens else None


class MemoryRetrieval:
    def __init__(self, memories: MemoryStore) -> None:
        self.memories = memories

    def retrieve(self, query: str, project_id: str | None) -> list[MemoryContextItem]:
        tokens, match = terms(query), fts_query(query)
        if match is None:
            return []
        with self.memories.store.transaction() as db:
            now = timestamp()
            rows = db.execute(
                "SELECT m.* FROM memory_fts JOIN memory_items m ON m.rowid=memory_fts.rowid "
                "WHERE memory_fts MATCH ? AND m.status='confirmed' "
                "AND (m.expires_at IS NULL OR m.expires_at>?) "
                "AND (m.effective_at IS NULL OR m.effective_at<=?) "
                "AND (m.scope='personal' OR (m.scope='project' AND m.project_id=?)) "
                "ORDER BY m.pinned DESC,m.importance DESC,bm25(memory_fts),m.id LIMIT ?",
                (match, now, now, project_id, MAX_CANDIDATES),
            ).fetchall()
            selected: list[MemoryContextItem] = []
            for row in rows:
                words = set(terms(row["content"], limit=1000))
                overlap = len(set(tokens) & words)
                # Multiword questions need two meaningful matches; a single explicit
                # keyword may match directly. Pins affect ranking, never eligibility.
                if overlap < min(2, len(tokens)) or overlap / len(tokens) < 0.25:
                    continue
                record = self.memories.record(db, row)
                item = MemoryContextItem(
                    **record.model_dump(include=set(MemoryContextItem.model_fields))
                )
                proposed = [*selected, item]
                if (
                    len(json.dumps([entry.model_dump() for entry in proposed], ensure_ascii=False))
                    > MEMORY_CHARACTER_BUDGET
                ):
                    continue
                selected.append(item)
                if len(selected) == MAX_MEMORIES:
                    break
            return selected

    def record_usage(
        self, context: list[MemoryContextItem], session_id: str, assistant_id: str
    ) -> None:
        if not context:
            return
        with self.memories.store.transaction() as db:
            now = timestamp()
            for item in context:
                # No copied wording: a concurrent Forget cannot resurrect content.
                db.execute(
                    "INSERT INTO memory_usage VALUES (?,?,?,?,?,?)",
                    (item.id, item.revision, session_id, assistant_id, "ollama", now),
                )
            Store._insert_audit(
                db,
                AuditEntry(
                    id=str(uuid4()),
                    timestamp=now,
                    event="memory_retrieved",
                    session_id=session_id,
                    details={
                        "memory_ids": [item.id for item in context],
                        "count": len(context),
                        "provider": "ollama",
                    },
                ),
            )
