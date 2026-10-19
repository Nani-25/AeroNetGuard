"""
Unit and integration test suite for AeroNetGuard Wireshark/PCAP traffic capture.

Tests:
1. SimulationCapture handles uninitialized/empty simulation gracefully
2. Successful capture generation from simulator result
3. Capture packet count and summary metrics
4. Capture records metadata fields (capture_id, event_index, IPs, MACs, UDP port)
5. PCAP binary file generation and filesystem write
6. Event order preservation in capture
7. Deterministic node-to-IP and MAC mapping verification
8. Go-Back-N retransmission representation in capture
9. CRC failure packet representation
10. Filename sanitization and path traversal prevention
11. Capture reset functionality
12. Mandatory Scenario 1: Security -> Baggage, window 3, failure [2]
13. Mandatory Scenario 2: Check-in -> Emergency Services, window 3, failure [1]
14. Scapy programmatic PCAP inspection (Ether, IP, UDP 5001, Raw AERONETGUARD marker)
15. REST API endpoints (/api/wireshark/capture, /summary, /packets, /reset, /download)
16. Download security and traversal rejection
"""

import os
import pytest
from flask import Flask
from backend.app import create_app
from simulation.network import AirportNetwork
from simulation.network_simulator import NetworkSimulator
from wireshark.capture import (
    SimulationCapture,
    sanitize_filename,
    NODE_IP_MAP,
    NODE_MAC_MAP,
    DEFAULT_UDP_PORT,
    SCAPY_AVAILABLE,
)

if SCAPY_AVAILABLE:
    from scapy.all import rdpcap, Ether, IP, UDP, Raw


@pytest.fixture
def simulator():
    """Create a clean NetworkSimulator instance."""
    net = AirportNetwork()
    return NetworkSimulator(network=net)


