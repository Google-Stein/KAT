import pytest

from kat_core.model_context import history
from kat_core.schemas import Message


def message(role: str, content: str) -> Message:
    return Message.model_validate(
        {
            "id": "message",
            "session_id": "session",
            "role": role,
            "content": content,
            "created_at": "then",
        }
    )


@pytest.mark.parametrize("status", ["completed", "failed", "denied", "interrupted"])
def test_historical_outcomes_are_excluded_without_mutating_persisted_messages(status: str) -> None:
    transcript = [
        message("user", "Open Notepad."),
        message("assistant", "Review the approval."),
        message("tool", '{"status":"' + status + '","pid":123}'),
        message("user", "Open Notepad."),
    ]
    context = history(transcript)
    assert context == [
        {"role": "user", "content": "Open Notepad."},
        {"role": "assistant", "content": "Review the approval."},
        {"role": "user", "content": "Open Notepad."},
    ]
    assert transcript[2].role == "tool" and "123" in transcript[2].content


def test_omitted_tool_results_do_not_consume_the_dialogue_context_budget() -> None:
    assert history(
        [message("assistant", "old"), message("tool", "x" * 10000), message("user", "new")],
        budget=6,
    ) == [{"role": "assistant", "content": "old"}, {"role": "user", "content": "new"}]
