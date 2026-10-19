"""
Test suite for AeroNetGuard Flask REST API.

Tests all endpoints:
1. Application factory creation
2. Health check endpoint (GET /api/health)
3. Network topology endpoint (GET /api/network/topology)
4. Network nodes endpoint (GET /api/network/nodes)
5. Shortest path route endpoint (GET /api/network/route)
6. Invalid route node error handling
7. Missing route parameters error handling
8. Run successful simulation (POST /api/simulation/run)
9. Run simulation with failure recovery (POST /api/simulation/run)
10. Get simulation state (GET /api/simulation/state)
11. Get simulation events (GET /api/simulation/events)
12. Get simulation frames (GET /api/simulation/frames)
13. Get analytics summary (GET /api/analytics/summary)
14. Reset simulation (POST /api/simulation/reset)
15. Invalid JSON request handling
16. Invalid window size handling
17. Missing message validation
18. Unknown endpoint 404 handler
19. Mandatory API route test (Security -> Baggage)
20. Mandatory simulation test (Security -> Baggage, window 3)
21. Mandatory failure test (Security -> Baggage, failure [2])
22. Frames empty when reset
23. Analytics empty when reset
24. Analytics endpoints empty state (summary, frames, timeline, protocol)
25. Analytics endpoints post-simulation state (summary, frames, timeline, protocol)
26. Analytics failure & retransmission telemetry via API
"""

import pytest
from flask import Flask
from backend.app import create_app


@pytest.fixture
def client():
    """Create a Flask test client for API testing."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_1_app_creation():
    """TEST 1: Application factory creates valid Flask app instance."""
    app = create_app()
    assert isinstance(app, Flask)
    assert "network_routes" in app.blueprints
    assert "simulation_routes" in app.blueprints
    assert "analytics_routes" in app.blueprints


def test_2_health_endpoint(client):
    """TEST 2: GET /api/health returns operational status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["service"] == "AeroNetGuard API"
    assert data["status"] == "running"


def test_3_get_topology(client):
    """TEST 3: GET /api/network/topology returns all nodes and connections."""
    response = client.get("/api/network/topology")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["nodes"]) == 5
    assert len(data["connections"]) == 5

    # Check connection structure
    first_conn = data["connections"][0]
    assert "source" in first_conn
    assert "destination" in first_conn
    assert "cost" in first_conn


def test_4_get_nodes(client):
    """TEST 4: GET /api/network/nodes returns canonical airport department names."""
    response = client.get("/api/network/nodes")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    expected_nodes = [
        "Control Tower",
        "Check-in",
        "Security",
        "Baggage",
        "Emergency Services",
    ]
    assert sorted(data["nodes"]) == sorted(expected_nodes)


def test_5_get_route(client):
    """TEST 5: GET /api/network/route computes Dijkstra path."""
    response = client.get("/api/network/route?source=Control Tower&destination=Check-in")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    route = data["route"]
    assert route["source"] == "Control Tower"
    assert route["destination"] == "Check-in"
    assert route["path"] == ["Control Tower", "Check-in"]
    assert route["total_cost"] == 2
    assert route["hop_count"] == 1


def test_6_invalid_route(client):
    """TEST 6: Invalid route nodes return HTTP 400 with clear message."""
    response = client.get("/api/network/route?source=Unknown Node&destination=Baggage")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "does not exist" in data["error"]


def test_7_missing_route_parameters(client):
    """TEST 7: Missing source or destination parameters return HTTP 400."""
    response = client.get("/api/network/route?source=Security")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "source and destination are required" in data["error"]


