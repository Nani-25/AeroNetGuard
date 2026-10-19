"""
Analytics API endpoints for AeroNetGuard.

Exposes deterministic simulation telemetry, protocol performance metrics,
per-frame metrics, and event timeline calculated by SimulationMetrics.
"""

from typing import Dict, Any
from flask import Blueprint, jsonify, request
from backend.routes.simulation_routes import simulator
from analytics.metrics import SimulationMetrics, NetworkAnalytics

analytics_bp = Blueprint("analytics_routes", __name__)


@analytics_bp.route("/api/analytics/summary", methods=["GET"])
def get_analytics_summary():
    """
    Return comprehensive analytics and performance summary from the most recent simulation run.

    Uses SimulationMetrics to analyze the simulator result.
    """
    if simulator.result is None:
        return jsonify({
            "success": True,
            "analytics": None,
            "summary": {},
            "message": "No simulation data available",
        }), 200

    metrics = SimulationMetrics(simulator.result)
    summary_data = metrics.get_summary()

    return jsonify({
        "success": True,
        "analytics": summary_data,
        "summary": summary_data,
    }), 200


@analytics_bp.route("/api/analytics/frames", methods=["GET"])
def get_analytics_frames():
    """
    Return per-frame performance and verification metrics.
    """
    if simulator.result is None:
        return jsonify({
            "success": True,
            "frames": [],
            "message": "No simulation data available",
        }), 200

    metrics = SimulationMetrics(simulator.result)
    return jsonify({
        "success": True,
        "frames": metrics.get_frame_metrics(),
    }), 200


@analytics_bp.route("/api/analytics/timeline", methods=["GET"])
def get_analytics_timeline():
    """
    Return simulation event timeline records in chronological order.
    """
    if simulator.result is None:
        return jsonify({
            "success": True,
            "timeline": [],
            "message": "No simulation data available",
        }), 200

    metrics = SimulationMetrics(simulator.result)
    return jsonify({
        "success": True,
        "timeline": metrics.get_timeline(),
    }), 200


@analytics_bp.route("/api/analytics/protocol", methods=["GET"])
def get_analytics_protocol():
    """
    Return breakdown of protocol metrics (Framing, CRC, Sliding Window, Go-Back-N).
    """
    if simulator.result is None:
        return jsonify({
            "success": True,
            "protocol": None,
            "message": "No simulation data available",
        }), 200

    metrics = SimulationMetrics(simulator.result)
    return jsonify({
        "success": True,
        "protocol": metrics.get_protocol_metrics(),
    }), 200


@analytics_bp.route("/api/analytics/metrics", methods=["POST"])
def compute_metrics():
    """
    Legacy endpoint for external metrics payload analysis.
    """
    try:
        sim_result = request.get_json(silent=True) or {}
        report = NetworkAnalytics.analyze_simulation(sim_result)
        return jsonify({
            "success": True,
            "report": report,
            **report,
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 400
