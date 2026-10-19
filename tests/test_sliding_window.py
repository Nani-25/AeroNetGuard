"""
Unit tests for SlidingWindow in algorithms.sliding_window module.

Validates:
- TEST 1: Initial window with window size 3
- TEST 2: Initial window with window size 2
- TEST 3: Initial window with window size 1
- TEST 4: send_window transmits frames without auto-ACK
- TEST 5: ACK first frame advances window by 1
- TEST 6: ACK multiple frames advances window contiguously
- TEST 7: is_complete returns True when all frames are acknowledged
- TEST 8: get_unacknowledged_frames returns transmitted but unacked frames
- TEST 9: Out-of-order ACK does not jump the window base
- TEST 10: Duplicate ACKs do not corrupt window state
- TEST 11: Invalid window sizes (0, negative) raise ValueError
- TEST 12: Invalid frames parameter raises TypeError
- TEST 13: Acknowledging non-existent sequence numbers raises ValueError
- TEST 14: get_window_state returns valid state dictionary
"""

import pytest
from simulation.frame import Frame
from algorithms.sliding_window import SlidingWindow


@pytest.fixture
def five_frames():
    """Fixture providing 5 Frame objects (F0 to F4)."""
    return [
        Frame(
            packet_id="pkt-demo",
            source="Security",
            destination="Baggage",
            payload=f"WORD_{i}",
            sequence_number=i,
        )
        for i in range(5)
    ]


def test_1_initial_window(five_frames):
    """TEST 1: Window size 3 yields initial window [F0, F1, F2]."""
    sw = SlidingWindow(five_frames, window_size=3)
    curr = sw.get_current_window()
    assert len(curr) == 3
    assert [f.sequence_number for f in curr] == [0, 1, 2]
    assert sw.get_base() == 0


def test_2_window_size_2(five_frames):
    """TEST 2: Window size 2 yields initial window [F0, F1]."""
    sw = SlidingWindow(five_frames, window_size=2)
    curr = sw.get_current_window()
    assert len(curr) == 2
    assert [f.sequence_number for f in curr] == [0, 1]


def test_3_window_size_1(five_frames):
    """TEST 3: Window size 1 yields initial window [F0]."""
    sw = SlidingWindow(five_frames, window_size=1)
    curr = sw.get_current_window()
    assert len(curr) == 1
    assert [f.sequence_number for f in curr] == [0]


def test_4_send_window(five_frames):
    """TEST 4: send_window transmits frames without auto-ACK."""
    sw = SlidingWindow(five_frames, window_size=3)
    sent = sw.send_window()

    assert len(sent) == 3
    assert [f.sequence_number for f in sent] == [0, 1, 2]
    for f in sent:
        assert f.status == "transmitted"

    # No frames should be acknowledged yet
    assert len(sw.acknowledged_frames) == 0
    assert sw.is_complete() is False


def test_5_ack_first_frame(five_frames):
    """TEST 5: Acknowledging F0 advances window from [F0, F1, F2] to [F1, F2, F3]."""
    sw = SlidingWindow(five_frames, window_size=3)
    sw.send_window()

    sw.acknowledge(0)
    assert sw.get_base() == 1
    curr = sw.get_current_window()
    assert [f.sequence_number for f in curr] == [1, 2, 3]


def test_6_ack_multiple_frames(five_frames):
    """TEST 6: Acknowledging F0, F1, F2 advances window to [F3, F4]."""
    sw = SlidingWindow(five_frames, window_size=3)
    sw.send_window()

    sw.acknowledge(0)
    sw.acknowledge(1)
    sw.acknowledge(2)

    assert sw.get_base() == 3
    curr = sw.get_current_window()
    assert [f.sequence_number for f in curr] == [3, 4]


def test_7_completion(five_frames):
    """TEST 7: Acknowledging all frames marks transmission as complete."""
    sw = SlidingWindow(five_frames, window_size=3)
    assert sw.is_complete() is False

    for i in range(5):
        sw.send_window()
        sw.acknowledge(i)

    assert sw.is_complete() is True
    assert sw.get_current_window() == []


def test_8_unacknowledged_frames(five_frames):
    """TEST 8: Transmit F0..F2, ACK F0 -> unacknowledged frames are F1, F2."""
    sw = SlidingWindow(five_frames, window_size=3)
    sw.send_window()
    sw.acknowledge(0)

    unacked = sw.get_unacknowledged_frames()
    assert len(unacked) == 2
    assert [f.sequence_number for f in unacked] == [1, 2]


def test_9_out_of_order_ack(five_frames):
    """TEST 9: Receiving ACK F2 before F0 does not jump the window base."""
    sw = SlidingWindow(five_frames, window_size=3)
    sw.send_window()

    # Out of order arrival: ACK 2 arrives first
    sw.acknowledge(2)
    assert sw.get_base() == 0  # base must remain at 0 until 0 and 1 are acked
    assert [f.sequence_number for f in sw.get_current_window()] == [0, 1, 2]

    # When 0 arrives, base advances to 1
    sw.acknowledge(0)
    assert sw.get_base() == 1

    # When 1 arrives, base advances past 1 and 2 to 3
    sw.acknowledge(1)
    assert sw.get_base() == 3


def test_10_duplicate_ack(five_frames):
    """TEST 10: Duplicate ACKs do not corrupt window state."""
    sw = SlidingWindow(five_frames, window_size=3)
    sw.send_window()

    sw.acknowledge(0)
    assert sw.get_base() == 1

    # Duplicate ACK for F0
    sw.acknowledge(0)
    assert sw.get_base() == 1
    assert [f.sequence_number for f in sw.get_current_window()] == [1, 2, 3]


def test_11_invalid_window_size(five_frames):
    """TEST 11: Window size <= 0 raises ValueError."""
    with pytest.raises(ValueError, match="window_size must be greater than zero"):
        SlidingWindow(five_frames, window_size=0)

    with pytest.raises(ValueError, match="window_size must be greater than zero"):
        SlidingWindow(five_frames, window_size=-3)

    with pytest.raises(TypeError, match="window_size must be an integer"):
        SlidingWindow(five_frames, window_size="3")


def test_12_invalid_frames():
    """TEST 12: Invalid frames input raises TypeError."""
    with pytest.raises(TypeError, match="frames must be a list"):
        SlidingWindow("not_a_list", window_size=3)

    with pytest.raises(TypeError, match="not an instance of Frame"):
        SlidingWindow(["not_a_frame_object"], window_size=3)


def test_13_invalid_ack(five_frames):
    """TEST 13: Acknowledging non-existent sequence number raises ValueError."""
    sw = SlidingWindow(five_frames, window_size=3)
    with pytest.raises(ValueError, match="non-existent sequence number"):
        sw.acknowledge(999)


def test_14_window_state_dict(five_frames):
    """TEST 14: get_window_state returns complete, accurate dictionary."""
    sw = SlidingWindow(five_frames, window_size=3)
    sw.send_window()
    sw.acknowledge(0)

    state = sw.get_window_state()
    assert state["base"] == 1
    assert state["window_size"] == 3
    assert state["current_window"] == [1, 2, 3]
    assert state["acknowledged_frames"] == [0]
    assert state["unacknowledged_frames"] == [1, 2]
