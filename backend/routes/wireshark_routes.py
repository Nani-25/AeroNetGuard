"""
Wireshark & PCAP capture API endpoints for AeroNetGuard.

Provides REST endpoints to generate binary .pcap captures, retrieve PCAP summaries,
inspect packet headers/payloads, download PCAP files, and reset capture buffers.
"""

import os
from typing import Dict, Any
from flask import Blueprint, jsonify, request, send_from_directory, Response
from backend.routes.simulation_routes import simulator
from wireshark.capture import SimulationCapture, sanitize_filename, PCAPExporter

wireshark_bp = Blueprint("wireshark_routes", __name__)

# Singleton capture instance for the application
simulation_capture = SimulationCapture()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAPTURES_DIR = os.path.join(BASE_DIR, "wireshark", "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)


@wireshark_bp.route("/api/wireshark/capture", methods=["POST"])
def generate_capture():
    """
    Generate standard binary .pcap file for the latest simulation run.

    Request Body (optional):
        { "filename": "aeronetguard_capture.pcap" }

    Returns:
        JSON response with filename, packet_count, and download link.
    """
    if simulator.result is None:
        return jsonify({
            "success": False,
            "error": "No simulation data available",
        }), 400

    data = request.get_json(silent=True) or {}
    raw_filename = data.get("filename", "aeronetguard_capture.pcap")
    safe_filename = sanitize_filename(raw_filename)

    output_path = os.path.join(CAPTURES_DIR, safe_filename)

    # Convert simulator events into packet capture records
    simulation_capture.create_capture(simulator.result)
    export_meta = simulation_capture.export_pcap(output_path)
    summary = simulation_capture.get_capture_summary()

    return jsonify({
        "success": True,
        "filename": safe_filename,
        "packet_count": export_meta.get("packet_count", len(simulation_capture.get_packets())),
        "download_url": f"/api/wireshark/download/{safe_filename}",
        "summary": summary,
    }), 200


@wireshark_bp.route("/api/wireshark/summary", methods=["GET"])
def get_wireshark_summary():
    """
    Return summary metadata of the latest packet capture.
    """
    if simulator.result is None:
        return jsonify({
            "success": True,
            "summary": {
                "packet_count": 0,
                "frame_packets": 0,
                "ack_packets": 0,
                "retransmission_packets": 0,
                "crc_failure_packets": 0,
                "route_packets": 0,
                "pcap_file": None,
                "is_ready": False,
            },
            "message": "No simulation data available",
        }), 200

    # Auto-populate capture records if simulation exists but capture not generated yet
    if not simulation_capture.get_packets():
        simulation_capture.create_capture(simulator.result)

    summary = simulation_capture.get_capture_summary()
    return jsonify({
        "success": True,
        "summary": summary,
    }), 200


@wireshark_bp.route("/api/wireshark/packets", methods=["GET"])
def get_wireshark_packets():
    """
    Return list of formatted Wireshark packet capture records for UI display.
    """
    if simulator.result is None:
        return jsonify({
            "success": True,
            "packets": [],
            "count": 0,
            "message": "No simulation data available",
        }), 200

    # Auto-populate if not yet captured
    if not simulation_capture.get_packets():
        simulation_capture.create_capture(simulator.result)

    packets = simulation_capture.get_packets()
    return jsonify({
        "success": True,
        "packets": packets,
        "count": len(packets),
    }), 200


@wireshark_bp.route("/api/wireshark/reset", methods=["POST"])
def reset_wireshark():
    """
    Reset packet capture state.
    """
    simulation_capture.reset()
    return jsonify({
        "success": True,
        "message": "Wireshark packet capture state reset successfully.",
    }), 200


@wireshark_bp.route("/api/wireshark/download/<path:filename>", methods=["GET"])
def download_pcap(filename: str):
    """
    Safely download a generated PCAP capture file with strict path-traversal prevention.

    :param filename: Filename within wireshark/captures/.
    """
    # Reject directory traversal attempts
    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({
            "success": False,
            "error": "Invalid filename or path traversal detected.",
        }), 400

    safe_name = sanitize_filename(filename)
    target_path = os.path.join(CAPTURES_DIR, safe_name)

    if not os.path.isfile(target_path):
        return jsonify({
            "success": False,
            "error": f"Capture file '{safe_name}' not found.",
        }), 404

    return send_from_directory(
        CAPTURES_DIR,
        safe_name,
        as_attachment=True,
        mimetype="application/vnd.tcpdump.pcap",
    )
