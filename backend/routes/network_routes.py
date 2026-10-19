"""
Network topology & routing API endpoints for AeroNetGuard.

Provides REST endpoints to query airport graph topology, departments (nodes),
and Dijkstra shortest-path calculations.
"""

from typing import Dict, Any, List
from flask import Blueprint, jsonify, request
from simulation.network import AirportNetwork
from simulation.dijkstra import DijkstraRouter

network_bp = Blueprint("network_routes", __name__)
airport_network = AirportNetwork()
router = DijkstraRouter(airport_network)


@network_bp.route("/api/network/topology", methods=["GET"])
def get_topology():
    """
    Return the complete airport network topology.

    Response:
    {
        "success": true,
        "nodes": [{"id": "...", "name": "..."}, ...],
        "connections": [{"source": "...", "destination": "...", "cost": ...}, ...]
    }
    """
    nodes = [{"id": node, "name": node} for node in airport_network.get_nodes()]
    connections = [
        {"source": u, "destination": v, "cost": w, "weight": w}
        for u, v, w in airport_network.get_connections()
    ]

    return jsonify({
        "success": True,
        "nodes": nodes,
        "connections": connections,
    }), 200


@network_bp.route("/api/network/nodes", methods=["GET"])
def get_nodes():
    """
    Return all canonical airport department node names.

    Response:
    {
        "success": true,
        "nodes": ["Control Tower", "Check-in", "Security", "Baggage", "Emergency Services"]
    }
    """
    return jsonify({
        "success": True,
        "nodes": airport_network.get_nodes(),
    }), 200


@network_bp.route("/api/network/route", methods=["GET", "POST"])
def get_route():
    """
    Compute shortest Dijkstra route between source and destination.

    Accepts GET query parameters (?source=...&destination=...)
    or optional POST JSON body ({"source": "...", "destination": "..."}).
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        source = data.get("source")
        destination = data.get("destination")
        allow_emergency = data.get("allow_emergency_transit", True)
    else:
        source = request.args.get("source")
        destination = request.args.get("destination")
        allow_emergency_param = request.args.get("allow_emergency_transit")
        allow_emergency = True if allow_emergency_param is None else (allow_emergency_param.lower() == "true")

    if not source or not destination:
        return jsonify({
            "success": False,
            "error": "source and destination are required",
        }), 400

    if not airport_network.has_node(source):
        return jsonify({
            "success": False,
            "error": f"Source node '{source}' does not exist in the airport network.",
        }), 400

    if not airport_network.has_node(destination):
        return jsonify({
            "success": False,
            "error": f"Destination node '{destination}' does not exist in the airport network.",
        }), 400

    try:
        route_info = router.find_route(
            source, destination, allow_emergency_transit=allow_emergency
        )
        return jsonify({
            "success": True,
            "route": route_info,
            "source": route_info["source"],
            "destination": route_info["destination"],
            "path": route_info["path"],
            "total_cost": route_info["total_cost"],
            "hop_count": route_info["hop_count"],
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 400
