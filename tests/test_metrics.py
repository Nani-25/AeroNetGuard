"""
Unit tests for AeroNetGuard SimulationMetrics analytics engine.

Tests:
1. Empty initialization and zero-division protection
2. Successful simulation metrics computation
3. Simulation with failure and retransmission telemetry
4. CRC error detection statistics
5. Frame metrics table structure and field validation
6. Protocol breakdown metrics (Framing, CRC, Window, GBN)
7. Event timeline formatting and sequence indices
8. Efficiency ratio calculation
9. JSON serializability of all metric outputs
10. Legacy NetworkAnalytics compatibility facade
11. Method chaining and re-analysis support
"""

import json
import pytest
from simulation.network import AirportNetwork
from simulation.network_simulator import NetworkSimulator
from analytics.metrics import SimulationMetrics, NetworkAnalytics


@pytest.fixture
def clean_simulator():
    """Create a clean NetworkSimulator instance."""
    net = AirportNetwork()
    return NetworkSimulator(network=net)


def test_empty_initialization():
    """TEST 1: SimulationMetrics handles None and empty results without error."""
    metrics = SimulationMetrics()
    summary = metrics.get_summary()
    assert summary["simulation"]["status"] == "idle"
    assert summary["frames"]["total"] == 0
    assert summary["transmission"]["attempts"] == 0
    assert summary["transmission"]["success_rate"] == 0.0
    assert summary["crc"]["error_rate"] == 0.0
    assert summary["retransmission"]["count"] == 0
    assert summary["efficiency"]["frame_delivery_efficiency"] == 0.0
    assert metrics.get_frame_metrics() == []
    assert metrics.get_timeline() == []
    assert metrics.get_crc_metrics()["checked"] == 0
    assert metrics.get_route_metrics()["path"] == []


def test_successful_simulation_metrics(clean_simulator):
    """TEST 2: Compute metrics from a completely successful simulation."""
    result = clean_simulator.simulate(
        source="Control Tower",
        destination="Check-in",
        message="RUNWAY TWO SEVEN OPEN",
        window_size=2,
    )
    metrics = SimulationMetrics(result)
    summary = metrics.get_summary()

    # Route checks
    assert summary["route"]["source"] == "Control Tower"
    assert summary["route"]["destination"] == "Check-in"
    assert summary["route"]["path"] == ["Control Tower", "Check-in"]
    assert summary["route"]["route_cost"] == 2
    assert summary["route"]["hop_count"] == 1

    # Frames checks (4 words: RUNWAY, TWO, SEVEN, OPEN)
    assert summary["frames"]["total"] == 4
    assert summary["frames"]["successful"] == 4
    assert summary["frames"]["failed"] == 0

    # CRC checks
    assert summary["crc"]["valid"] == 4
    assert summary["crc"]["invalid"] == 0
    assert summary["crc"]["error_rate"] == 0.0

    # Retransmission checks (clean run)
    assert summary["retransmission"]["count"] == 0
    assert summary["retransmission"]["rate"] == 0.0
    assert summary["retransmission"]["affected_frames"] == 0

    # Transmission checks
    assert summary["transmission"]["attempts"] == 4
    assert summary["transmission"]["successful"] == 4
    assert summary["transmission"]["failed"] == 0
    assert summary["transmission"]["success_rate"] == 1.0

    # Efficiency (4 useful frames / 4 attempts = 1.0)
    assert summary["efficiency"]["frame_delivery_efficiency"] == 1.0
    assert summary["simulation"]["delivery_successful"] is True


def test_failure_and_retransmission_metrics(clean_simulator):
    """TEST 3: Compute metrics from simulation with failure and GBN recovery."""
    result = clean_simulator.simulate(
        source="Control Tower",
        destination="Baggage",
        message="SECURITY ALERT GATE A5",
        window_size=3,
        failure_sequence=[2],
    )
    metrics = SimulationMetrics(result)
    summary = metrics.get_summary()

    # 4 frames total: F0="SECURITY", F1="ALERT", F2="GATE", F3="A5"
    assert summary["frames"]["total"] == 4
    assert summary["simulation"]["delivery_successful"] is True

    # Retransmissions occurred for F2 (and any sliding window frames)
    assert summary["retransmission"]["count"] > 0
    assert summary["retransmission"]["affected_frames"] >= 1
    assert summary["retransmission"]["rate"] > 0.0
    assert summary["transmission"]["failed"] >= 1
    assert summary["simulated_failures"]["count"] >= 1

    # Efficiency should be less than 1.0 due to retransmissions
    assert summary["efficiency"]["frame_delivery_efficiency"] < 1.0
    assert summary["efficiency"]["frame_delivery_efficiency"] > 0.0


def test_crc_statistics_with_custom_events():
    """TEST 4: CRC statistics accurately track valid vs invalid frames."""
    fake_result = {
        "source": "Security",
        "destination": "Baggage",
        "route": ["Security", "Baggage"],
        "route_cost": 5,
        "hop_count": 1,
        "total_frames": 2,
        "delivery_successful": False,
        "frames": [
            {"sequence_number": 0, "payload": "A", "crc": 0x1234, "retransmission_count": 0},
            {"sequence_number": 1, "payload": "B", "crc": 0x5678, "retransmission_count": 0},
        ],
        "events": [
            {"event": "crc_verification", "sequence_number": 0, "is_valid": True},
            {"event": "crc_verification", "sequence_number": 1, "is_valid": False},
            {"event": "transmission", "sequence_number": 0, "status": "success"},
            {"event": "transmission", "sequence_number": 1, "status": "failed"},
        ],
    }
    metrics = SimulationMetrics(fake_result)
    crc_stats = metrics.get_crc_metrics()

    assert crc_stats["checked"] == 2
    assert crc_stats["valid"] == 1
    assert crc_stats["invalid"] == 1
    assert crc_stats["error_rate"] == 0.5


