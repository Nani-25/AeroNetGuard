"""
Test suite for NetworkSimulator in simulation.network_simulator module.

Validates:
1. Simulator initialization
2. Successful basic simulation
3. Routing integration
4. Packet creation
5. Framing integration
6. CRC calculation
7. Successful CRC verification
8. Go-Back-N integration
9. No-failure transmission
10. Failure simulation
11. Retransmission
12. Final successful delivery
13. Event log
14. Result structure
15. Metrics
16. Invalid source
17. Invalid destination
18. Empty/non-string message
19. Invalid window size
20. Control Tower cannot be destination
21. Reset functionality
22. get_state()
23. Requirement 1: Source is always Control Tower
24. Requirement 2: Control Tower -> Check-in works (Cost: 2, Hops: 1)
25. Requirement 3: Control Tower -> Security works (Cost: 3, Hops: 1)
26. Requirement 4: Control Tower -> Baggage works (Cost: 4, Hops: 2)
27. Requirement 5: Control Tower -> Emergency Services works (Cost: 5, Hops: 2)
28. Requirement 6: Security as source is rejected
29. Requirement 7: Baggage as source is rejected
30. Requirement 8: Check-in as source is rejected
31. Requirement 9: Emergency Services as source is rejected
32. Requirement 10: Control Tower cannot be selected as destination
33. Failure sequence validation
34. Backward compatibility legacy tests (impairment generator, run_simulation)
"""

import pytest
from simulation.network import (
    AirportNetwork,
    NODE_CONTROL_TOWER,
    NODE_SECURITY,
    NODE_BAGGAGE,
    NODE_CHECK_IN,
    NODE_EMERGENCY_SERVICES,
)
from simulation.dijkstra import DijkstraRouter
from simulation.network_simulator import NetworkSimulator
from simulation.error_generator import NetworkImpairmentGenerator
from simulation.frame import Frame


# --- Unit Tests ---

def test_1_simulator_initialization():
    """TEST 1: Simulator initializes network, router, crc_processor, and state."""
    sim = NetworkSimulator()
    assert isinstance(sim.network, AirportNetwork)
    assert isinstance(sim.router, DijkstraRouter)
    assert sim.state == "initialized"
    assert sim.events == []
    assert sim.packet is None
    assert sim.frames == []
    assert sim.result is None


def test_2_successful_basic_simulation():
    """TEST 2: Basic end-to-end simulation delivers successfully."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_CHECK_IN,
        message="SCHEDULE UPDATE",
        window_size=2,
    )
    assert result["status"] == "delivered"
    assert result["delivery_successful"] is True
    assert result["total_frames"] == 2
    assert result["retransmission_count"] == 0


def test_3_routing_integration():
    """TEST 3: Routing correctly uses DijkstraRouter shortest paths from Control Tower."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_EMERGENCY_SERVICES,
        message="MEDICAL ESCORT REQUEST",
        window_size=3,
    )
    expected_path = [NODE_CONTROL_TOWER, NODE_SECURITY, NODE_EMERGENCY_SERVICES]
    assert result["route"] == expected_path
    assert result["route_cost"] == 5
    assert result["hop_count"] == 2


def test_4_packet_creation():
    """TEST 4: Packet is properly created, routed, and delivered."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_SECURITY,
        message="ALL CLEAR",
        window_size=2,
    )
    assert sim.packet is not None
    assert sim.packet.source == NODE_CONTROL_TOWER
    assert sim.packet.destination == NODE_SECURITY
    assert sim.packet.payload == "ALL CLEAR"
    assert sim.packet.status == "delivered"
    assert sim.packet.route == [NODE_CONTROL_TOWER, NODE_SECURITY]


def test_5_framing_integration():
    """TEST 5: FramingEngine splits payload into ordered, sequential frames."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_CHECK_IN,
        message="GATE FOUR READY",
        window_size=3,
    )
    assert result["total_frames"] == 3
    frames = result["frames"]
    assert len(frames) == 3
    assert frames[0]["payload"] == "GATE"
    assert frames[0]["sequence_number"] == 0
    assert frames[1]["payload"] == "FOUR"
    assert frames[1]["sequence_number"] == 1
    assert frames[2]["payload"] == "READY"
    assert frames[2]["sequence_number"] == 2


