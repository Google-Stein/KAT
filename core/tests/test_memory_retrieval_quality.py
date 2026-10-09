"""Owner-discovered lexical retrieval regressions, without identity special cases."""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from kat_core.app import create_app
from kat_core.local_provider import OllamaRuntime
from kat_core.memory_lexical import lexical_normalizer
from kat_core.memory_retrieval import MemoryRetrieval
from kat_core.memory_schemas import MemoryCreate, ProjectCreate
from kat_core.memory_store import MemoryStore
from kat_core.storage import Store


@pytest.fixture
def memories(tmp_path: Path):
    store = Store(tmp_path / "kat.sqlite3")
    yield MemoryStore(store)
    store.close()


@pytest.mark.parametrize(
    "content,question",
    [
        ("main user is named Luis", "What is my name?"),
        ("The owner's name is Luis.", "What am I named?"),
        ("The account holder is named Amina", "What name do I have?"),
        ("KAT should prefer local models when practical.", "Which model setup do I prefer?"),
        (
            "The user prefers local inference for KAT.",
            "Do I normally prefer cloud or local inference?",
        ),
        ("I prefer concise responses.", "What response style do I prefer?"),
        ("My preference is green tea.", "Which tea is preferred?"),
        ("I remembered the mountain excursion.", "What excursion do I remember?"),
        ("I am working with copper sensors.", "What sensor work do I do?"),
        ("My models use copper calibration.", "Which copper model is used?"),
        ("I prefer café tables.", "Which cafe table do I prefer?"),
        ("The Москва project uses copper sensors.", "What sensors does the МОСКВА project use?"),
        ("The Straße project uses copper.", "Which copper project is on the Straße?"),
        ("The 响应方式 project uses copper.", "What copper project uses 响应方式?"),
    ],
)
def test_positive_quality_matrix(memories: MemoryStore, content: str, question: str) -> None:
    item = memories.create(MemoryCreate(content=content, confirmed=True))
    assert [r.id for r in MemoryRetrieval(memories).retrieve(question, None)] == [item.id]


@pytest.mark.parametrize(
    "content,question",
    [
        ("main user is named Luis", "What is the weather in Oslo?"),
        ("KAT should prefer local models when practical.", "How do I cook pasta?"),
        ("KAT should prefer local models when practical.", "Which model makes cooking easy?"),
        ("KAT should prefer local models when practical.", "models"),
        ("The project is current.", "What is the current project?"),
        ("The universe contains distant stars.", "Where is the university campus?"),
        ("main user is named Luis", '" OR * NOT NEAR() content:missing - [ ]'),
        ("main user is named Luis", "\x00\x00 *** ::: ()"),
    ],
)
def test_negative_and_hostile_quality_matrix(
    memories: MemoryStore, content: str, question: str
) -> None:
    memories.create(MemoryCreate(content=content, confirmed=True, pinned=True, importance=3))
    assert MemoryRetrieval(memories).retrieve(question, None) == []


def test_current_focus_is_project_isolated(memories: MemoryStore) -> None:
    project = memories.create_project(ProjectCreate(name="Active work"))
    other = memories.create_project(ProjectCreate(name="Other work"))
    item = memories.create(
        MemoryCreate(
            content="The KAT project is currently focused on persistent memory.",
            confirmed=True,
            scope="project",
            project_id=project.id,
            pinned=True,
        )
    )
    question = "What is the current focus of the KAT project?"
    retrieval = MemoryRetrieval(memories)
    assert retrieval.retrieve(question, None) == []
    assert retrieval.retrieve(question, other.id) == []
    assert [r.id for r in retrieval.retrieve(question, project.id)] == [item.id]


@pytest.mark.parametrize(
    "forms",
    [
        ("name", "named", "naming"),
        ("prefer", "prefers", "preferred", "preference"),
        ("remember", "remembered"),
        ("work", "working"),
        ("model", "models"),
        ("café", "cafe"),
        ("Москва", "МОСКВА"),
    ],
)
def test_sqlite_normalization_is_shared_and_does_not_retain_previous_input(forms) -> None:
    with lexical_normalizer() as normalize:
        expected = normalize(forms[0])
        assert len(expected) == 1
        for form in forms[1:]:
            assert normalize(form) == expected
        assert normalize("unrelatedword") != expected
        assert normalize(forms[0]) == expected


def test_stem_deduplication_and_safe_diagnostics(memories: MemoryStore, caplog) -> None:
    item = memories.create(MemoryCreate(content="My private preference is copper.", confirmed=True))
    with caplog.at_level(logging.INFO, logger="kat_core.memory_retrieval"):
        result = MemoryRetrieval(memories).retrieve_with_diagnostics(
            "prefer preferred preference", None
        )
    assert result.diagnostics.query_term_count == 3
    assert result.diagnostics.normalized_term_count == 1
    assert result.diagnostics.selected == ((item.id, 1),)
    assert result.diagnostics.candidate_count == 1
    assert result.diagnostics.relevance_rejected == 0
    assert item.content not in caplog.text
    assert "copper" not in caplog.text and "preferred" not in caplog.text
    assert item.id in caplog.text


