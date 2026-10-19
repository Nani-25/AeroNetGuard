"""
Unit tests for Frame data model in simulation.frame module.

Validates:
1. Frame creation
2. Frame unique ID
3. Packet ID
4. Source
5. Destination
6. Payload
7. Sequence number
8. Default CRC
9. Default CRC status
10. Default frame status
11. Default retransmission count
12. set_crc()
13. set_crc_status()
14. update_status()
15. increment_retransmission()
16. to_dict()
17. Invalid packet ID
18. Invalid source
19. Invalid destination
20. Invalid sequence number
21. Invalid retransmission count
"""

import pytest
from simulation.frame import Frame


def test_1_frame_creation():
    """Test 1: Verify frame creation with valid parameters."""
    frame = Frame(
        packet_id="pkt-001",
        source="Security",
        destination="Baggage",
        payload="SECURITY",
        sequence_number=0,
    )
    assert frame is not None
    assert frame.payload == "SECURITY"


def test_2_frame_unique_id():
    """Test 2: Verify auto-generated frame IDs are unique."""
    f1 = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="F1")
    f2 = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="F2")
    assert f1.frame_id != f2.frame_id
    assert len(f1.frame_id) > 0


def test_3_packet_id():
    """Test 3: Verify packet_id is correctly assigned."""
    frame = Frame(packet_id="pkt-999", source="Security", destination="Baggage", payload="DATA")
    assert frame.packet_id == "pkt-999"


def test_4_source():
    """Test 4: Verify source node is correctly assigned."""
    frame = Frame(packet_id="pkt-1", source="Control Tower", destination="Check-in", payload="DATA")
    assert frame.source == "Control Tower"


def test_5_destination():
    """Test 5: Verify destination node is correctly assigned."""
    frame = Frame(packet_id="pkt-1", source="Control Tower", destination="Check-in", payload="DATA")
    assert frame.destination == "Check-in"


def test_6_payload():
    """Test 6: Verify payload content is preserved."""
    frame = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="ALERT")
    assert frame.payload == "ALERT"


def test_7_sequence_number():
    """Test 7: Verify sequence number is correctly set."""
    frame = Frame(
        packet_id="pkt-1",
        source="Security",
        destination="Baggage",
        payload="ALERT",
        sequence_number=3,
    )
    assert frame.sequence_number == 3


def test_8_default_crc():
    """Test 8: Verify default CRC is None."""
    frame = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA")
    assert frame.crc is None


def test_9_default_crc_status():
    """Test 9: Verify default CRC status is 'not_checked'."""
    frame = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA")
    assert frame.crc_status == "not_checked"


def test_10_default_frame_status():
    """Test 10: Verify default frame status is 'created'."""
    frame = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA")
    assert frame.status == "created"


def test_11_default_retransmission_count():
    """Test 11: Verify default retransmission count is 0."""
    frame = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA")
    assert frame.retransmission_count == 0


def test_12_set_crc():
    """Test 12: Verify set_crc stores the CRC value."""
    frame = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA")
    frame.set_crc("0x4A2B")
    assert frame.crc == "0x4A2B"


def test_13_set_crc_status():
    """Test 13: Verify set_crc_status updates status and validates valid states."""
    frame = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA")
    frame.set_crc_status("valid")
    assert frame.crc_status == "valid"

    frame.set_crc_status("invalid")
    assert frame.crc_status == "invalid"

    with pytest.raises(ValueError):
        frame.set_crc_status("corrupted_state")


def test_14_update_status():
    """Test 14: Verify update_status updates frame state and rejects empty strings."""
    frame = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA")
    frame.update_status("transmitted")
    assert frame.status == "transmitted"

    frame.update_status("acked")
    assert frame.status == "acked"

    with pytest.raises(ValueError):
        frame.update_status("")


def test_15_increment_retransmission():
    """Test 15: Verify increment_retransmission increases counter by 1."""
    frame = Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA")
    assert frame.retransmission_count == 0
    cnt1 = frame.increment_retransmission()
    assert cnt1 == 1
    assert frame.retransmission_count == 1
    cnt2 = frame.increment_retransmission()
    assert cnt2 == 2
    assert frame.retransmission_count == 2


def test_16_to_dict():
    """Test 16: Verify to_dict returns a complete JSON-friendly dictionary."""
    frame = Frame(
        packet_id="pkt-42",
        source="Security",
        destination="Baggage",
        payload="SECURITY",
        sequence_number=2,
    )
    frame.set_crc("0xABCD")
    frame.set_crc_status("valid")
    frame.update_status("transmitted")
    frame.increment_retransmission()

    data = frame.to_dict()
    assert data["frame_id"] == frame.frame_id
    assert data["packet_id"] == "pkt-42"
    assert data["sequence_number"] == 2
    assert data["payload"] == "SECURITY"
    assert data["source"] == "Security"
    assert data["destination"] == "Baggage"
    assert data["crc"] == "0xABCD"
    assert data["crc_status"] == "valid"
    assert data["status"] == "transmitted"
    assert data["retransmission_count"] == 1


def test_17_invalid_packet_id():
    """Test 17: Verify empty packet_id raises ValueError."""
    with pytest.raises(ValueError, match="packet_id cannot be empty"):
        Frame(packet_id="", source="Security", destination="Baggage", payload="DATA")

    with pytest.raises(ValueError, match="packet_id cannot be empty"):
        Frame(packet_id="   ", source="Security", destination="Baggage", payload="DATA")


def test_18_invalid_source():
    """Test 18: Verify empty source raises ValueError."""
    with pytest.raises(ValueError, match="source cannot be empty"):
        Frame(packet_id="pkt-1", source="", destination="Baggage", payload="DATA")

    with pytest.raises(ValueError, match="source cannot be empty"):
        Frame(packet_id="pkt-1", source="   ", destination="Baggage", payload="DATA")


def test_19_invalid_destination():
    """Test 19: Verify empty destination raises ValueError."""
    with pytest.raises(ValueError, match="destination cannot be empty"):
        Frame(packet_id="pkt-1", source="Security", destination="", payload="DATA")

    with pytest.raises(ValueError, match="destination cannot be empty"):
        Frame(packet_id="pkt-1", source="Security", destination="  ", payload="DATA")


def test_20_invalid_sequence_number():
    """Test 20: Verify non-integer or negative sequence number raises appropriate error."""
    with pytest.raises(TypeError, match="sequence_number must be an integer"):
        Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA", sequence_number="0")

    with pytest.raises(ValueError, match="sequence_number cannot be negative"):
        Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA", sequence_number=-1)


def test_21_invalid_retransmission_count():
    """Test 21: Verify non-integer or negative retransmission count raises appropriate error."""
    with pytest.raises(TypeError, match="retransmission_count must be an integer"):
        Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA", retransmission_count="0")

    with pytest.raises(ValueError, match="retransmission_count cannot be negative"):
        Frame(packet_id="pkt-1", source="Security", destination="Baggage", payload="DATA", retransmission_count=-2)