def test_8_run_successful_simulation(client):
    """TEST 8: POST /api/simulation/run executes simulation without errors."""
    payload = {
        "source": "Control Tower",
        "destination": "Check-in",
        "message": "FLIGHT CLEARED FOR ARRIVAL",
        "window_size": 2,
    }
    response = client.post("/api/simulation/run", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["delivery_successful"] is True
    assert data["simulation"]["status"] == "delivered"


def test_9_run_simulation_with_failure(client):
    """TEST 9: POST /api/simulation/run with failure_sequence recovers via GBN."""
    payload = {
        "source": "Control Tower",
        "destination": "Baggage",
        "message": "SCAN ALERT GATE B2",
        "window_size": 3,
        "failure_sequence": [1],
    }
    response = client.post("/api/simulation/run", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["delivery_successful"] is True
    assert data["retransmission_count"] > 0


def test_10_get_state(client):
    """TEST 10: GET /api/simulation/state returns runtime state dictionary."""
    response = client.get("/api/simulation/state")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "state" in data
    assert "events" in data["state"]


def test_11_get_events(client):
    """TEST 11: GET /api/simulation/events returns trace of lifecycle events."""
    # Ensure a simulation has run
    client.post("/api/simulation/run", json={
        "source": "Control Tower",
        "destination": "Baggage",
        "message": "TEST MSG",
        "window_size": 2,
    })
    response = client.get("/api/simulation/events")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert isinstance(data["events"], list)
    assert len(data["events"]) > 0


def test_12_get_frames(client):
    """TEST 12: GET /api/simulation/frames returns serialized frame dictionaries."""
    client.post("/api/simulation/run", json={
        "source": "Control Tower",
        "destination": "Baggage",
        "message": "WORD1 WORD2",
        "window_size": 2,
    })
    response = client.get("/api/simulation/frames")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["frames"]) == 2
    assert data["frames"][0]["payload"] == "WORD1"
    assert data["frames"][1]["payload"] == "WORD2"


def test_13_get_analytics_summary(client):
    """TEST 13: GET /api/analytics/summary returns performance telemetry."""
    client.post("/api/simulation/run", json={
        "source": "Control Tower",
        "destination": "Baggage",
        "message": "ALPHA BRAVO",
        "window_size": 2,
    })
    response = client.get("/api/analytics/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    summary = data["summary"]
    assert summary["total_frames"] == 2
    assert summary["delivery_successful"] is True


def test_14_reset_simulation(client):
    """TEST 14: POST /api/simulation/reset restores clean initialized state."""
    response = client.post("/api/simulation/reset")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "Simulation reset successfully"
    assert data["state"]["state"] == "initialized"
    assert data["state"]["total_frames"] == 0


def test_15_invalid_json_request(client):
    """TEST 15: Non-JSON POST body returns HTTP 400."""
    response = client.post(
        "/api/simulation/run",
        data="non-json-content",
        content_type="text/plain",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "JSON" in data["error"]


def test_16_invalid_window_size(client):
    """TEST 16: Non-positive or invalid window_size returns HTTP 400."""
    payload = {
        "source": "Control Tower",
        "destination": "Baggage",
        "message": "MSG",
        "window_size": -1,
    }
    response = client.post("/api/simulation/run", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "positive integer" in data["error"]


def test_17_missing_message(client):
    """TEST 17: Request without message returns HTTP 400."""
    payload = {
        "source": "Control Tower",
        "destination": "Baggage",
    }
    response = client.post("/api/simulation/run", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "message is required" in data["error"]


def test_18_unknown_endpoint(client):
    """TEST 18: Unrecognized URL returns clean 404 JSON error."""
    response = client.get("/api/nonexistent/endpoint")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["error"] == "Endpoint not found."


# --- Mandatory API Tests ---

def test_19_mandatory_api_route(client):
    """
    MANDATORY API TEST:
    GET /api/network/route?source=Security&destination=Baggage
    Verify:
        success == True
        path == ["Security", "Emergency Services", "Baggage"]
        total_cost == 6
        hop_count == 2
    """
    response = client.get("/api/network/route?source=Security&destination=Baggage")
    assert response.status_code == 200
    data = response.get_json()

    assert data["success"] is True
    route = data["route"]
    assert route["path"] == ["Security", "Emergency Services", "Baggage"]
    assert route["total_cost"] == 6
    assert route["hop_count"] == 2


def test_20_mandatory_simulation_run(client):
    """
    MANDATORY SIMULATION TEST:
    POST /api/simulation/run
    JSON: { "source": "Control Tower", "destination": "Baggage", "message": "SECURITY ALERT GATE A5", "window_size": 3 }
    Verify:
        HTTP 200
        success == True
        delivery_successful == True
    """
    payload = {
        "source": "Control Tower",
        "destination": "Baggage",
        "message": "SECURITY ALERT GATE A5",
        "window_size": 3,
    }
    response = client.post("/api/simulation/run", json=payload)
    assert response.status_code == 200
    data = response.get_json()

    assert data["success"] is True
    assert data["delivery_successful"] is True
    assert data["simulation"]["status"] == "delivered"


def test_21_mandatory_failure_test(client):
    """
    MANDATORY FAILURE TEST:
    POST /api/simulation/run
    JSON: { "source": "Control Tower", "destination": "Baggage", "message": "SECURITY ALERT GATE A5", "window_size": 3, "failure_sequence": [2] }
    Verify:
        HTTP 200
        success == True
        delivery_successful == True
        retransmission_count > 0
    """
    payload = {
        "source": "Control Tower",
        "destination": "Baggage",
        "message": "SECURITY ALERT GATE A5",
        "window_size": 3,
        "failure_sequence": [2],
    }
    response = client.post("/api/simulation/run", json=payload)
    assert response.status_code == 200
    data = response.get_json()

    assert data["success"] is True
    assert data["delivery_successful"] is True
    assert data["retransmission_count"] > 0


def test_22_empty_frames_when_reset(client):
    """TEST 22: Frames endpoint returns empty list after reset."""
    client.post("/api/simulation/reset")
    response = client.get("/api/simulation/frames")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["frames"] == []


def test_23_empty_analytics_when_reset(client):
    """TEST 23: Analytics summary endpoint returns empty dict after reset."""
    client.post("/api/simulation/reset")
    response = client.get("/api/analytics/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["summary"] == {}


def test_24_analytics_endpoints_empty_state(client):
    """TEST 24: All 4 analytics endpoints return safe empty states when no simulation has run."""
    client.post("/api/simulation/reset")

    # 1. Summary
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    d = res.get_json()
    assert d["success"] is True
    assert d["analytics"] is None
    assert d["message"] == "No simulation data available"

    # 2. Frames
    res = client.get("/api/analytics/frames")
    assert res.status_code == 200
    d = res.get_json()
    assert d["success"] is True
    assert d["frames"] == []
    assert d["message"] == "No simulation data available"

    # 3. Timeline
    res = client.get("/api/analytics/timeline")
    assert res.status_code == 200
    d = res.get_json()
    assert d["success"] is True
    assert d["timeline"] == []
    assert d["message"] == "No simulation data available"

    # 4. Protocol
    res = client.get("/api/analytics/protocol")
    assert res.status_code == 200
    d = res.get_json()
    assert d["success"] is True
    assert d["protocol"] is None
    assert d["message"] == "No simulation data available"


def test_25_analytics_endpoints_after_simulation(client):
    """TEST 25: All 4 analytics endpoints return populated telemetry after simulation."""
    client.post("/api/simulation/run", json={
        "source": "Control Tower",
        "destination": "Baggage",
        "message": "SECURITY ALERT GATE A5",
        "window_size": 3,
    })

    # 1. Summary
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    d = res.get_json()
    assert d["success"] is True
    assert d["analytics"]["frames"]["total"] == 4
    assert d["analytics"]["frames"]["successful"] == 4
    assert d["analytics"]["route"]["path"] == ["Control Tower", "Check-in", "Baggage"]
    assert d["analytics"]["efficiency"]["frame_delivery_efficiency"] == 1.0

    # 2. Frames
    res = client.get("/api/analytics/frames")
    assert res.status_code == 200
    d = res.get_json()
    assert d["success"] is True
    assert len(d["frames"]) == 4
    assert d["frames"][0]["payload"] == "SECURITY"
    assert d["frames"][0]["crc_status"] == "valid"

    # 3. Timeline
    res = client.get("/api/analytics/timeline")
    assert res.status_code == 200
    d = res.get_json()
    assert d["success"] is True
    assert len(d["timeline"]) > 0
    assert d["timeline"][0]["event_index"] == 0

    # 4. Protocol
    res = client.get("/api/analytics/protocol")
    assert res.status_code == 200
    d = res.get_json()
    assert d["success"] is True
    assert d["protocol"]["framing"]["total_frames"] == 4
    assert d["protocol"]["crc"]["valid"] == 4
    assert d["protocol"]["sliding_window"]["window_size"] == 3
    assert d["protocol"]["go_back_n"]["retransmissions"] == 0


def test_26_analytics_failure_telemetry(client):
    """TEST 26: Analytics endpoints accurately report GBN retransmissions and failure rates."""
    client.post("/api/simulation/run", json={
        "source": "Control Tower",
        "destination": "Baggage",
        "message": "SECURITY ALERT GATE A5",
        "window_size": 3,
        "failure_sequence": [2],
    })

    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    d = res.get_json()
    assert d["success"] is True
    summary = d["analytics"]

    assert summary["retransmission"]["count"] > 0
    assert summary["retransmission"]["affected_frames"] >= 1
    assert summary["simulated_failures"]["count"] >= 1
    assert summary["efficiency"]["frame_delivery_efficiency"] < 1.0

    # Check frames endpoint shows retransmission count
    f_res = client.get("/api/analytics/frames")
    frames = f_res.get_json()["frames"]
    f2 = next(f for f in frames if f["sequence_number"] == 2)
    assert f2["retransmission_count"] >= 1


def test_27_api_rejects_security_as_source(client):
    """TEST 27: API rejects Security as source node with HTTP 400."""
    res = client.post("/api/simulation/run", json={
        "source": "Security",
        "destination": "Baggage",
        "message": "ALERT",
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "Invalid source node. Source must be Control Tower."


def test_28_api_rejects_baggage_as_source(client):
    """TEST 28: API rejects Baggage as source node with HTTP 400."""
    res = client.post("/api/simulation/run", json={
        "source": "Baggage",
        "destination": "Security",
        "message": "ALERT",
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "Invalid source node. Source must be Control Tower."


def test_29_api_rejects_checkin_as_source(client):
    """TEST 29: API rejects Check-in as source node with HTTP 400."""
    res = client.post("/api/simulation/run", json={
        "source": "Check-in",
        "destination": "Emergency Services",
        "message": "ALERT",
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "Invalid source node. Source must be Control Tower."


def test_30_api_rejects_emergency_services_as_source(client):
    """TEST 30: API rejects Emergency Services as source node with HTTP 400."""
    res = client.post("/api/simulation/run", json={
        "source": "Emergency Services",
        "destination": "Security",
        "message": "ALERT",
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "Invalid source node. Source must be Control Tower."


def test_31_api_rejects_control_tower_as_destination(client):
    """TEST 31: API rejects Control Tower as destination node with HTTP 400."""
    res = client.post("/api/simulation/run", json={
        "source": "Control Tower",
        "destination": "Control Tower",
        "message": "ALERT",
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "Invalid destination node. Destination cannot be Control Tower."