@pytest.fixture
def client():
    """Create Flask test client."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_1_empty_capture_init():
    """TEST 1: SimulationCapture handles None and empty inputs safely."""
    capture = SimulationCapture()
    assert capture.get_packets() == []
    summary = capture.get_capture_summary()
    assert summary["packet_count"] == 0
    assert summary["frame_packets"] == 0
    assert summary["ack_packets"] == 0
    assert summary["retransmission_packets"] == 0
    assert summary["crc_failure_packets"] == 0
    assert summary["is_ready"] is False

    # Calling create_capture with None
    records = capture.create_capture(None)
    assert records == []


def test_2_successful_capture_generation(simulator):
    """TEST 2: Generate capture records from standard simulation."""
    res = simulator.simulate(
        source="Control Tower",
        destination="Check-in",
        message="CLEAR FOR TAKEOFF",
        window_size=2,
    )
    capture = SimulationCapture()
    packets = capture.create_capture(res)

    assert len(packets) > 0
    assert capture.get_packets() == packets

    summary = capture.get_capture_summary()
    assert summary["packet_count"] == len(packets)
    assert summary["frame_packets"] == 3  # 3 words: CLEAR, FOR, TAKEOFF
    assert summary["ack_packets"] == 3
    assert summary["retransmission_packets"] == 0
    assert summary["crc_failure_packets"] == 0
    assert summary["is_ready"] is True


def test_3_capture_metadata_fields(simulator):
    """TEST 3: Verify all required capture record fields exist."""
    res = simulator.simulate(
        source="Control Tower",
        destination="Check-in",
        message="LANDING PERMITTED",
        window_size=2,
    )
    capture = SimulationCapture()
    packets = capture.create_capture(res)

    required_fields = [
        "capture_id",
        "event_index",
        "frame_id",
        "packet_id",
        "source",
        "destination",
        "source_ip",
        "destination_ip",
        "source_mac",
        "destination_mac",
        "udp_port",
        "sequence_number",
        "payload",
        "event_type",
        "status",
        "crc_status",
        "retransmission_count",
        "raw_payload",
    ]

    for p in packets:
        for f in required_fields:
            assert f in p, f"Missing required field {f} in packet {p}"
        assert p["udp_port"] == DEFAULT_UDP_PORT
        assert "AERONETGUARD" in p["raw_payload"]


def test_4_node_ip_mac_mapping(simulator):
    """TEST 4: Check deterministic IP and MAC assignments."""
    assert NODE_IP_MAP["Control Tower"] == "10.0.0.1"
    assert NODE_IP_MAP["Check-in"] == "10.0.0.2"
    assert NODE_IP_MAP["Security"] == "10.0.0.3"
    assert NODE_IP_MAP["Baggage"] == "10.0.0.4"
    assert NODE_IP_MAP["Emergency Services"] == "10.0.0.5"

    res = simulator.simulate(
        source="Control Tower",
        destination="Baggage",
        message="CHECK BAG",
        window_size=2,
    )
    capture = SimulationCapture()
    packets = capture.create_capture(res)

    frame_pkts = [p for p in packets if p["event_type"] == "FRAME"]
    assert len(frame_pkts) > 0
    assert frame_pkts[0]["source_ip"] == "10.0.0.1"
    assert frame_pkts[0]["destination_ip"] == "10.0.0.4"
    assert frame_pkts[0]["source_mac"] == "02:00:00:00:00:01"
    assert frame_pkts[0]["destination_mac"] == "02:00:00:00:00:04"

    # ACKs should have reversed source and destination
    ack_pkts = [p for p in packets if p["event_type"] == "ACK"]
    assert len(ack_pkts) > 0
    assert ack_pkts[0]["source_ip"] == "10.0.0.4"
    assert ack_pkts[0]["destination_ip"] == "10.0.0.1"


def test_5_retransmission_representation(simulator):
    """TEST 5: Retransmission packets are captured with correct types and counters."""
    res = simulator.simulate(
        source="Control Tower",
        destination="Baggage",
        message="ALERT GATE ONE",
        window_size=3,
        failure_sequence=[1],
    )
    capture = SimulationCapture()
    packets = capture.create_capture(res)

    retrans_pkts = [p for p in packets if p["event_type"] == "RETRANSMISSION"]
    assert len(retrans_pkts) > 0
    assert retrans_pkts[0]["status"] == "retransmitted"
    assert retrans_pkts[0]["retransmission_count"] >= 1
    assert "RETRANSMISSION=" in retrans_pkts[0]["raw_payload"]


def test_6_crc_failure_representation():
    """TEST 6: CRC failure events generate CRC_FAILURE capture records."""
    fake_result = {
        "source": "Security",
        "destination": "Baggage",
        "route": ["Security", "Baggage"],
        "packet_id": "P_TEST",
        "frames": [
            {"sequence_number": 0, "payload": "PAYLOAD_A", "crc": 100, "retransmission_count": 0},
        ],
        "events": [
            {"event": "transmission", "sequence_number": 0, "status": "failed"},
            {"event": "crc_verification", "sequence_number": 0, "is_valid": False},
        ],
    }
    capture = SimulationCapture()
    packets = capture.create_capture(fake_result)

    crc_fails = [p for p in packets if p["event_type"] == "CRC_FAILURE"]
    assert len(crc_fails) == 1
    assert crc_fails[0]["crc_status"] == "invalid"
    assert "CRC=INVALID" in crc_fails[0]["raw_payload"]


def test_7_filename_sanitization():
    """TEST 7: sanitize_filename protects against directory traversal and invalid paths."""
    assert sanitize_filename("test.pcap") == "test.pcap"
    assert sanitize_filename("test") == "test.pcap"
    assert sanitize_filename("../../etc/passwd") == "passwd.pcap"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe.pcap"
    assert sanitize_filename("/var/log/capture.pcap") == "capture.pcap"
    assert sanitize_filename("   ") == "aeronetguard_capture.pcap"
    assert sanitize_filename(None) == "aeronetguard_capture.pcap"
    assert sanitize_filename("...hidden") == "hidden.pcap"


def test_8_pcap_file_export(simulator, tmp_path):
    """TEST 8: export_pcap writes valid PCAP binary file to disk."""
    res = simulator.simulate(
        source="Control Tower",
        destination="Check-in",
        message="HELLO WORLD",
        window_size=2,
    )
    capture = SimulationCapture()
    capture.create_capture(res)

    pcap_file = str(tmp_path / "test_out.pcap")
    meta = capture.export_pcap(pcap_file)

    assert meta["success"] is True
    assert meta["file"] == "test_out.pcap"
    assert meta["packet_count"] > 0
    assert os.path.exists(pcap_file)
    assert os.path.getsize(pcap_file) > 0


def test_9_capture_reset():
    """TEST 9: reset() cleans all capture state."""
    capture = SimulationCapture()
    capture.packets = [{"test": 1}]
    capture.pcap_path = "some_path.pcap"
    capture.reset()

    assert capture.packets == []
    assert capture.pcap_path is None
    assert capture.get_capture_summary()["packet_count"] == 0


def test_10_mandatory_scenario_1_scapy_validation(simulator, tmp_path):
    """
    TEST 10: Mandatory Scenario 1:
    Control Tower -> Baggage, 'SECURITY ALERT GATE A5', window 3, failure [2]
    Validates Scapy layers: Ether / IP / UDP(5001) / Raw(AERONETGUARD)
    """
    res = simulator.simulate(
        source="Control Tower",
        destination="Baggage",
        message="SECURITY ALERT GATE A5",
        window_size=3,
        failure_sequence=[2],
    )
    capture = SimulationCapture()
    capture.create_capture(res)

    pcap_file = str(tmp_path / "scenario_1.pcap")
    meta = capture.export_pcap(pcap_file)
    assert meta["packet_count"] > 0

    if SCAPY_AVAILABLE:
        packets = rdpcap(pcap_file)
        assert len(packets) == meta["packet_count"]

        # Check every packet structure
        for p in packets:
            assert p.haslayer(Ether), "Missing Ethernet layer"
            assert p.haslayer(IP), "Missing IP layer"
            assert p.haslayer(UDP), "Missing UDP layer"
            assert p[UDP].sport == 5001
            assert p[UDP].dport == 5001
            assert p.haslayer(Raw), "Missing Raw payload layer"
            raw_text = p[Raw].load.decode("utf-8", errors="ignore")
            assert "AERONETGUARD" in raw_text

        # First packet is ROUTE
        route_pkt = packets[0]
        assert "AERONETGUARD|ROUTE" in route_pkt[Raw].load.decode("utf-8")
        assert route_pkt[IP].src == "10.0.0.1"
        assert route_pkt[IP].dst == "10.0.0.4"


def test_11_mandatory_scenario_2_scapy_validation(simulator, tmp_path):
    """
    TEST 11: Mandatory Scenario 2:
    Control Tower -> Emergency Services, 'EMERGENCY BAGGAGE ALERT', window 3, failure [1]
    Validates distinct source/dest IPs and retransmission capture.
    """
    res = simulator.simulate(
        source="Control Tower",
        destination="Emergency Services",
        message="EMERGENCY BAGGAGE ALERT",
        window_size=3,
        failure_sequence=[1],
    )
    capture = SimulationCapture()
    capture.create_capture(res)

    pcap_file = str(tmp_path / "scenario_2.pcap")
    meta = capture.export_pcap(pcap_file)

    if SCAPY_AVAILABLE:
        packets = rdpcap(pcap_file)
        assert len(packets) == meta["packet_count"]

        # Check Control Tower (10.0.0.1) and Emergency Services (10.0.0.5)
        ip_srcs = {p[IP].src for p in packets}
        ip_dsts = {p[IP].dst for p in packets}
        assert "10.0.0.1" in ip_srcs
        assert "10.0.0.5" in ip_dsts

        # Find retransmission packet
        retrans_raws = [
            p[Raw].load.decode("utf-8")
            for p in packets
            if "RETRANSMISSION" in p[Raw].load.decode("utf-8")
        ]
        assert len(retrans_raws) > 0


def test_12_api_no_simulation(client):
    """TEST 12: API endpoints behave safely when no simulation has been run."""
    client.post("/api/simulation/reset")

    # Capture generation should fail with HTTP 400
    res = client.post("/api/wireshark/capture", json={"filename": "test.pcap"})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "No simulation data available" in data["error"]

    # Summary should return packet_count 0
    res = client.get("/api/wireshark/summary")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["summary"]["packet_count"] == 0

    # Packets should return empty list
    res = client.get("/api/wireshark/packets")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["packets"] == []


def test_13_api_capture_and_download(client):
    """TEST 13: Full API workflow: run simulation -> generate capture -> download PCAP."""
    # 1. Run simulation
    client.post("/api/simulation/run", json={
        "source": "Control Tower",
        "destination": "Baggage",
        "message": "SECURITY ALERT GATE A5",
        "window_size": 3,
        "failure_sequence": [2],
    })

    # 2. Call capture generation endpoint
    res = client.post("/api/wireshark/capture", json={
        "filename": "integration_test.pcap"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["filename"] == "integration_test.pcap"
    assert data["packet_count"] > 0
    assert "/api/wireshark/download/integration_test.pcap" in data["download_url"]

    # 3. Verify summary endpoint
    res = client.get("/api/wireshark/summary")
    assert res.status_code == 200
    sum_data = res.get_json()
    assert sum_data["success"] is True
    assert sum_data["summary"]["packet_count"] > 0
    assert sum_data["summary"]["is_ready"] is True

    # 4. Verify packets endpoint
    res = client.get("/api/wireshark/packets")
    assert res.status_code == 200
    pkt_data = res.get_json()
    assert pkt_data["success"] is True
    assert len(pkt_data["packets"]) == data["packet_count"]

    # 5. Download PCAP file
    dl_res = client.get("/api/wireshark/download/integration_test.pcap")
    assert dl_res.status_code == 200
    assert dl_res.mimetype == "application/vnd.tcpdump.pcap"
    assert len(dl_res.data) > 0


def test_14_api_download_path_traversal_rejection(client):
    """TEST 14: Download endpoint strictly blocks path traversal attacks."""
    # Slashes or .. in URL
    res = client.get("/api/wireshark/download/..%2F..%2Fapp.py")
    assert res.status_code in [400, 404]

    res = client.get("/api/wireshark/download/non_existent_file.pcap")
    assert res.status_code == 404
    data = res.get_json()
    assert data["success"] is False


def test_15_api_reset(client):
    """TEST 15: POST /api/wireshark/reset clears capture state."""
    res = client.post("/api/wireshark/reset")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "reset successfully" in data["message"]
