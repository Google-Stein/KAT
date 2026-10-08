"""Measure bounded retrieval over a synthetic personal-scale database, no private data."""

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from kat_core.memory_retrieval import MemoryRetrieval
from kat_core.memory_schemas import MemoryCreate
from kat_core.memory_store import MemoryStore
from kat_core.storage import Store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=5000)
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args()
    if not 100 <= args.records <= 100000 or not 10 <= args.iterations <= 1000:
        raise SystemExit("Use 100–100000 records and 10–1000 iterations")
    with tempfile.TemporaryDirectory(prefix="kat-memory-benchmark-") as directory:
        store = Store(Path(directory) / "kat.sqlite3")
        try:
            memories = MemoryStore(store)
            for index in range(args.records):
                text = (
                    "KAT should prefer local models when practical."
                    if index % 100 == 0
                    else f"Project specimen {index} uses copper calibration for sensor {index}."
                )
                memories.create(MemoryCreate(content=text, confirmed=True))
            retrieval = MemoryRetrieval(memories)
            samples = []
            for _ in range(args.iterations):
                start = time.perf_counter()
                assert retrieval.retrieve("Do I prefer local or cloud models for KAT?", None)
                assert retrieval.retrieve("What is the weather in Oslo?", None) == []
                samples.append((time.perf_counter() - start) * 1000)
            print(
                json.dumps(
                    {
                        "records": args.records,
                        "iterations": args.iterations,
                        "two_queries_median_ms": round(statistics.median(samples), 3),
                        "two_queries_p95_ms": round(
                            sorted(samples)[int(len(samples) * 0.95) - 1], 3
                        ),
                        "max_candidates_per_query": 50,
                    },
                    sort_keys=True,
                )
            )
        finally:
            store.close()


if __name__ == "__main__":
    main()
