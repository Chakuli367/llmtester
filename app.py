import os
from flask import Flask, request, jsonify
from add_tester import add_tester

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/add-tester", methods=["POST"])
def add_tester_route():
    secret = request.headers.get("X-Webhook-Secret")
    if secret != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    email = data.get("email")

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
