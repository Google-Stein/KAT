import pytest

from kat_core.model_context import TOOL_TURN_MARKER, history
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
        {"role": "assistant", "content": TOOL_TURN_MARKER},
        {"role": "user", "content": "Open Notepad."},
    ]
    assert transcript[2].role == "tool" and "123" in transcript[2].content


def test_omitted_tool_results_do_not_consume_the_dialogue_context_budget() -> None:
    assert history(
        [
            message("assistant", "old"),
            message("user", "do"),
            message("tool", "x" * 10000),
            message("user", "new"),
        ],
        budget=8,
    ) == [
        {"role": "assistant", "content": "old"},
        {"role": "user", "content": "do"},
        {"role": "user", "content": "new"},
    ]


@pytest.mark.parametrize("approval_order", [False, True])
def test_transient_tool_turn_answers_cannot_supply_stale_inference_evidence(
    approval_order: bool,
) -> None:
    outcome = message("tool", '{"iso":"09:54","status":"completed"}')
    answer = message("assistant", "09:54; review the Notepad approval.")
    tool_turn = [answer, outcome] if approval_order else [outcome, answer]
    transcript = [
        message("user", "My name is Sam."),
        message("assistant", "Hello, Sam."),
        message("user", "Tell me the time and open Notepad."),
        *tool_turn,
        message("user", "Tell me the time and open Calculator."),
    ]
    assert history(transcript) == [
        {"role": "user", "content": "My name is Sam."},
        {"role": "assistant", "content": "Hello, Sam."},
        {"role": "user", "content": "Tell me the time and open Notepad."},
        {"role": "assistant", "content": TOOL_TURN_MARKER},
        {"role": "user", "content": "Tell me the time and open Calculator."},
    ]
    assert answer.content == "09:54; review the Notepad approval."


def test_late_approval_result_is_associated_with_its_original_owner_turn() -> None:
    original = message("user", "Read briefing.txt.").model_copy(update={"id": "original"})
    pending = message("assistant", "Please approve.").model_copy(
        update={"origin_user_message_id": original.id}
    )
    later = message("user", "What is two plus two?").model_copy(update={"id": "later"})
    answer = message("assistant", "Four.").model_copy(update={"origin_user_message_id": later.id})
    result = message("tool", "Private briefing contents.").model_copy(
        update={"origin_user_message_id": original.id}
    )
    assert history([original, pending, later, answer, result]) == [
        {"role": "user", "content": original.content},
        {"role": "assistant", "content": TOOL_TURN_MARKER},
        {"role": "user", "content": later.content},
        {"role": "assistant", "content": "Four."},
    ]


def test_continued_private_answer_stays_excluded_after_source_tool_leaves_history_window() -> None:
    private = message("assistant", "Copper Falcon; November 12.").model_copy(
        update={"transient_tool_context": True, "origin_user_message_id": "old-owner"}
    )
    transcript = [message("tool", "Private source."), private]
    transcript.extend(message("user", f"Later request {index}.") for index in range(99))
    context = history(transcript)
    assert len(context) == 100
    assert context[0] == {"role": "assistant", "content": TOOL_TURN_MARKER}
    assert "Copper Falcon" not in str(context)
    assert private.content == "Copper Falcon; November 12."