def test_6_crc_calculation():
    """TEST 6: CRC-8 is calculated for every frame and stored."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_BAGGAGE,
        message="SCAN PASS",
        window_size=2,
    )
    for f in result["frames"]:
        assert f["crc"] is not None
        assert isinstance(f["crc"], int)
        assert 0 <= f["crc"] <= 255


def test_7_successful_crc_verification():
    """TEST 7: CRC verification validates each delivered frame."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_BAGGAGE,
        message="SCAN PASS",
        window_size=2,
    )
    for f in result["frames"]:
        assert f["crc_status"] == "valid"

    crc_events = [e for e in result["events"] if e.get("event") == "crc_verification"]
    assert len(crc_events) == 2
    assert all(e["is_valid"] is True for e in crc_events)


def test_8_go_back_n_integration():
    """TEST 8: Go-Back-N protocol manages cumulative ACKs across window."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_BAGGAGE,
        message="A B C D E",
        window_size=3,
    )
    assert result["delivery_successful"] is True
    ack_events = [e for e in result["events"] if e.get("event") == "acknowledgement"]
    assert len(ack_events) == 5
    ack_seqs = [e["sequence_number"] for e in ack_events]
    assert ack_seqs == [0, 1, 2, 3, 4]


def test_9_no_failure_transmission():
    """TEST 9: Clean transmission without failures requires zero retransmissions."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_CHECK_IN,
        message="NORMAL TRAFFIC FLOW",
        window_size=3,
        failure_sequence=None,
    )
    assert result["retransmission_count"] == 0
    assert result["failed_frames"] == 0
    assert result["retransmitted_frames"] == 0


def test_10_failure_simulation():
    """TEST 10: Designated failure_sequence triggers simulated failure."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_BAGGAGE,
        message="ALPHA BRAVO CHARLIE DELTA",
        window_size=2,
        failure_sequence=[1],
    )
    failure_events = [e for e in result["events"] if e.get("event") == "failure"]
    assert len(failure_events) == 1
    assert failure_events[0]["sequence_number"] == 1
    assert result["delivery_successful"] is True


def test_11_retransmission():
    """TEST 11: Retransmissions occur upon failure and recover window."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_BAGGAGE,
        message="ALPHA BRAVO CHARLIE DELTA",
        window_size=3,
        failure_sequence=[1],
    )
    assert result["retransmission_count"] > 0
    retrans_events = [e for e in result["events"] if e.get("event") == "retransmission"]
    assert len(retrans_events) > 0
    assert any(e["sequence_number"] == 1 for e in retrans_events)


def test_12_final_successful_delivery():
    """TEST 12: Normal simulation terminates with state 'delivered'."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_SECURITY,
        message="STANDBY",
        window_size=1,
    )
    assert result["status"] == "delivered"
    assert sim.state == "delivered"
    delivery_events = [e for e in result["events"] if e.get("event") == "delivery"]
    assert len(delivery_events) == 1


def test_13_event_log():
    """TEST 13: Event log records all lifecycle stages in execution order."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_SECURITY,
        message="MSG ONE TWO",
        window_size=3,
    )
    events = result["events"]
    event_names = [e["event"] for e in events]

    assert "routing" in event_names
    assert "packet_created" in event_names
    assert "frame_created" in event_names
    assert "crc_calculated" in event_names
    assert "transmission" in event_names
    assert "crc_verification" in event_names
    assert "acknowledgement" in event_names
    assert "delivery" in event_names


