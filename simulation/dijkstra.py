"""
Dijkstra shortest-path routing algorithm module for AeroNetGuard.

DijkstraRouter calculates minimum-cost routes through the simulated airport network.
It uses link weights from the AirportNetwork graph to compute optimal transmission
paths, path costs, and hop counts between airport departments.

In airport operational architectures, safety-critical nodes such as Emergency Services
do not serve as intermediate transit relays for ordinary operational traffic
(e.g., Baggage and Security screening telemetry) unless Emergency Services is the origin
or destination. This policy can be toggled via `allow_emergency_transit`.
"""

from typing import List, Dict, Any, Optional
import networkx as nx
from simulation.network import AirportNetwork, NODE_EMERGENCY_SERVICES


class DijkstraRouter:
    """
    Dijkstra-based routing engine for the airport communication network.

    Receives an AirportNetwork instance and calculates the lowest-cost paths
    between airport nodes based on link weights using Dijkstra's algorithm.
    """

    def __init__(
        self,
        network: AirportNetwork,
        allow_emergency_transit: bool = True,
    ) -> None:
        """
        Initialize the router with an AirportNetwork instance.

        :param network: AirportNetwork instance containing the airport graph.
        :param allow_emergency_transit: Whether all nodes in the graph participate in routing (default True).
        :raises TypeError: If network does not provide a get_graph() method.
        """
        if not hasattr(network, "get_graph"):
            raise TypeError("network must provide a 'get_graph()' method returning a NetworkX Graph.")
        self.network: AirportNetwork = network
        self.graph: nx.Graph = network.get_graph()
        self.allow_emergency_transit: bool = allow_emergency_transit

    def _get_routing_graph(
        self,
        source: str,
        destination: str,
        allow_emergency_transit: Optional[bool] = None,
    ) -> nx.Graph:
        """
        Return the graph view suitable for routing between source and destination,
        applying transit isolation policies where applicable.

        :param source: Origin airport node.
        :param destination: Destination airport node.
        :param allow_emergency_transit: Override flag for emergency transit.
        :return: NetworkX Graph for route calculation.
        """
        permit_transit = (
            allow_emergency_transit
            if allow_emergency_transit is not None
            else self.allow_emergency_transit
        )

        # If emergency transit is permitted, or Emergency Services is either source or destination,
        # the complete graph is used.
        if permit_transit or source == NODE_EMERGENCY_SERVICES or destination == NODE_EMERGENCY_SERVICES:
            return self.graph

        # Otherwise, Emergency Services is excluded as an intermediate relay
        if self.graph.has_node(NODE_EMERGENCY_SERVICES):
            routing_graph = self.graph.copy()
            routing_graph.remove_node(NODE_EMERGENCY_SERVICES)
            return routing_graph

        return self.graph

    def find_shortest_path(
        self,
        source: str,
        destination: str,
        allow_emergency_transit: Optional[bool] = None,
    ) -> List[str]:
        """
        Find and return the shortest path (sequence of node names) between source and destination.

        :param source: Name of source airport node.
        :param destination: Name of destination airport node.
        :param allow_emergency_transit: Optional override for emergency transit policy.
        :return: List of node names along the shortest path.
        :raises ValueError: If source/destination nodes do not exist or are disconnected.
        """
        self._validate_nodes(source, destination)

        # Special case: source is identical to destination
        if source == destination:
            return [source]

        routing_graph = self._get_routing_graph(
            source, destination, allow_emergency_transit
        )

        try:
            path: List[str] = nx.shortest_path(
                routing_graph,
                source=source,
                target=destination,
                weight="weight",
                method="dijkstra",
            )
            return path
        except nx.NetworkXNoPath:
            raise ValueError(f"No route exists between source '{source}' and destination '{destination}'.")

    def get_path_cost(
        self,
        source: str,
        destination: str,
        allow_emergency_transit: Optional[bool] = None,
    ) -> int:
        """
        Calculate and return the total cost (sum of link weights) of the shortest path.

        :param source: Name of source airport node.
        :param destination: Name of destination airport node.
        :param allow_emergency_transit: Optional override for emergency transit policy.
        :return: Total integer cost of the path computed from edge weights.
        :raises ValueError: If source/destination nodes do not exist or are disconnected.
        """
        self._validate_nodes(source, destination)

        if source == destination:
            return 0

        path = self.find_shortest_path(
            source, destination, allow_emergency_transit=allow_emergency_transit
        )
        total_cost = 0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            total_cost += self.graph[u][v]["weight"]

        return int(total_cost)

    def find_route(
        self,
        source: str,
        destination: str,
        allow_emergency_transit: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Calculate and return structured route information.

        :param source: Name of source airport node.
        :param destination: Name of destination airport node.
        :param allow_emergency_transit: Optional override for emergency transit policy.
        :return: Dictionary containing source, destination, path, total_cost, and hop_count.
        :raises ValueError: If source/destination nodes do not exist or are disconnected.
        """
        self._validate_nodes(source, destination)

        if source == destination:
            path = [source]
            total_cost = 0
            hop_count = 0
        else:
            path = self.find_shortest_path(
                source, destination, allow_emergency_transit=allow_emergency_transit
            )
            total_cost = self.get_path_cost(
                source, destination, allow_emergency_transit=allow_emergency_transit
            )
            hop_count = len(path) - 1

        return {
            "source": source,
            "destination": destination,
            "path": path,
            "total_cost": total_cost,
            "hop_count": hop_count,
        }

    def _validate_nodes(self, source: str, destination: str) -> None:
        """
        Verify that source and destination nodes exist within the airport network graph.

        :param source: Source node name.
        :param destination: Destination node name.
        :raises ValueError: If either node is not in the graph.
        """
        if not self.graph.has_node(source):
            raise ValueError(f"Source node '{source}' does not exist in the airport network.")
        if not self.graph.has_node(destination):
            raise ValueError(f"Destination node '{destination}' does not exist in the airport network.")

    def __repr__(self) -> str:
        return f"<DijkstraRouter nodes={len(self.graph.nodes)} edges={len(self.graph.edges)}>"