def test_frame_metrics_structure(clean_simulator):
    """TEST 5: get_frame_metrics() provides detailed per-frame telemetry."""
    result = clean_simulator.simulate(
        source="Control Tower",
        destination="Emergency Services",
        message="EMERGENCY BAGGAGE ALERT",
        window_size=3,
        failure_sequence=[1],
    )
    metrics = SimulationMetrics(result)
    frame_metrics = metrics.get_frame_metrics()

    assert len(frame_metrics) == 3  # 3 words
    for fm in frame_metrics:
        assert "sequence_number" in fm
        assert "frame_id" in fm
        assert "packet_id" in fm
        assert "payload" in fm
        assert "status" in fm
        assert "crc" in fm
        assert "retransmission_count" in fm
        assert "transmission_attempts" in fm
        assert "successful" in fm
        assert "failed" in fm

    # Frame 1 failed and was retransmitted
    f1 = next(f for f in frame_metrics if f["sequence_number"] == 1)
    assert f1["transmission_attempts"] >= 2
    assert f1["retransmission_count"] >= 1
    assert f1["successful"] is True


def test_protocol_metrics_breakdown(clean_simulator):
    """TEST 6: get_protocol_metrics() provides 4-layer protocol stack data."""
    result = clean_simulator.simulate(
        source="Control Tower",
        destination="Baggage",
        message="ALPHA BRAVO CHARLIE",
        window_size=2,
    )
    metrics = SimulationMetrics(result)
    proto = metrics.get_protocol_metrics()

    assert "framing" in proto
    assert proto["framing"]["total_frames"] == 3
    assert proto["framing"]["strategy"] == "word_based"

    assert "crc" in proto
    assert proto["crc"]["valid"] == 3

    assert "sliding_window" in proto
    assert proto["sliding_window"]["window_size"] == 2

    assert "go_back_n" in proto
    assert "retransmissions" in proto["go_back_n"]
    assert "retransmission_rate" in proto["go_back_n"]


def test_timeline_formatting(clean_simulator):
    """TEST 7: get_timeline() records sequential events with descriptions."""
    result = clean_simulator.simulate(
        source="Control Tower",
        destination="Security",
        message="CLEARANCE GRANTED",
        window_size=2,
    )
    metrics = SimulationMetrics(result)
    timeline = metrics.get_timeline()

    assert len(timeline) > 0
    for idx, item in enumerate(timeline):
        assert item["event_index"] == idx
        assert "event_type" in item
        assert "description" in item
        assert "status" in item
        assert "details" in item
        assert len(item["description"]) > 0


def test_json_serializability(clean_simulator):
    """TEST 8: All metric getters return 100% JSON-serializable structures."""
    result = clean_simulator.simulate(
        source="Control Tower",
        destination="Baggage",
        message="SECURITY ALERT GATE A5",
        window_size=3,
        failure_sequence=[2],
    )
    metrics = SimulationMetrics(result)

    # Should serialize without TypeError
    json_summary = json.dumps(metrics.get_summary())
    json_frames = json.dumps(metrics.get_frame_metrics())
    json_timeline = json.dumps(metrics.get_timeline())
    json_proto = json.dumps(metrics.get_protocol_metrics())
    json_crc = json.dumps(metrics.get_crc_metrics())
    json_route = json.dumps(metrics.get_route_metrics())

    assert len(json_summary) > 0
    assert len(json_frames) > 0
    assert len(json_timeline) > 0
    assert len(json_proto) > 0
    assert len(json_crc) > 0
    assert len(json_route) > 0


def test_network_analytics_backward_compatibility(clean_simulator):
    """TEST 9: NetworkAnalytics legacy class functions correctly."""
    result = clean_simulator.simulate(
        source="Control Tower",
        destination="Check-in",
        message="TEST MESSAGE",
        window_size=2,
    )
    legacy_report = NetworkAnalytics.analyze_simulation(result)
    assert isinstance(legacy_report, dict)
    assert "quality_rating" in legacy_report
    assert legacy_report["quality_rating"] == "EXCELLENT"
    assert legacy_report["total_frames"] == 2
    assert legacy_report["delivery_successful"] is True


def test_reanalysis_method_chaining(clean_simulator):
    """TEST 10: SimulationMetrics supports chaining and re-analysis."""
    res1 = clean_simulator.simulate(
        source="Control Tower",
        destination="Check-in",
        message="ONE",
        window_size=1,
    )
    res2 = clean_simulator.simulate(
        source="Control Tower",
        destination="Check-in",
        message="ONE TWO THREE",
        window_size=2,
    )

    metrics = SimulationMetrics()
    metrics.analyze(res1)
    assert metrics.get_summary()["frames"]["total"] == 1

    # Re-analyze second result
    metrics.analyze(res2)
    assert metrics.get_summary()["frames"]["total"] == 3
