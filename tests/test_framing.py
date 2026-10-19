"""
Unit tests for FramingEngine in algorithms.framing module.

Validates:
- TEST 1: Basic framing ('SECURITY ALERT AT GATE A5' -> 5 frames)
- TEST 2: Sequence numbers (zero-indexed, contiguous)
- TEST 3: Source node preservation across frames
- TEST 4: Destination node preservation across frames
- TEST 5: Packet ID preservation across frames
- TEST 6: Packet status updated to 'framed'
- TEST 7: Order preservation of words
- TEST 8: Single word payload handling
- TEST 9: Multiple consecutive whitespace tokenization
- TEST 10: Empty payload raises ValueError
- TEST 11: Whitespace-only payload raises ValueError
- TEST 12: Non-Packet input raises TypeError
- TEST 13: CRC default state in generated frames
- TEST 14: Retransmission count default value
- Additional ByteStuffing tests
"""

import pytest
from simulation.packet import Packet
from algorithms.framing import (
    FramingEngine,
    ByteStuffing,
    create_frame_data,
    extract_frame_data,
    FLAG,
    ESC,
)


@pytest.fixture
def framing_engine():
    """Fixture providing a fresh FramingEngine instance."""
    return FramingEngine()


def test_1_basic_framing(framing_engine):
    """TEST 1: Verify 'SECURITY ALERT AT GATE A5' produces 5 frames with expected payloads."""
    pkt = Packet(source="Security", destination="Baggage", payload="SECURITY ALERT AT GATE A5")
    frames = framing_engine.create_frames(pkt)

    assert len(frames) == 5
    assert framing_engine.get_frame_count(frames) == 5
    expected_payloads = ["SECURITY", "ALERT", "AT", "GATE", "A5"]
    assert [f.payload for f in frames] == expected_payloads


def test_2_sequence_numbers(framing_engine):
    """TEST 2: Verify frame sequence numbers start at 0 and increment sequentially."""
    pkt = Packet(source="Security", destination="Baggage", payload="SECURITY ALERT AT GATE A5")
    frames = framing_engine.create_frames(pkt)

    for i, frame in enumerate(frames):
        assert frame.sequence_number == i


def test_3_source(framing_engine):
    """TEST 3: Verify all generated frames preserve packet source."""
    pkt = Packet(source="Control Tower", destination="Check-in", payload="RUNWAY CLEARED")
    frames = framing_engine.create_frames(pkt)

    for frame in frames:
        assert frame.source == "Control Tower"


def test_4_destination(framing_engine):
    """TEST 4: Verify all generated frames preserve packet destination."""
    pkt = Packet(source="Control Tower", destination="Check-in", payload="RUNWAY CLEARED")
    frames = framing_engine.create_frames(pkt)

    for frame in frames:
        assert frame.destination == "Check-in"


def test_5_packet_id(framing_engine):
    """TEST 5: Verify all frames link back to the parent packet_id."""
    pkt = Packet(source="Security", destination="Baggage", payload="INSPECTION PASS")
    frames = framing_engine.create_frames(pkt)

    for frame in frames:
        assert frame.packet_id == pkt.packet_id


def test_6_packet_status(framing_engine):
    """TEST 6: Verify packet status transitions from 'created' to 'framed' upon framing."""
    pkt = Packet(source="Security", destination="Baggage", payload="SECURITY ALERT")
    assert pkt.status == "created"

    framing_engine.create_frames(pkt)
    assert pkt.status == "framed"


def test_7_order_preservation(framing_engine):
    """TEST 7: Verify framing preserves the exact word order."""
    pkt = Packet(source="Check-in", destination="Baggage", payload="CHECK IN BAGGAGE")
    frames = framing_engine.create_frames(pkt)

    assert [f.payload for f in frames] == ["CHECK", "IN", "BAGGAGE"]


def test_8_single_word(framing_engine):
    """TEST 8: Verify a single-word payload produces exactly one frame."""
    pkt = Packet(source="Security", destination="Emergency Services", payload="EMERGENCY")
    frames = framing_engine.create_frames(pkt)

    assert len(frames) == 1
    assert frames[0].payload == "EMERGENCY"
    assert frames[0].sequence_number == 0


def test_9_multiple_spaces(framing_engine):
    """TEST 9: Verify multiple contiguous spaces do not produce empty frames."""
    pkt = Packet(source="Security", destination="Baggage", payload="SECURITY    ALERT   GATE")
    frames = framing_engine.create_frames(pkt)

    assert len(frames) == 3
    assert [f.payload for f in frames] == ["SECURITY", "ALERT", "GATE"]


def test_10_empty_payload(framing_engine):
    """TEST 10: Verify empty payload raises ValueError."""
    pkt = Packet(source="Security", destination="Baggage", payload="TEMP")
    pkt.payload = ""

    with pytest.raises(ValueError, match="cannot be empty"):
        framing_engine.create_frames(pkt)

    assert pkt.status == "created"


def test_11_whitespace_payload(framing_engine):
    """TEST 11: Verify whitespace-only payload raises ValueError."""
    pkt = Packet(source="Security", destination="Baggage", payload="TEMP")
    pkt.payload = "     "

    with pytest.raises(ValueError, match="cannot be empty or whitespace only"):
        framing_engine.create_frames(pkt)

    assert pkt.status == "created"


def test_12_invalid_input(framing_engine):
    """TEST 12: Verify passing non-Packet object raises TypeError."""
    with pytest.raises(TypeError, match="create_frames\\(\\) expects a Packet object"):
        framing_engine.create_frames("Not A Packet")

    with pytest.raises(TypeError, match="create_frames\\(\\) expects a Packet object"):
        framing_engine.create_frames({"source": "Security", "payload": "ALERT"})


def test_13_crc_default_state(framing_engine):
    """TEST 13: Verify newly generated frames have default CRC fields."""
    pkt = Packet(source="Security", destination="Baggage", payload="DATA LINK TEST")
    frames = framing_engine.create_frames(pkt)

    for frame in frames:
        assert frame.crc is None
        assert frame.crc_status == "not_checked"


def test_14_retransmission_default(framing_engine):
    """TEST 14: Verify newly generated frames have retransmission_count initialized to 0."""
    pkt = Packet(source="Security", destination="Baggage", payload="TRANSMIT FRAME")
    frames = framing_engine.create_frames(pkt)

    for frame in frames:
        assert frame.retransmission_count == 0


def test_byte_stuffing_basic():
    """Verify byte stuffing and destuffing delimiter logic."""
    payload = "Control Tower to Security: Clear Runway 09"
    framed = ByteStuffing.stuff_bytes(payload)
    assert framed.startswith(FLAG) and framed.endswith(FLAG)
    assert ByteStuffing.destuff_bytes(framed) == payload
