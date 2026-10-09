"""Bounded lexical retrieval and exact per-response evidence mapping."""

import json
import logging
import re
import sqlite3
from dataclasses import asdict, dataclass
from time import perf_counter
from uuid import uuid4

from kat_core.memory_lexical import lexical_normalizer, weak_query_terms
from kat_core.memory_schemas import MemoryContextItem
from kat_core.memory_store import MemoryStore
from kat_core.schemas import AuditEntry
from kat_core.storage import Store, timestamp

MAX_MEMORIES = 4
MEMORY_CHARACTER_BUDGET = 4000
MAX_CANDIDATES = 50
logger = logging.getLogger(__name__)
STOP_WORDS = frozenset(
    [
        "a",
        "about",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
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
        "practical",
    ]
)


def terms(query: str, limit: int = 12) -> list[str]:
    # Quoting only letters/numbers makes arbitrary input inert FTS syntax.
    # Preserve characters such as German ß; SQLite performs the index's case
    # and diacritic normalization. Python casefold would rewrite ß to ss first.
    tokens = re.findall(r"[^\W_]+", query[:2000].lower(), re.UNICODE)
    return list(
        dict.fromkeys(token for token in tokens if len(token) >= 3 and token not in STOP_WORDS)
    )[:limit]


def fts_query(query: str) -> str | None:
    tokens = terms(query)
    return " OR ".join('"' + token + '"' for token in tokens) if tokens else None


@dataclass(frozen=True)
class RetrievalDiagnostics:
    query_term_count: int
    normalized_term_count: int
    candidate_count: int
    relevance_rejected: int
    budget_rejected: int
    selected: tuple[tuple[str, int], ...]
    duration_ms: float


@dataclass(frozen=True)
class RetrievalResult:
    items: list[MemoryContextItem]
    diagnostics: RetrievalDiagnostics


class MemoryRetrieval:
    def __init__(self, memories: MemoryStore) -> None:
        self.memories = memories

    def retrieve(self, query: str, project_id: str | None) -> list[MemoryContextItem]:
        return self.retrieve_with_diagnostics(query, project_id).items

    def retrieve_with_diagnostics(self, query: str, project_id: str | None) -> RetrievalResult:
        started = perf_counter()
        tokens, match = terms(query), fts_query(query)
        selected: list[MemoryContextItem] = []
        normalized_count = candidate_count = relevance_rejected = budget_rejected = 0
        if match is not None:
            with lexical_normalizer() as normalize, self.memories.store.transaction() as db:
                query_words = normalize(" ".join(tokens))
                normalized_count = len(query_words)
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
                candidate_count = len(rows)
                for row in rows:
                    # Search and scoring use SQLite's identical Porter/unicode61
                    # tokenizer. Count distinct stems, not repeated inflections.
                    overlap = len(query_words & normalize(row["content"]))
                    if (
                        not query_words
                        or query_words <= weak_query_terms()
                        or overlap < min(2, normalized_count)
                        or overlap / normalized_count < 0.25
                    ):
                        relevance_rejected += 1
                        continue
                    record = self.memories.record(db, row)
                    item = MemoryContextItem(
                        **record.model_dump(include=set(MemoryContextItem.model_fields))
                    )
                    proposed = [*selected, item]
                    if (
                        len(
                            json.dumps(
                                [entry.model_dump() for entry in proposed], ensure_ascii=False
                            )
                        )
                        > MEMORY_CHARACTER_BUDGET
                    ):
                        budget_rejected += 1
                        continue
                    selected.append(item)
                    if len(selected) == MAX_MEMORIES:
                        break
        diagnostics = RetrievalDiagnostics(
            query_term_count=len(tokens),
            normalized_term_count=normalized_count,
            candidate_count=candidate_count,
            relevance_rejected=relevance_rejected,
            budget_rejected=budget_rejected,
            selected=tuple((item.id, item.revision) for item in selected),
            duration_ms=round((perf_counter() - started) * 1000, 3),
        )
        # No query terms, candidate wording or rejected identifiers are logged.
        logger.info("memory_retrieval %s", json.dumps(asdict(diagnostics), sort_keys=True))
        return RetrievalResult(selected, diagnostics)

    def record_usage(
        self,
        context: list[MemoryContextItem],
        session_id: str,
        assistant_id: str,
        *,
        db: sqlite3.Connection | None = None,
    ) -> None:
        if not context:
            return
        if db is None:
            with self.memories.store.transaction() as connection:
                self.record_usage(context, session_id, assistant_id, db=connection)
        else:
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