def test_14_result_structure():
    """TEST 14: Result dictionary matches specified JSON schema."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_BAGGAGE,
        message="TEST MSG",
        window_size=2,
    )
    required_keys = [
        "status",
        "source",
        "destination",
        "message",
        "route",
        "route_cost",
        "hop_count",
        "packet_id",
        "total_frames",
        "window_size",
        "frames",
        "events",
        "retransmission_count",
        "delivery_successful",
    ]
    for key in required_keys:
        assert key in result, f"Key '{key}' missing from result."


def test_15_metrics():
    """TEST 15: Basic simulation metrics are accurately computed."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_BAGGAGE,
        message="A B C",
        window_size=3,
        failure_sequence=[1],
    )
    metrics = result["metrics"]
    assert metrics["total_frames"] == 3
    assert metrics["successful_frames"] == 3
    assert metrics["failed_frames"] == 1
    assert metrics["retransmitted_frames"] > 0
    assert metrics["retransmission_count"] >= 1
    assert metrics["delivery_successful"] is True


def test_16_invalid_source():
    """TEST 16: Unknown or non-Control Tower source node raises ValueError."""
    sim = NetworkSimulator()
    with pytest.raises(ValueError, match="Invalid source node. Source must be Control Tower."):
        sim.simulate(source="Invalid Airport", destination=NODE_BAGGAGE, message="MSG")

    with pytest.raises(ValueError, match="non-empty string"):
        sim.simulate(source="", destination=NODE_BAGGAGE, message="MSG")


def test_17_invalid_destination():
    """TEST 17: Control Tower as destination, unknown or empty destination node raises ValueError."""
    sim = NetworkSimulator()
    with pytest.raises(ValueError, match="Destination cannot be Control Tower."):
        sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_CONTROL_TOWER, message="MSG")

    with pytest.raises(ValueError, match="does not exist"):
        sim.simulate(source=NODE_CONTROL_TOWER, destination="Ghost Terminal", message="MSG")

    with pytest.raises(ValueError, match="non-empty string"):
        sim.simulate(source=NODE_CONTROL_TOWER, destination="", message="MSG")


def test_18_empty_message():
    """TEST 18: Empty, whitespace-only, or non-string message raises exception."""
    sim = NetworkSimulator()
    with pytest.raises(ValueError, match="empty"):
        sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_BAGGAGE, message="")

    with pytest.raises(ValueError, match="empty"):
        sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_BAGGAGE, message="   ")

    with pytest.raises(TypeError, match="must be a string"):
        sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_BAGGAGE, message=12345)


def test_19_invalid_window_size():
    """TEST 19: Non-positive, non-integer, or oversized window raises exception."""
    sim = NetworkSimulator()
    with pytest.raises(ValueError, match="positive integer"):
        sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_BAGGAGE, message="TEST", window_size=0)

    with pytest.raises(ValueError, match="positive integer"):
        sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_BAGGAGE, message="TEST", window_size=-2)

    with pytest.raises(TypeError, match="must be an integer"):
        sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_BAGGAGE, message="TEST", window_size="3")

    with pytest.raises(ValueError, match="cannot exceed total frames"):
        sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_BAGGAGE, message="ONE TWO", window_size=5)


def test_20_control_tower_cannot_be_destination():
    """TEST 20: Control Tower as destination is forbidden even when requested as source."""
    sim = NetworkSimulator()
    with pytest.raises(ValueError, match="Destination cannot be Control Tower."):
        sim.simulate(
            source=NODE_CONTROL_TOWER,
            destination=NODE_CONTROL_TOWER,
            message="LOOPBACK ATTEMPT",
            window_size=3,
        )


def test_21_reset():
    """TEST 21: reset() restores initial state without rebuilding graph."""
    sim = NetworkSimulator()
    sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_CHECK_IN, message="TEST MSG", window_size=2)
    assert sim.state == "delivered"
    assert len(sim.events) > 0

    sim.reset()
    assert sim.state == "initialized"
    assert sim.events == []
    assert sim.packet is None
    assert sim.frames == []
    assert sim.result is None


