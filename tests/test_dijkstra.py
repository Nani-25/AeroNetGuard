"""
Unit tests for DijkstraRouter in simulation.dijkstra module.

Validates:
- Test 1: Security -> Baggage (Path, cost 7, hops 3)
- Test 2: Check-in -> Emergency Services (Path, cost 6, hops 2)
- Test 3: Security -> Emergency Services (Path, cost 2, hops 1)
- Test 4: Control Tower -> Baggage (Path, cost 4, hops 2)
- Test 5: Baggage -> Control Tower (Cost 4, bidirectional)
- Test 6: Security -> Security (Same node special case: cost 0, hops 0)
- Test 7: Invalid source ("Unknown Airport") raises ValueError
- Test 8: Invalid destination ("Unknown Airport") raises ValueError
- Disconnected nodes route failure handling
- Emergency Services transit policy toggle verification
- Router initialization validation
"""

import pytest
from simulation.network import AirportNetwork
from simulation.dijkstra import DijkstraRouter


@pytest.fixture
def network():
    """Fixture providing a fresh default AirportNetwork."""
    return AirportNetwork()


@pytest.fixture
def router(network):
    """Fixture providing a DijkstraRouter bound to the default AirportNetwork."""
    return DijkstraRouter(network)


def test_1_security_to_baggage(router):
    """
    Test 1:
    Source: Security
    Destination: Baggage
    Expected Path: Security -> Emergency Services -> Baggage
    Expected Cost: 6 (2 + 4)
    Expected Hops: 2
    """
    route = router.find_route("Security", "Baggage")
    expected_path = ["Security", "Emergency Services", "Baggage"]

    assert route["source"] == "Security"
    assert route["destination"] == "Baggage"
    assert route["path"] == expected_path
    assert route["total_cost"] == 6
    assert route["hop_count"] == 2

    assert router.find_shortest_path("Security", "Baggage") == expected_path
    assert router.get_path_cost("Security", "Baggage") == 6


def test_baggage_to_security(router):
    """
    Test Baggage -> Security:
    Expected Path: Baggage -> Emergency Services -> Security
    Expected Cost: 6 (4 + 2)
    Expected Hops: 2
    """
    route = router.find_route("Baggage", "Security")
    expected_path = ["Baggage", "Emergency Services", "Security"]

    assert route["source"] == "Baggage"
    assert route["destination"] == "Security"
    assert route["path"] == expected_path
    assert route["total_cost"] == 6
    assert route["hop_count"] == 2

    assert router.find_shortest_path("Baggage", "Security") == expected_path
    assert router.get_path_cost("Baggage", "Security") == 6


def test_control_tower_to_emergency_services(router):
    """
    Test Control Tower -> Emergency Services:
    Expected Path: Control Tower -> Security -> Emergency Services
    Expected Cost: 5 (3 + 2)
    Expected Hops: 2
    """
    route = router.find_route("Control Tower", "Emergency Services")
    expected_path = ["Control Tower", "Security", "Emergency Services"]

    assert route["source"] == "Control Tower"
    assert route["destination"] == "Emergency Services"
    assert route["path"] == expected_path
    assert route["total_cost"] == 5
    assert route["hop_count"] == 2

    assert router.find_shortest_path("Control Tower", "Emergency Services") == expected_path
    assert router.get_path_cost("Control Tower", "Emergency Services") == 5


def test_2_checkin_to_emergency_services(router):
    """
    Test 2:
    Source: Check-in
    Destination: Emergency Services
    Expected Path: Check-in -> Baggage -> Emergency Services
    Expected Cost: 6 (2 + 4)
    Expected Hops: 2
    """
    route = router.find_route("Check-in", "Emergency Services")
    expected_path = ["Check-in", "Baggage", "Emergency Services"]

    assert route["source"] == "Check-in"
    assert route["destination"] == "Emergency Services"
    assert route["path"] == expected_path
    assert route["total_cost"] == 6
    assert route["hop_count"] == 2

    assert router.find_shortest_path("Check-in", "Emergency Services") == expected_path
    assert router.get_path_cost("Check-in", "Emergency Services") == 6


def test_3_security_to_emergency_services(router):
    """
    Test 3:
    Source: Security
    Destination: Emergency Services
    Expected Path: Security -> Emergency Services
    Expected Cost: 2
    Expected Hops: 1
    """
    route = router.find_route("Security", "Emergency Services")
    expected_path = ["Security", "Emergency Services"]

    assert route["source"] == "Security"
    assert route["destination"] == "Emergency Services"
    assert route["path"] == expected_path
    assert route["total_cost"] == 2
    assert route["hop_count"] == 1

    assert router.find_shortest_path("Security", "Emergency Services") == expected_path
    assert router.get_path_cost("Security", "Emergency Services") == 2


