"""
Unit tests for the AirportNetwork class in simulation.network module.

Validates:
1. Exactly five nodes exist.
2. All required nodes exist.
3. Exactly five connections exist.
4. All required connections exist.
5. Correct edge weights exist.
6. Connections are bidirectional.
7. get_neighbors() works.
8. get_edge_cost() returns correct values.
9. Unknown nodes and non-existent connections are handled correctly.
10. has_node() works.
11. has_connection() works.
"""

import pytest
import networkx as nx
from simulation.network import AirportNetwork


@pytest.fixture
def network():
    """Fixture providing a fresh instance of AirportNetwork."""
    return AirportNetwork()


def test_1_exactly_five_nodes_exist(network):
    """Test 1: Verify exactly five nodes exist in the network."""
    nodes = network.get_nodes()
    assert len(nodes) == 5
    assert network.get_graph().number_of_nodes() == 5


def test_2_all_required_nodes_exist(network):
    """Test 2: Verify all five required airport nodes exist with exact names."""
    required_nodes = [
        "Control Tower",
        "Check-in",
        "Security",
        "Baggage",
        "Emergency Services",
    ]
    nodes = network.get_nodes()
    for node in required_nodes:
        assert node in nodes


def test_3_exactly_five_connections_exist(network):
    """Test 3: Verify exactly five connections exist in the network."""
    connections = network.get_connections()
    assert len(connections) == 5
    assert network.get_graph().number_of_edges() == 5


def test_4_all_required_connections_exist(network):
    """Test 4: Verify all five required connections exist in the network."""
    required_connections = [
        ("Control Tower", "Check-in"),
        ("Control Tower", "Security"),
        ("Check-in", "Baggage"),
        ("Security", "Emergency Services"),
        ("Baggage", "Emergency Services"),
    ]
    for src, dst in required_connections:
        assert network.has_connection(src, dst)
        assert network.has_connection(dst, src)


def test_5_correct_edge_weights_exist(network):
    """
    Test 5: Verify correct edge weights exist for all required connections:
    - Control Tower <-> Check-in: 2
    - Control Tower <-> Security: 3
    - Check-in <-> Baggage: 2
    - Security <-> Emergency Services: 2
    - Baggage <-> Emergency Services: 4
    """
    graph = network.get_graph()
    assert graph["Control Tower"]["Check-in"]["weight"] == 2
    assert graph["Control Tower"]["Security"]["weight"] == 3
    assert graph["Check-in"]["Baggage"]["weight"] == 2
    assert graph["Security"]["Emergency Services"]["weight"] == 2
    assert graph["Baggage"]["Emergency Services"]["weight"] == 4


def test_6_connections_are_bidirectional(network):
    """Test 6: Verify connections and edge costs are strictly bidirectional."""
    pairs = [
        ("Control Tower", "Check-in", 2),
        ("Control Tower", "Security", 3),
        ("Check-in", "Baggage", 2),
        ("Security", "Emergency Services", 2),
        ("Baggage", "Emergency Services", 4),
    ]
    for u, v, weight in pairs:
        assert network.has_connection(u, v) is True
        assert network.has_connection(v, u) is True
        assert network.get_edge_cost(u, v) == weight
        assert network.get_edge_cost(v, u) == weight


def test_7_get_neighbors_works(network):
    """Test 7: Verify get_neighbors returns correct neighbors for each node."""
    tower_neighbors = set(network.get_neighbors("Control Tower"))
    assert tower_neighbors == {"Check-in", "Security"}

    checkin_neighbors = set(network.get_neighbors("Check-in"))
    assert checkin_neighbors == {"Control Tower", "Baggage"}

    security_neighbors = set(network.get_neighbors("Security"))
    assert security_neighbors == {"Control Tower", "Emergency Services"}

    baggage_neighbors = set(network.get_neighbors("Baggage"))
    assert baggage_neighbors == {"Check-in", "Emergency Services"}

    emergency_neighbors = set(network.get_neighbors("Emergency Services"))
    assert emergency_neighbors == {"Security", "Baggage"}


def test_8_get_edge_cost_returns_correct_values(network):
    """Test 8: Verify get_edge_cost returns expected values."""
    assert network.get_edge_cost("Control Tower", "Check-in") == 2
    assert network.get_edge_cost("Control Tower", "Security") == 3
    assert network.get_edge_cost("Check-in", "Baggage") == 2
    assert network.get_edge_cost("Security", "Emergency Services") == 2
    assert network.get_edge_cost("Baggage", "Emergency Services") == 4


def test_9_unknown_nodes_are_handled_correctly(network):
    """Test 9: Verify queries with unknown nodes or non-existent edges raise ValueError."""
    # get_neighbors with unknown node
    with pytest.raises(ValueError, match="does not exist"):
        network.get_neighbors("Unknown Node")

    # get_edge_cost with unknown source
    with pytest.raises(ValueError, match="does not exist"):
        network.get_edge_cost("Unknown", "Security")

    # get_edge_cost with unknown destination
    with pytest.raises(ValueError, match="does not exist"):
        network.get_edge_cost("Security", "Unknown")

    # get_edge_cost between valid nodes without a direct edge
    with pytest.raises(ValueError, match="No direct connection exists"):
        network.get_edge_cost("Control Tower", "Emergency Services")


def test_10_has_node_works(network):
    """Test 10: Verify has_node returns True for valid nodes and False otherwise."""
    assert network.has_node("Control Tower") is True
    assert network.has_node("Check-in") is True
    assert network.has_node("Security") is True
    assert network.has_node("Baggage") is True
    assert network.has_node("Emergency Services") is True

    assert network.has_node("Tower") is False
    assert network.has_node("Gate 12") is False
    assert network.has_node("") is False


def test_11_has_connection_works(network):
    """Test 11: Verify has_connection returns True for existing edges and False otherwise."""
    assert network.has_connection("Control Tower", "Check-in") is True
    assert network.has_connection("Check-in", "Control Tower") is True
    assert network.has_connection("Control Tower", "Security") is True
    assert network.has_connection("Check-in", "Baggage") is True
    assert network.has_connection("Security", "Emergency Services") is True
    assert network.has_connection("Baggage", "Emergency Services") is True

    # Nodes without direct link
    assert network.has_connection("Control Tower", "Baggage") is False
    assert network.has_connection("Control Tower", "Emergency Services") is False
    assert network.has_connection("Check-in", "Security") is False
    assert network.has_connection("Check-in", "Emergency Services") is False
