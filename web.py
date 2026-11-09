from flask import Flask, render_template, request, jsonify
from nexus.assistant import Assistant
from nexus.conversation import Conversation
from nexus.config import HISTORY_DIR, ensure_directories
from flask import Response, stream_with_context
import json

app = Flask(__name__)

ensure_directories()

assistant = Assistant()
conversation = Conversation(HISTORY_DIR)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400

    if len(message) > 20000:
        return jsonify({"error": "Message is too long"}), 400

    def generate():
        conversation.add("user", message)

        parts = []

        try:
            for chunk in assistant.generate(conversation):
                parts.append(chunk)
                yield json.dumps({
                    "token": chunk
                }) + "\n"

            answer = "".join(parts).strip()

            if answer:
                conversation.add("assistant", answer)

            yield json.dumps({"done": True}) + "\n"

        except Exception as error:
            if (
                conversation.messages
                and conversation.messages[-1]["role"] == "user"
                and conversation.messages[-1]["content"] == message
            ):
                conversation.messages.pop()
                conversation.save()

            yield json.dumps({
                "error": str(error)
            }) + "\n"

    return Response(
        stream_with_context(generate()),
        content_type="application/x-ndjson"
    )


@app.route("/api/reset", methods=["POST"])
def reset():
    conversation.clear()
    return jsonify({"success": True})


@app.route("/api/status")
def status():
    connected, message = assistant.check_connection()

    return jsonify({
        "connected": connected,
        "model": assistant.provider.model,
        "message": message
    })


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
