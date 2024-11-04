from flask import Blueprint, jsonify
from datetime import datetime

health_bp = Blueprint('health', __name__)

# Tiempo de inicio del servicio
start_time = datetime.now()
service_version = "1.0.0"

@health_bp.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "UP",
        "checks": [
            {
                "data": {
                    "from": start_time.isoformat(),
                    "status": "READY"
                },
                "name": "Readiness check",
                "status": "UP"
            },
            {
                "data": {
                    "from": start_time.isoformat(),
                    "status": "ALIVE"
                },
                "name": "Liveness check",
                "status": "UP"
            }
        ]
    }), 200

@health_bp.route('/health/ready', methods=['GET'])
def health_ready():
    return jsonify({
        "status": "UP",
        "data": {
            "from": start_time.isoformat(),
            "version": service_version,
            "status": "READY"
        }
    }), 200

@health_bp.route('/health/live', methods=['GET'])
def health_live():
    return jsonify({
        "status": "UP",
        "data": {
            "from": start_time.isoformat(),
            "version": service_version,
            "status": "ALIVE"
        }
    }), 200
