import pytest

from agent.state import RunState


def test_max_iterations_is_enforced():
    state = RunState(1, "objectif")
    for _ in range(10):
        state.next_iteration(10)
    with pytest.raises(RuntimeError, match="MAX_ITERATIONS=10"):
        state.next_iteration(10)


def test_max_retries_is_enforced():
    state = RunState(1, "objectif")
    for _ in range(3):
        state.next_retry(3)
    with pytest.raises(RuntimeError, match="MAX_RETRIES_PER_TASK=3"):
        state.next_retry(3)
