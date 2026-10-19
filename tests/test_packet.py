"""
Unit tests for Packet data model in simulation.packet module.

Validates:
1. Packet creation
2. Packet unique ID
3. Source
4. Destination
5. Payload
6. Default sequence number
7. Default route
8. Default status
9. set_route()
10. update_status()
11. to_dict()
12. Invalid empty source
13. Invalid empty destination
14. Invalid payload type
15. Invalid sequence number
16. Negative sequence number
"""

import pytest
from simulation.packet import Packet


def test_1_packet_creation():
    """Test 1: Verify packet can be created with required parameters."""
    pkt = Packet(source="Security", destination="Baggage", payload="TEST ALERT")
    assert pkt is not None
    assert pkt.payload == "TEST ALERT"


def test_2_packet_unique_id():
    """Test 2: Verify automatically generated packet_ids are unique."""
    pkt1 = Packet(source="Security", destination="Baggage", payload="ALERT 1")
    pkt2 = Packet(source="Security", destination="Baggage", payload="ALERT 2")
    assert pkt1.packet_id != pkt2.packet_id
    assert len(pkt1.packet_id) > 0


def test_3_source():
    """Test 3: Verify source node is correctly assigned."""
    pkt = Packet(source="Control Tower", destination="Check-in", payload="DATA")
    assert pkt.source == "Control Tower"


def test_4_destination():
    """Test 4: Verify destination node is correctly assigned."""
    pkt = Packet(source="Control Tower", destination="Check-in", payload="DATA")
    assert pkt.destination == "Check-in"


def test_5_payload():
    """Test 5: Verify payload content is preserved."""
    message = "SECURITY ALERT AT GATE A5"
    pkt = Packet(source="Security", destination="Baggage", payload=message)
    assert pkt.payload == message


def test_6_default_sequence_number():
    """Test 6: Verify default sequence number is 0."""
    pkt = Packet(source="Security", destination="Baggage", payload="DATA")
    assert pkt.sequence_number == 0


def test_7_default_route():
    """Test 7: Verify default route is an empty list."""
    pkt = Packet(source="Security", destination="Baggage", payload="DATA")
    assert pkt.route == []


def test_8_default_status():
    """Test 8: Verify default status is 'created'."""
    pkt = Packet(source="Security", destination="Baggage", payload="DATA")
    assert pkt.status == "created"


def test_9_set_route():
    """Test 9: Verify set_route assigns route list and validates types."""
    pkt = Packet(source="Security", destination="Baggage", payload="DATA")
    route = ["Security", "Control Tower", "Check-in", "Baggage"]
    pkt.set_route(route)
    assert pkt.route == route

    with pytest.raises(TypeError):
        pkt.set_route("invalid_route_type")


def test_10_update_status():
    """Test 10: Verify update_status updates packet status and rejects empty strings."""
    pkt = Packet(source="Security", destination="Baggage", payload="DATA")
    pkt.update_status("transmitting")
    assert pkt.status == "transmitting"

    pkt.update_status("delivered")
    assert pkt.status == "delivered"

    with pytest.raises(ValueError):
        pkt.update_status("")


def test_11_to_dict():
    """Test 11: Verify to_dict returns a valid JSON-friendly dictionary."""
    pkt = Packet(
        source="Security",
        destination="Baggage",
        payload="SECURITY ALERT",
        sequence_number=1,
    )
    pkt.set_route(["Security", "Emergency Services", "Baggage"])
    pkt.update_status("framed")

    data = pkt.to_dict()
    assert data["packet_id"] == pkt.packet_id
    assert data["source"] == "Security"
    assert data["destination"] == "Baggage"
    assert data["payload"] == "SECURITY ALERT"
    assert data["sequence_number"] == 1
    assert data["route"] == ["Security", "Emergency Services", "Baggage"]
    assert data["status"] == "framed"


def test_12_invalid_empty_source():
    """Test 12: Verify empty source raises ValueError."""
    with pytest.raises(ValueError, match="source cannot be empty"):
        Packet(source="", destination="Baggage", payload="ALERT")

    with pytest.raises(ValueError, match="source cannot be empty"):
        Packet(source="   ", destination="Baggage", payload="ALERT")


def test_13_invalid_empty_destination():
    """Test 13: Verify empty destination raises ValueError."""
    with pytest.raises(ValueError, match="destination cannot be empty"):
        Packet(source="Security", destination="", payload="ALERT")

    with pytest.raises(ValueError, match="destination cannot be empty"):
        Packet(source="Security", destination="   ", payload="ALERT")


def test_14_invalid_payload_type():
    """Test 14: Verify non-string payload raises TypeError."""
    with pytest.raises(TypeError, match="payload must be a string"):
        Packet(source="Security", destination="Baggage", payload=12345)

    with pytest.raises(TypeError, match="payload must be a string"):
        Packet(source="Security", destination="Baggage", payload={"msg": "ALERT"})


def test_15_invalid_sequence_number():
    """Test 15: Verify non-integer sequence number raises TypeError."""
    with pytest.raises(TypeError, match="sequence_number must be an integer"):
        Packet(source="Security", destination="Baggage", payload="ALERT", sequence_number="0")

    with pytest.raises(TypeError, match="sequence_number must be an integer"):
        Packet(source="Security", destination="Baggage", payload="ALERT", sequence_number=1.5)


def test_16_negative_sequence_number():
    """Test 16: Verify negative sequence number raises ValueError."""
    with pytest.raises(ValueError, match="sequence_number cannot be negative"):
        Packet(source="Security", destination="Baggage", payload="ALERT", sequence_number=-1)
