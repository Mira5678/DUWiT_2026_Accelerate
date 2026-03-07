# Quick setup:

# bash
# pip install -r requirements.txt
# export ANTHROPIC_API_KEY=your_key_here   # or set on Windows
# python app.py
# Then go to http://localhost:5000.


import os
import json
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/generate-ideas", methods=["POST"])
def generate_ideas():
    data = request.json
    topic = data.get("topic", "")
    existing = data.get("existing", [])
    context = data.get("context", "")

    existing_str = ", ".join(existing) if existing else "none yet"
    context_str = f" (Context: {context})" if context else ""

    prompt = (
        f"You are a creative brainstorming assistant. Generate exactly 5 fresh, interesting ideas or subtopics for: '{topic}'{context_str}. "
        f"Existing ideas to avoid duplicating: {existing_str}. "
        f"Return ONLY a JSON array of 5 short strings (2-5 words each). No explanation, no markdown, just the JSON array."
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    # Strip markdown fences if present
    response_text = response_text.replace("```json", "").replace("```", "").strip()
    ideas = json.loads(response_text)
    return jsonify({"success": True, "ideas": ideas})


@app.route("/api/refine-idea", methods=["POST"])
def refine_idea():
    data = request.json
    idea = data.get("idea", "")
    parent = data.get("parent", "")

    prompt = (
        f"Refine and improve this idea: '{idea}'"
        + (f" (it belongs to the topic '{parent}')" if parent else "")
        + ". Make it more specific, vivid, and actionable. "
        "Return ONLY the refined idea as a short phrase (2-6 words). No punctuation at end, no explanation."
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=60,
        messages=[{"role": "user", "content": prompt}]
    )

    refined = message.content[0].text.strip().strip(".")
    return jsonify({"success": True, "refined": refined})


@app.route("/api/expand-node", methods=["POST"])
def expand_node():
    data = request.json
    node_text = data.get("node", "")
    parent_text = data.get("parent", "")
    depth = data.get("depth", 1)

    count = 4 if depth <= 1 else 3

    prompt = (
        f"You are a study and brainstorming assistant. Generate exactly {count} specific subtopics or ideas for: '{node_text}'"
        + (f" (which is part of '{parent_text}')" if parent_text else "")
        + f". Return ONLY a JSON array of {count} short strings (2-5 words each). No explanation, no markdown, just the JSON array."
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    response_text = response_text.replace("```json", "").replace("```", "").strip()
    ideas = json.loads(response_text)
    return jsonify({"success": True, "ideas": ideas})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
