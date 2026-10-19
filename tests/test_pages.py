"""
Unit and integration tests for AeroNetGuard Flask HTML Page Routes and Static Assets.
"""

import pytest
from backend.app import create_app


@pytest.fixture
def client():
    """Create a test client for the AeroNetGuard Flask application."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestPageRoutes:
    """Test suite verifying all HTML dashboard pages render successfully with status 200."""

    def test_dashboard_index_page(self, client):
        """GET / should render index.html with 200 OK and expected DOM elements."""
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.content_type
        html = res.get_data(as_text=True)
        assert "AeroNetGuard" in html
        assert "SYSTEM ONLINE" in html
        assert "Simulation Parameters" in html
        assert "Airport Network Topology" in html
        assert "topologySvg" in html
        assert "dashboard.js" in html
        # Step 12 Animation Controls & Progress Elements
        assert "pauseSimulationBtn" in html
        assert "resumeSimulationBtn" in html
        assert "speedSelect" in html
        assert "simulationProgressFill" in html
        assert "currentEventBanner" in html

    def test_topology_page(self, client):
        """GET /topology should render topology.html with 200 OK."""
        res = client.get("/topology")
        assert res.status_code == 200
        assert "text/html" in res.content_type
        html = res.get_data(as_text=True)
        assert "AeroNetGuard" in html
        assert "Airport Network Graph Topology" in html
        assert "Dijkstra Route Finder" in html
        assert "topology.js" in html

    def test_simulation_page(self, client):
        """GET /simulation should render simulation.html with 200 OK."""
        res = client.get("/simulation")
        assert res.status_code == 200
        assert "text/html" in res.content_type
        html = res.get_data(as_text=True)
        assert "AeroNetGuard" in html
        assert "Simulation Execution Controls" in html
        assert "Go-Back-N ARQ" in html
        assert "simulation.js" in html
        # Step 12 Animation Controls & Progress Elements
        assert "simPauseBtn" in html
        assert "simResumeBtn" in html
        assert "simSpeedSelect" in html
        assert "simProgressFill" in html
        assert "simCurrentEventBanner" in html

    def test_packet_monitor_pages(self, client):
        """GET /packet-monitor and /packet_monitor should render packet_monitor.html with 200 OK."""
        for path in ["/packet-monitor", "/packet_monitor"]:
            res = client.get(path)
            assert res.status_code == 200
            assert "text/html" in res.content_type
            html = res.get_data(as_text=True)
            assert "AeroNetGuard" in html
            assert "Packet Details" in html
            assert "Frame Information Table" in html
            assert "packet_monitor.js" in html

    def test_analytics_page(self, client):
        """GET /analytics should render analytics.html with 200 OK."""
        res = client.get("/analytics")
        assert res.status_code == 200
        assert "text/html" in res.content_type
        html = res.get_data(as_text=True)
        assert "AeroNetGuard" in html
        assert "Network Performance Summary" in html
        assert "Total Frames" in html
        assert "Successful Frames" in html
        assert "Failed Frames" in html
        assert "analytics.js" in html

    def test_traffic_analysis_page(self, client):
        """GET /traffic-analysis should render traffic_analysis.html with 200 OK."""
        res = client.get("/traffic-analysis")
        assert res.status_code == 200
        assert "text/html" in res.content_type
        html = res.get_data(as_text=True)
        assert "AeroNetGuard" in html
        assert "Traffic Analysis" in html
        assert "traffic_analysis.js" in html


class TestStaticAssets:
    """Test suite ensuring all referenced CSS and JS files exist and are servable."""

    @pytest.mark.parametrize("asset_path", [
        "/static/css/style.css",
        "/static/css/dashboard.css",
        "/static/css/components.css",
        "/static/js/dashboard.js",
        "/static/js/topology.js",
        "/static/js/simulation.js",
        "/static/js/packet_monitor.js",
        "/static/js/analytics.js",
        "/static/js/traffic_analysis.js",
    ])
    def test_static_asset_servable(self, client, asset_path):
        """Static asset should return HTTP 200."""
        res = client.get(asset_path)
        assert res.status_code == 200, f"Failed to serve asset: {asset_path}"
        assert len(res.data) > 0


class TestSimulationIntegrationViaPages:
    """Verify simulation execution and subsequent state retrieval via API endpoints."""

    def test_full_simulation_flow(self, client):
        """Test reset -> run -> state check -> analytics summary sequence."""
        # 1. Reset
        reset_res = client.post("/api/simulation/reset")
        assert reset_res.status_code == 200

        # 2. Run simulation with failure sequence
        run_payload = {
            "source": "Control Tower",
            "destination": "Baggage",
            "message": "SECURITY ALERT GATE A5",
            "window_size": 3,
            "failure_sequence": [2],
        }
        run_res = client.post("/api/simulation/run", json=run_payload)
        assert run_res.status_code == 200
        sim_data = run_res.get_json()["simulation"]

        assert sim_data["delivery_successful"] is True
        assert sim_data["route"] == ["Control Tower", "Check-in", "Baggage"]
        assert sim_data["route_cost"] == 4
        assert sim_data["hop_count"] == 2
        assert sim_data["total_frames"] == 4
        assert sim_data["retransmission_count"] >= 1

        # 3. Verify state
        state_res = client.get("/api/simulation/state")
        assert state_res.status_code == 200
        state = state_res.get_json()["state"]
        assert state["state"] == "delivered"

        # 4. Verify frames
        frames_res = client.get("/api/simulation/frames")
        assert frames_res.status_code == 200
        frames = frames_res.get_json()["frames"]
        assert len(frames) == 4

        # 5. Verify analytics summary
        analytics_res = client.get("/api/analytics/summary")
        assert analytics_res.status_code == 200
        summary = analytics_res.get_json()["summary"]
        assert summary["total_frames"] == 4
        assert summary["delivery_status"] == "delivered"
        assert summary["retransmissions"] >= 1