def test_22_get_state():
    """TEST 22: get_state() provides JSON-friendly snapshot before and after run."""
    sim = NetworkSimulator()
    state_init = sim.get_state()
    assert state_init["state"] == "initialized"
    assert state_init["total_frames"] == 0
    assert state_init["events"] == []

    sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_CHECK_IN, message="HI", window_size=1)
    state_after = sim.get_state()
    assert state_after["state"] == "delivered"
    assert state_after["source"] == NODE_CONTROL_TOWER
    assert state_after["destination"] == NODE_CHECK_IN
    assert state_after["total_frames"] == 1
    assert len(state_after["events"]) > 0


# --- Step 15 Requirements 1-10 Tests ---

def test_23_source_always_control_tower():
    """Requirement 1: Source is always Control Tower."""
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_SECURITY,
        message="TELEMETRY PACKET",
        window_size=2,
    )
    assert result["source"] == "Control Tower"
    assert result["route"][0] == "Control Tower"


def test_24_control_tower_to_checkin():
    """
    Requirement 2: Control Tower -> Check-in works.
    Expected: Control Tower -> Check-in
    Cost: 2
    Hops: 1
    """
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_CHECK_IN,
        message="PASSENGER MANIFEST",
        window_size=2,
    )
    assert result["route"] == ["Control Tower", "Check-in"]
    assert result["route_cost"] == 2
    assert result["hop_count"] == 1
    assert result["delivery_successful"] is True


def test_25_control_tower_to_security():
    """
    Requirement 3: Control Tower -> Security works.
    Expected: Control Tower -> Security
    Cost: 3
    Hops: 1
    """
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_SECURITY,
        message="CLEAR CHECKPOINT",
        window_size=2,
    )
    assert result["route"] == ["Control Tower", "Security"]
    assert result["route_cost"] == 3
    assert result["hop_count"] == 1
    assert result["delivery_successful"] is True


def test_26_control_tower_to_baggage():
    """
    Requirement 4: Control Tower -> Baggage works.
    Expected: Control Tower -> Check-in -> Baggage
    Cost: 4
    Hops: 2
    """
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_BAGGAGE,
        message="CONVEYOR BELT ACTIVE",
        window_size=3,
    )
    assert result["route"] == ["Control Tower", "Check-in", "Baggage"]
    assert result["route_cost"] == 4
    assert result["hop_count"] == 2
    assert result["delivery_successful"] is True


def test_27_control_tower_to_emergency_services():
    """
    Requirement 5: Control Tower -> Emergency Services works.
    Expected: Control Tower -> Security -> Emergency Services
    Cost: 5
    Hops: 2
    """
    sim = NetworkSimulator()
    result = sim.simulate(
        source=NODE_CONTROL_TOWER,
        destination=NODE_EMERGENCY_SERVICES,
        message="DISPATCH CRASH CREW",
        window_size=3,
    )
    assert result["route"] == ["Control Tower", "Security", "Emergency Services"]
    assert result["route_cost"] == 5
    assert result["hop_count"] == 2
    assert result["delivery_successful"] is True


def test_28_security_as_source_rejected():
    """Requirement 6: Security as source is rejected."""
    sim = NetworkSimulator()
    with pytest.raises(ValueError, match="Invalid source node. Source must be Control Tower."):
        sim.simulate(source=NODE_SECURITY, destination=NODE_BAGGAGE, message="UNAUTHORIZED SOURCE")


def test_29_baggage_as_source_rejected():
    """Requirement 7: Baggage as source is rejected."""
    sim = NetworkSimulator()
    with pytest.raises(ValueError, match="Invalid source node. Source must be Control Tower."):
        sim.simulate(source=NODE_BAGGAGE, destination=NODE_SECURITY, message="UNAUTHORIZED SOURCE")


def test_30_checkin_as_source_rejected():
    """Requirement 8: Check-in as source is rejected."""
    sim = NetworkSimulator()
    with pytest.raises(ValueError, match="Invalid source node. Source must be Control Tower."):
        sim.simulate(source=NODE_CHECK_IN, destination=NODE_EMERGENCY_SERVICES, message="UNAUTHORIZED SOURCE")


