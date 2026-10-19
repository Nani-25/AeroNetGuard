"""
Flask application factory and configuration for AeroNetGuard.

Provides create_app() to instantiate the REST API with registered blueprints,
CORS security, structured JSON error handlers, and health telemetry.
"""

import os
from flask import Flask, jsonify, request, render_template
from backend.routes.network_routes import network_bp
from backend.routes.simulation_routes import simulation_bp
from backend.routes.analytics_routes import analytics_bp
from backend.routes.wireshark_routes import wireshark_bp


def create_app() -> Flask:
    """
    Create, configure, and return the Flask application instance.

    :return: Configured Flask app.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, "frontend", "templates")
    static_dir = os.path.join(base_dir, "frontend", "static")

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
        static_url_path="/static",
    )

    # Configure JSON responses
    app.config["JSON_SORT_KEYS"] = False
    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

    # Configure CORS for local development
    try:
        from flask_cors import CORS
        CORS(
            app,
            resources={
                r"/api/*": {
                    "origins": [
                        "http://127.0.0.1",
                        "http://localhost",
                        "http://127.0.0.1:5000",
                        "http://localhost:5000",
                        "http://127.0.0.1:3000",
                        "http://localhost:3000",
                        "http://127.0.0.1:8080",
                        "http://localhost:8080",
                    ]
                }
            },
            supports_credentials=True,
        )
    except ImportError:
        pass

    @app.after_request
    def set_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin and ("127.0.0.1" in origin or "localhost" in origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

    # Health check endpoint
    @app.route("/api/health", methods=["GET"])
    def health_check():
        """
        System health check endpoint.
        """
        return jsonify({
            "success": True,
            "service": "AeroNetGuard API",
            "status": "running",
        }), 200

    # Register Blueprints
    app.register_blueprint(network_bp)
    app.register_blueprint(simulation_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(wireshark_bp)

    # Web Dashboard Page Routes
    @app.route("/", methods=["GET"])
    def index_page():
        """Render main dashboard view."""
        return render_template("index.html")

    @app.route("/topology", methods=["GET"])
    def topology_page():
        """Render network topology graph and route inspector view."""
        return render_template("topology.html")

    @app.route("/simulation", methods=["GET"])
    def simulation_page():
        """Render dedicated GBN simulation view."""
        return render_template("simulation.html")

    @app.route("/packet-monitor", methods=["GET"])
    @app.route("/packet_monitor", methods=["GET"])
    def packet_monitor_page():
        """Render packet and frame inspector view."""
        return render_template("packet_monitor.html")

    @app.route("/analytics", methods=["GET"])
    def analytics_page():
        """Render network analytics and metrics view."""
        return render_template("analytics.html")

    @app.route("/traffic-analysis", methods=["GET"])
    @app.route("/traffic_analysis", methods=["GET"])
    def traffic_analysis_page():
        """Render Wireshark traffic capture analysis view."""
        return render_template("traffic_analysis.html")

    # JSON Error Handlers
    @app.errorhandler(400)
    def bad_request(error):
        description = getattr(error, "description", "Bad request.")
        return jsonify({
            "success": False,
            "error": description if isinstance(description, str) else "Bad request.",
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "success": False,
            "error": "Endpoint not found.",
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "success": False,
            "error": "Method not allowed.",
        }), 405

    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({
            "success": False,
            "error": "Internal server error.",
        }), 500

    @app.errorhandler(Exception)
    def handle_unhandled_exception(error):
        if hasattr(error, "code") and hasattr(error, "description"):
            code = error.code if isinstance(error.code, int) else 500
            desc = error.description if isinstance(error.description, str) else "An error occurred."
            return jsonify({
                "success": False,
                "error": desc,
            }), code
        return jsonify({
            "success": False,
            "error": "Internal server error.",
        }), 500

    return app