def test_4_control_tower_to_baggage(router):
    """
    Test 4:
    Source: Control Tower
    Destination: Baggage
    Expected Path: Control Tower -> Check-in -> Baggage
    Expected Cost: 4 (2 + 2)
    Expected Hops: 2
    """
    route = router.find_route("Control Tower", "Baggage")
    expected_path = ["Control Tower", "Check-in", "Baggage"]

    assert route["source"] == "Control Tower"
    assert route["destination"] == "Baggage"
    assert route["path"] == expected_path
    assert route["total_cost"] == 4
    assert route["hop_count"] == 2

    assert router.find_shortest_path("Control Tower", "Baggage") == expected_path
    assert router.get_path_cost("Control Tower", "Baggage") == 4


def test_5_baggage_to_control_tower_bidirectional(router):
    """
    Test 5:
    Source: Baggage
    Destination: Control Tower
    Expected Cost: 4 (symmetric / bidirectional)
    Expected Path: Baggage -> Check-in -> Control Tower
    """
    route = router.find_route("Baggage", "Control Tower")
    expected_path = ["Baggage", "Check-in", "Control Tower"]

    assert route["path"] == expected_path
    assert route["total_cost"] == 4
    assert route["hop_count"] == 2

    assert router.find_shortest_path("Baggage", "Control Tower") == expected_path
    assert router.get_path_cost("Baggage", "Control Tower") == 4


def test_6_same_source_and_destination(router):
    """
    Test 6:
    Source: Security
    Destination: Security
    Expected: path = ["Security"], cost = 0, hop_count = 0
    """
    route = router.find_route("Security", "Security")

    assert route["source"] == "Security"
    assert route["destination"] == "Security"
    assert route["path"] == ["Security"]
    assert route["total_cost"] == 0
    assert route["hop_count"] == 0

    assert router.find_shortest_path("Security", "Security") == ["Security"]
    assert router.get_path_cost("Security", "Security") == 0


def test_7_invalid_source_raises_value_error(router):
    """Test 7: Invalid source node raises ValueError."""
    with pytest.raises(ValueError, match="Source node 'Unknown Airport' does not exist"):
        router.find_shortest_path("Unknown Airport", "Security")

    with pytest.raises(ValueError, match="Source node 'Unknown Airport' does not exist"):
        router.get_path_cost("Unknown Airport", "Security")

    with pytest.raises(ValueError, match="Source node 'Unknown Airport' does not exist"):
        router.find_route("Unknown Airport", "Security")


def test_8_invalid_destination_raises_value_error(router):
    """Test 8: Invalid destination node raises ValueError."""
    with pytest.raises(ValueError, match="Destination node 'Unknown Airport' does not exist"):
        router.find_shortest_path("Security", "Unknown Airport")

    with pytest.raises(ValueError, match="Destination node 'Unknown Airport' does not exist"):
        router.get_path_cost("Security", "Unknown Airport")

    with pytest.raises(ValueError, match="Destination node 'Unknown Airport' does not exist"):
        router.find_route("Security", "Unknown Airport")


def test_disconnected_nodes_raise_value_error(network):
    """Verify that if links are removed causing disconnection, a ValueError is raised."""
    # Remove all connections to Control Tower to isolate it
    network.get_graph().remove_edge("Control Tower", "Check-in")
    network.get_graph().remove_edge("Control Tower", "Security")

    router = DijkstraRouter(network)

    with pytest.raises(ValueError, match="No route exists between source 'Control Tower' and destination 'Baggage'"):
        router.find_shortest_path("Control Tower", "Baggage")

    with pytest.raises(ValueError, match="No route exists between source 'Control Tower' and destination 'Baggage'"):
        router.get_path_cost("Control Tower", "Baggage")

    with pytest.raises(ValueError, match="No route exists between source 'Control Tower' and destination 'Baggage'"):
        router.find_route("Control Tower", "Baggage")


def test_emergency_transit_policy_toggle(router):
    """Verify when emergency transit is explicitly permitted, direct shortest transit is computed."""
    # With emergency transit enabled: Security -> Emergency Services -> Baggage (2 + 4 = 6)
    route = router.find_route("Security", "Baggage", allow_emergency_transit=True)
    assert route["path"] == ["Security", "Emergency Services", "Baggage"]
    assert route["total_cost"] == 6
    assert route["hop_count"] == 2


def test_initialization_type_validation():
    """Verify initialization checks for valid network object."""
    with pytest.raises(TypeError, match="must provide a 'get_graph\\(\\)' method"):
        DijkstraRouter("invalid_network_object")