def test_31_emergency_services_as_source_rejected():
    """Requirement 9: Emergency Services as source is rejected."""
    sim = NetworkSimulator()
    with pytest.raises(ValueError, match="Invalid source node. Source must be Control Tower."):
        sim.simulate(source=NODE_EMERGENCY_SERVICES, destination=NODE_SECURITY, message="UNAUTHORIZED SOURCE")


def test_32_control_tower_cannot_be_destination():
    """Requirement 10: Control Tower cannot be selected as destination."""
    sim = NetworkSimulator()
    with pytest.raises(ValueError, match="Invalid destination node. Destination cannot be Control Tower."):
        sim.simulate(source=NODE_CONTROL_TOWER, destination=NODE_CONTROL_TOWER, message="UNAUTHORIZED DESTINATION")


def test_33_failure_sequence_validation():
    """TEST 33: Invalid failure sequence inputs raise exceptions."""
    sim = NetworkSimulator()
    # Non-list failure sequence
    with pytest.raises(TypeError, match="must be a list of integers"):
        sim.simulate(NODE_CONTROL_TOWER, NODE_BAGGAGE, "HELLO WORLD", window_size=2, failure_sequence="2")

    # Sequence number out of range
    with pytest.raises(ValueError, match="outside frame range"):
        sim.simulate(NODE_CONTROL_TOWER, NODE_BAGGAGE, "HELLO WORLD", window_size=2, failure_sequence=[99])

    # Negative sequence number
    with pytest.raises(ValueError, match="cannot be negative"):
        sim.simulate(NODE_CONTROL_TOWER, NODE_BAGGAGE, "HELLO WORLD", window_size=2, failure_sequence=[-1])


# --- Backward Compatibility Legacy Tests ---

def test_impairment_generator():
    """Legacy test for NetworkImpairmentGenerator."""
    imp = NetworkImpairmentGenerator(loss_rate=1.0, corruption_rate=1.0, seed=123)
    assert imp.should_drop() is True
    assert imp.should_corrupt() is True

    f = Frame(packet_id="p1", source="A", destination="B", payload="Clean Data")
    corrupted_f = imp.corrupt_frame(f)
    assert corrupted_f.payload != "Clean Data"
    assert corrupted_f.status == "corrupted"


def test_simulator_ideal_transmission():
    """Legacy test for NetworkSimulator.run_simulation."""
    sim = NetworkSimulator()
    result = sim.run_simulation(
        source=NODE_CONTROL_TOWER,
        destination=NODE_BAGGAGE,
        payloads=["Baggage Manifest Item 1", "Baggage Manifest Item 2"],
        window_size=4,
        loss_rate=0.0,
        corruption_rate=0.0,
    )

    assert result["source"] == NODE_CONTROL_TOWER
    assert result["destination"] == NODE_BAGGAGE
    assert result["total_frames_delivered"] == 2
    assert result["packet_delivery_ratio"] == 100.0
    assert result["total_retransmissions"] == 0
    assert len(result["event_logs"]) > 0


def test_simulator_with_packet_loss_recovery():
    """Legacy test for NetworkSimulator.run_simulation with packet loss."""
    sim = NetworkSimulator()
    result = sim.run_simulation(
        source=NODE_CONTROL_TOWER,
        destination=NODE_SECURITY,
        payloads=["Alert Msg 1", "Alert Msg 2"],
        window_size=2,
        loss_rate=0.2,
        corruption_rate=0.0,
        seed=42,
    )

    assert result["total_frames_delivered"] == 2
    assert result["total_steps"] > 0
    assert any(log["event"] == "ROUTE_CALCULATED" for log in result["event_logs"])


def test_simulator_emergency_transit_policy():
    """Legacy test for emergency transit policy check."""
    sim = NetworkSimulator()
    res = sim.find_route if hasattr(sim, "find_route") else sim.router.find_route(
        NODE_CHECK_IN, NODE_SECURITY
    )
    assert res["total_cost"] > 0
