"""
Simulation API endpoints for AeroNetGuard.

Exposes endpoints to initiate discrete-event simulations, inspect runtime states,
retrieve event logs and transmitted frames, and reset the simulation environment.
"""

from typing import Dict, Any, List, Optional
from flask import Blueprint, jsonify, request, Response
from simulation.network_simulator import NetworkSimulator

simulation_bp = Blueprint("simulation_routes", __name__)

# Single shared simulator instance across the application process
simulator = NetworkSimulator()


@simulation_bp.route("/api/simulation/run", methods=["POST"])
def run_simulation():
    """
    Execute end-to-end discrete event simulation via NetworkSimulator.

    Request JSON:
    {
        "source": "Security",
        "destination": "Baggage",
        "message": "SECURITY ALERT GATE A5",
        "window_size": 3,
        "failure_sequence": [2]
    }

    Response:
    {
        "success": true,
        "simulation": { ... },
        "delivery_successful": true,
        "retransmission_count": ...
    }
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "Request body must be valid JSON.",
        }), 400

    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "Invalid JSON request payload.",
        }), 400

    # Mandatory field validation
    source = data.get("source")
    destination = data.get("destination")
    message = data.get("message")

    if not source:
        return jsonify({
            "success": False,
            "error": "source is required",
        }), 400

    if source != "Control Tower":
        return jsonify({
            "success": False,
            "error": "Invalid source node. Source must be Control Tower.",
        }), 400

    if not destination:
        return jsonify({
            "success": False,
            "error": "destination is required",
        }), 400

    if destination == "Control Tower":
        return jsonify({
            "success": False,
            "error": "Invalid destination node. Destination cannot be Control Tower.",
        }), 400

    if message is None:
        return jsonify({
            "success": False,
            "error": "message is required",
        }), 400

    if not isinstance(message, str):
        return jsonify({
            "success": False,
            "error": "message must be a string",
        }), 400

    if not message.strip():
        return jsonify({
            "success": False,
            "error": "message cannot be empty",
        }), 400

    # Optional fields with defaults
    window_size = data.get("window_size", 3)
    if type(window_size) is not int or window_size <= 0:
        return jsonify({
            "success": False,
            "error": "window_size must be a positive integer",
        }), 400

    failure_sequence = data.get("failure_sequence", [])
    if failure_sequence is not None:
        if not isinstance(failure_sequence, (list, tuple)):
            return jsonify({
                "success": False,
                "error": "failure_sequence must be a list of integers",
            }), 400
        for item in failure_sequence:
            if type(item) is not int:
                return jsonify({
                    "success": False,
                    "error": "Items in failure_sequence must be integers",
                }), 400
            if item < 0:
                return jsonify({
                    "success": False,
                    "error": "Failure sequence numbers cannot be negative",
                }), 400

    try:
        sim_result = simulator.simulate(
            source=source,
            destination=destination,
            message=message,
            window_size=window_size,
            failure_sequence=failure_sequence,
        )

        return jsonify({
            "success": True,
            "simulation": sim_result,
            "delivery_successful": sim_result.get("delivery_successful", False),
            "status": sim_result.get("status"),
            "retransmission_count": sim_result.get("retransmission_count", 0),
        }), 200

    except (ValueError, TypeError) as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Simulation execution failed.",
        }), 500


@simulation_bp.route("/api/simulation/state", methods=["GET"])
def get_simulation_state():
    """
    Return the current runtime state of the simulator.
    """
    return jsonify({
        "success": True,
        "state": simulator.get_state(),
    }), 200


@simulation_bp.route("/api/simulation/reset", methods=["POST"])
def reset_simulation():
    """
    Reset simulation state to initial conditions.
    """
    simulator.reset()
    return jsonify({
        "success": True,
        "message": "Simulation reset successfully",
        "state": simulator.get_state(),
    }), 200


@simulation_bp.route("/api/simulation/events", methods=["GET"])
def get_simulation_events():
    """
    Return all simulation event traces from the latest simulation run.
    """
    return jsonify({
        "success": True,
        "events": list(simulator.events),
    }), 200


@simulation_bp.route("/api/simulation/frames", methods=["GET"])
def get_simulation_frames():
    """
    Return frame objects and telemetry from the latest simulation run.
    """
    frames_data = [f.to_dict() for f in simulator.frames] if simulator.frames else []
    return jsonify({
        "success": True,
        "frames": frames_data,
    }), 200


@simulation_bp.route("/api/simulation/pcap", methods=["POST"])
def download_pcap():
    """
    Optional Wireshark PCAP export endpoint for simulation events.
    """
    try:
        from wireshark.capture import PCAPExporter
        data = request.get_json(silent=True) or {}
        event_logs = data.get("event_logs") or simulator.events
        pcap_bytes = PCAPExporter.generate_pcap_bytes(event_logs)
        return Response(
            pcap_bytes,
            mimetype="application/vnd.tcpdump.pcap",
            headers={"Content-Disposition": "attachment; filename=aeronetguard_capture.pcap"},
        )
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"PCAP export failed: {str(e)}",
        }), 500
