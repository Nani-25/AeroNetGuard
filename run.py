"""
AeroNetGuard: Airport Communication & Monitoring Network Simulator
Application Entrypoint Script.
"""

import os
from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print("=" * 70)
    print("  Starting AeroNetGuard Airport Communication & Network Simulator")
    print(f"  REST API & Dashboard: http://{host}:{port}")
    print("=" * 70)
    app.run(host=host, port=port, debug=debug)
