import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from add_tester import add_tester

app = Flask(__name__)

# ✅ Enable CORS properly
CORS(app, resources={
    r"/add-tester": {
        "origins": [
            "http://localhost:3039",
            "https://your-production-domain.com"
        ],
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-Webhook-Secret"]
    }
})

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ✅ Explicit preflight handler (critical)
@app.route("/add-tester", methods=["OPTIONS"])
def add_tester_options():
    response = jsonify({"ok": True})
    response.headers.add("Access-Control-Allow-Origin", "http://localhost:3039")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type, X-Webhook-Secret")
    response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
    return response, 200


@app.route("/add-tester", methods=["POST"])
def add_tester_route():
    secret = request.headers.get("X-Webhook-Secret")
    if secret != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    email = data.get("email") if data else None

    if not email:
        return jsonify({"error": "No email provided"}), 400

    try:
        result = add_tester(email)
        return jsonify(result), 200
    except Exception as e:
        print(f"[Error] {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