def test_porter_collision_rejection_reason(memories: MemoryStore) -> None:
    memories.create(MemoryCreate(content="The universe contains distant stars.", confirmed=True))
    result = MemoryRetrieval(memories).retrieve_with_diagnostics(
        "Where is the university campus?", None
    )
    assert result.items == []
    assert result.diagnostics.candidate_count == 1
    assert result.diagnostics.relevance_rejected == 1


def test_candidate_reads_and_scoring_are_bounded(memories: MemoryStore) -> None:
    for number in range(70):
        memories.create(
            MemoryCreate(content=f"Model specimen {number}", confirmed=True, pinned=True)
        )
    result = MemoryRetrieval(memories).retrieve_with_diagnostics("Which model helps cooking?", None)
    assert result.items == []
    assert result.diagnostics.candidate_count == 50
    assert result.diagnostics.relevance_rejected == 50


def test_forget_removes_stemmed_search_artifacts(memories: MemoryStore) -> None:
    item = memories.create(
        MemoryCreate(content="Privatewordmark naming preferences", confirmed=True)
    )
    retrieval = MemoryRetrieval(memories)
    assert retrieval.retrieve("What is named?", None)
    memories.forget(item.id)
    assert retrieval.retrieve("What is named?", None) == []
    with memories.store.transaction() as db:
        assert db.execute("SELECT count(*) FROM memory_revisions").fetchone()[0] == 0
        assert (
            db.execute(
                "SELECT count(*) FROM memory_fts WHERE memory_fts MATCH 'name OR prefer'"
            ).fetchone()[0]
            == 0
        )
        assert db.execute("SELECT count(*) FROM sqlite_temp_master").fetchone()[0] == 0
        for table in ("memory_fts_data", "memory_fts_docsize", "memory_fts_idx"):
            assert "privatewordmark" not in repr(list(db.execute(f"SELECT * FROM {table}")))


def test_porter_known_limits_are_not_semantic_synonyms() -> None:
    with lexical_normalizer() as normalize:
        assert normalize("universe") == normalize("university")
        assert normalize("focus") != normalize("focused")
        assert normalize("Straße") != normalize("STRASSE")
        assert normalize("automobile") != normalize("car")


def test_owner_name_memory_in_brand_new_conversation(tmp_path: Path) -> None:
    path = tmp_path / "kat.sqlite3"
    original = Store(path)
    memory = MemoryStore(original).create(
        MemoryCreate(content="main user is named Luis", confirmed=True)
    )
    original.close()
    restarted = Store(path)
    try:
        session = restarted.create_session("New conversation")
        assert restarted.messages(session.id) == []
        memories = MemoryStore(restarted)
        assert memories.get(memory.id).content == memory.content
        results = MemoryRetrieval(memories).retrieve("What is my name?", session.project_id)
        assert [(item.id, item.revision) for item in results] == [(memory.id, 1)]
    finally:
        restarted.close()


def test_name_recall_through_actual_ollama_adapter_after_restart(config, registry, monkeypatch):
    """Synthetic HTTP protocol regression; installed CI separately tests real inference."""
    payloads = []

    def backend(request):
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["tools"]})
        body = json.loads(request.content)
        payloads.append(body)
        records = [m for m in body["messages"] if "KAT MEMORY DATA" in m.get("content", "")]
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Luis" if records else "Unknown"}},
        )

    monkeypatch.setattr(
        OllamaRuntime,
        "client",
        lambda self, timeout=60: httpx.AsyncClient(
            transport=httpx.MockTransport(backend), base_url=self.endpoint, trust_env=False
        ),
    )
    headers = {"Authorization": "Bearer " + config.api_token}
    with patch("kat_core.provider.AsyncOpenAI", side_effect=AssertionError("Cloud fallback")):
        with TestClient(
            create_app(config, registry=registry), base_url="http://127.0.0.1", headers=headers
        ) as client:
            client.put("/settings", json={"provider": "ollama", "memory_enabled": True})
            item = client.post(
                "/memories", json={"content": "main user is named Luis", "confirmed": True}
            ).json()
        with TestClient(
            create_app(config, registry=registry), base_url="http://127.0.0.1", headers=headers
        ) as client:
            for question, expected in (
                ("What is my name?", 1),
                ("What am I named?", 1),
                ("What is the weather in Oslo?", 0),
            ):
                session = client.post("/sessions", json={}).json()["id"]
                assert client.get(f"/sessions/{session}/messages").json() == []
                response = client.post(f"/sessions/{session}/messages", json={"content": question})
                assert response.status_code == 200
                assert response.json()["assistant_message"]["content"] == (
                    "Luis" if expected else "Unknown"
                )
                usage = client.get(f"/sessions/{session}/memory-usage").json()
                assert len(usage) == expected
                if expected:
                    assert (usage[0]["memory_id"], usage[0]["revision"]) == (item["id"], 1)
                messages = payloads[-1]["messages"]
                envelopes = [m for m in messages if "KAT MEMORY DATA" in m.get("content", "")]
                assert len(envelopes) == expected
                assert messages[-1]["content"] == question
                assert "Luis" not in messages[0]["content"]
                if expected:
                    assert (
                        envelopes[0]["role"] == "user"
                        and item["content"] in envelopes[0]["content"]
                    )
