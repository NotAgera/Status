# server.py
from flask import Flask, render_template, request, jsonify
from logic.core import double_value

def create_app():
    app = Flask(__name__)

    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html")

    @app.route("/api/process", methods=["POST"])
    def process():
        try:
            data = request.get_json(force=True) or {}
            value = float(data.get("value", 0))
            result = double_value(value)
            return jsonify({"ok": True, "result": result})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    # Health-check endpoint (nyttig på hosting)
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    return app

# For lokal kjøring
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
