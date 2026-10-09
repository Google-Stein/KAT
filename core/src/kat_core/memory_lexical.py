"""Use SQLite's actual tokenizer for relevance, never an approximate Python stemmer.

The bounded scoring probe exists only in RAM and is closed after each retrieval.
It contains one input at a time; no additional persistent search artifacts exist.
"""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache

MEMORY_TOKENIZER = "porter unicode61"
WEAK_QUERY_WORDS = "current information main model owner project setup style thing user"


@contextmanager
def lexical_normalizer() -> Iterator[Callable[[str], frozenset[str]]]:
    db = sqlite3.connect(":memory:")
    try:
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute(f"CREATE VIRTUAL TABLE input USING fts5(content, tokenize='{MEMORY_TOKENIZER}')")
        db.execute("CREATE VIRTUAL TABLE lexemes USING fts5vocab(input,'row')")

        def normalize(text: str) -> frozenset[str]:
            db.execute("DELETE FROM input")
            db.execute("INSERT INTO input(rowid,content) VALUES (1,?)", (text,))
            return frozenset(row[0] for row in db.execute("SELECT term FROM lexemes"))

        yield normalize
    finally:
        db.close()


@lru_cache(maxsize=1)
def weak_query_terms() -> frozenset[str]:
    # General low-information vocabulary, not identity intents or owner data.
    # These terms still contribute in multiword questions; without any other
    # lexical evidence a generic-only query abstains.
    with lexical_normalizer() as normalize:
        return normalize(WEAK_QUERY_WORDS)
