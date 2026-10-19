"""
Network topology module for AeroNetGuard.

This module defines the simulated airport communication network topology
connecting the Control Tower, Check-in, Security, Baggage, and Emergency Services
using a NetworkX weighted undirected graph.
"""

from typing import List, Tuple, Dict, Any
import networkx as nx


# Canonical Airport Node Names
NODE_CONTROL_TOWER: str = "Control Tower"
NODE_CHECK_IN: str = "Check-in"
NODE_SECURITY: str = "Security"
NODE_BAGGAGE: str = "Baggage"
NODE_EMERGENCY_SERVICES: str = "Emergency Services"


class AirportNetwork:
    """
    Simulated Airport Communication Network.

    Models the five core airport departments and their communication links
    as a weighted, undirected NetworkX graph.
    """

    # Canonical Airport Node Names
    NODE_CONTROL_TOWER: str = NODE_CONTROL_TOWER
    NODE_CHECK_IN: str = NODE_CHECK_IN
    NODE_SECURITY: str = NODE_SECURITY
    NODE_BAGGAGE: str = NODE_BAGGAGE
    NODE_EMERGENCY_SERVICES: str = NODE_EMERGENCY_SERVICES

    # All five required airport nodes
    NODES: List[str] = [
        NODE_CONTROL_TOWER,
        NODE_CHECK_IN,
        NODE_SECURITY,
        NODE_BAGGAGE,
        NODE_EMERGENCY_SERVICES,
    ]

    # Required bidirectional connections with their respective edge costs (weights)
    CONNECTIONS: List[Tuple[str, str, int]] = [
        (NODE_CONTROL_TOWER, NODE_CHECK_IN, 2),
        (NODE_CONTROL_TOWER, NODE_SECURITY, 3),
        (NODE_CHECK_IN, NODE_BAGGAGE, 2),
        (NODE_SECURITY, NODE_EMERGENCY_SERVICES, 2),
        (NODE_BAGGAGE, NODE_EMERGENCY_SERVICES, 4),
    ]

    def __init__(self) -> None:
        """
        Initialize the airport network and automatically construct the topology.
        """
        self.graph: nx.Graph = nx.Graph()
        self.add_nodes()
        self.add_connections()

    def add_nodes(self) -> None:
        """
        Add all five canonical airport nodes to the network.
        Ensures duplicate nodes are not unnecessarily recreated.
        """
        for node in self.NODES:
            if not self.graph.has_node(node):
                self.graph.add_node(node)

    def add_connections(self) -> None:
        """
        Add all five canonical bidirectional connections with their edge weights.
        Ensures duplicate connections are not unnecessarily recreated.
        """
        for source, destination, weight in self.CONNECTIONS:
            if not self.graph.has_edge(source, destination):
                self.graph.add_edge(source, destination, weight=weight)

    def get_graph(self) -> nx.Graph:
        """
        Return the internal NetworkX graph instance.

        :return: NetworkX Graph object.
        """
        return self.graph

    def get_nodes(self) -> List[str]:
        """
        Return the list of airport nodes in the network.

        :return: List of node names.
        """
        return list(self.graph.nodes)

    def get_connections(self) -> List[Tuple[str, str, int]]:
        """
        Return all network connections including their weights.

        :return: List of (source, destination, weight) tuples.
        """
        return [
            (u, v, data["weight"])
            for u, v, data in self.graph.edges(data=True)
        ]

    def get_neighbors(self, node: str) -> List[str]:
        """
        Return the neighboring nodes directly connected to the specified node.

        :param node: Node name to query.
        :return: List of neighboring node names.
        :raises ValueError: If the node does not exist in the network.
        """
        if not self.has_node(node):
            raise ValueError(f"Node '{node}' does not exist in the airport network.")
        return list(self.graph.neighbors(node))

    def get_edge_cost(self, source: str, destination: str) -> int:
        """
        Return the connection cost (weight) between source and destination.

        :param source: Source node name.
        :param destination: Destination node name.
        :return: Edge cost integer.
        :raises ValueError: If either node does not exist or no direct connection exists.
        """
        if not self.has_node(source):
            raise ValueError(f"Node '{source}' does not exist in the airport network.")
        if not self.has_node(destination):
            raise ValueError(f"Node '{destination}' does not exist in the airport network.")
        if not self.has_connection(source, destination):
            raise ValueError(
                f"No direct connection exists between '{source}' and '{destination}'."
            )
        return int(self.graph[source][destination]["weight"])

    def has_node(self, node: str) -> bool:
        """
        Check if a node exists in the network.

        :param node: Node name to check.
        :return: True if node exists, False otherwise.
        """
        return self.graph.has_node(node)

    def has_connection(self, source: str, destination: str) -> bool:
        """
        Check if a direct connection exists between source and destination.

        :param source: Source node name.
        :param destination: Destination node name.
        :return: True if connection exists, False otherwise.
        """
        return self.graph.has_edge(source, destination)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the airport network topology to a dictionary for API/UI integration.

        :return: Dictionary containing nodes and connections.
        """
        return {
            "nodes": self.get_nodes(),
            "connections": [
                {"source": u, "destination": v, "weight": w}
                for u, v, w in self.get_connections()
            ],
        }

    def __repr__(self) -> str:
        return f"<AirportNetwork nodes={len(self.graph.nodes)} connections={len(self.graph.edges)}>"
