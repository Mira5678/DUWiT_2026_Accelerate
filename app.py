# ╔══════════════════════════════════════════════════╗
# ║  Sprout — The Aesthetic Visual Mapping OS        ║
# ║  Backend: Flask + Anthropic Claude               ║
# ╚══════════════════════════════════════════════════╝
#
# Setup:
#   pip install flask anthropic
#   export ANTHROPIC_API_KEY=your_key_here
#   python app.py  →  http://localhost:5000

import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for
import anthropic

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"


# ════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════
def ask(prompt,
        system="You are Lumi, a warm and creative AI companion inside Sprout, a cozy visual mapping app. Be helpful, specific, and delightful.",
        max_tokens=400):
    msg = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()


def parse_json(text):
    clean = text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


# ════════════════════════════════════════
#  PAGE ROUTES
# ════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/mode-select")
def mode_select():
    return render_template("mode_select.html")


# ════════════════════════════════════════
#  AUTH ROUTES  (stub — wire up your DB)
# ════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def api_login():
    data     = request.json or {}
    email    = data.get("email", "").strip()
    password = data.get("password", "")
    if email and password:
        name = email.split("@")[0].capitalize()
        return jsonify({"success": True, "user": {"email": email, "name": name}})
    return jsonify({"success": False, "error": "Invalid credentials"}), 401


@app.route("/api/signup", methods=["POST"])
def api_signup():
    data     = request.json or {}
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip()
    password = data.get("password", "")
    if name and email and password:
        return jsonify({"success": True, "user": {"email": email, "name": name}})
    return jsonify({"success": False, "error": "Missing fields"}), 400


# ════════════════════════════════════════
#  AI — SHARED
# ════════════════════════════════════════

@app.route("/api/generate-ideas", methods=["POST"])
def generate_ideas():
    data     = request.json or {}
    topic    = data.get("topic", "")
    existing = data.get("existing", [])
    mode     = data.get("mode", "study")
    existing_str = ", ".join(existing) if existing else "none yet"
    flavour = ("study subtopics or learning concepts" if mode == "study"
               else "creative content angles, shot ideas, or storytelling hooks")
    prompt = (
        f"Generate exactly 5 fresh {flavour} for the topic: '{topic}'. "
        f"Already present (do not duplicate): {existing_str}. "
        "Return ONLY a JSON array of 5 short strings (2-5 words each). No markdown."
    )
    ideas = parse_json(ask(prompt, max_tokens=300))
    return jsonify({"success": True, "ideas": ideas})


@app.route("/api/expand-node", methods=["POST"])
def expand_node():
    data        = request.json or {}
    node_text   = data.get("node", "")
    parent_text = data.get("parent", "")
    depth       = data.get("depth", 1)
    mode        = data.get("mode", "study")
    count   = 4 if depth <= 1 else 3
    flavour = ("study subtopics or key concepts" if mode == "study"
               else "content ideas, shots, or creative angles")
    prompt = (
        f"Generate exactly {count} specific {flavour} for: '{node_text}'"
        + (f" (part of '{parent_text}')" if parent_text else "")
        + f". Return ONLY a JSON array of {count} short strings (2-5 words). No markdown."
    )
    ideas = parse_json(ask(prompt, max_tokens=250))
    return jsonify({"success": True, "ideas": ideas})


@app.route("/api/refine-idea", methods=["POST"])
def refine_idea():
    data   = request.json or {}
    idea   = data.get("idea", "")
    parent = data.get("parent", "")
    prompt = (
        f"Refine and improve this idea: '{idea}'"
        + (f" (belongs to '{parent}')" if parent else "")
        + ". Make it more vivid and specific. Return ONLY the improved phrase (2-6 words). No punctuation at end."
    )
    return jsonify({"success": True, "refined": ask(prompt, max_tokens=60).strip(".")})


# ════════════════════════════════════════
#  AI — STUDY HUB
# ════════════════════════════════════════

@app.route("/api/study/explain", methods=["POST"])
def study_explain():
    data  = request.json or {}
    node  = data.get("node", "")
    topic = data.get("topic", "")
    prompt = (f"Explain '{node}' (part of {topic}) in 2-3 warm friendly sentences using one fun analogy. "
              "Use 1-2 emojis. Under 80 words.")
    return jsonify({"success": True, "text": ask(prompt, max_tokens=200)})


@app.route("/api/study/quiz", methods=["POST"])
def study_quiz():
    data  = request.json or {}
    node  = data.get("node", "")
    topic = data.get("topic", "")
    prompt = (f"Give 3 quiz questions about '{node}' in the context of {topic}, easiest to hardest. "
              "After each add a blank line then '✅ Answer: ...'. Friendly tone. Under 200 words.")
    return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})


@app.route("/api/study/flashcards", methods=["POST"])
def study_flashcards():
    data  = request.json or {}
    node  = data.get("node", "")
    topic = data.get("topic", "")
    prompt = (f"Create 4 flashcards for '{node}' in the context of {topic}. "
              "Format: 🃏 FRONT: [question]\n🌸 BACK: [answer]\n\nUnder 200 words.")
    return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})


@app.route("/api/study/connect", methods=["POST"])
def study_connect():
    data  = request.json or {}
    node  = data.get("node", "")
    topic = data.get("topic", "")
    prompt = (f"Explain how '{node}' connects to other parts of {topic}. "
              "What breaks if you skip it? What does mastering it unlock? 2-3 short paragraphs with emojis. Under 150 words.")
    return jsonify({"success": True, "text": ask(prompt, max_tokens=350)})


# ════════════════════════════════════════
#  AI — CREATIVE STUDIO
# ════════════════════════════════════════

@app.route("/api/content/script", methods=["POST"])
def content_script():
    data  = request.json or {}
    node  = data.get("node", "")
    topic = data.get("topic", "")
    prompt = (f"Write a 30-second TikTok script for '{node}' angle of a video about '{topic}'. "
              "Format:\n🎬 HOOK (0-3s):\n📖 MIDDLE (3-25s):\n✨ CTA (25-30s):\nUnder 200 words.")
    return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})


@app.route("/api/content/moodboard", methods=["POST"])
def content_moodboard():
    data  = request.json or {}
    node  = data.get("node", "")
    topic = data.get("topic", "")
    prompt = (f"Visual moodboard brief for '{node}' in a video about '{topic}':\n"
              "🎨 COLOR PALETTE — 5 colorblind-friendly pastel hex codes with names\n"
              "📷 VISUAL AESTHETIC — 3 style references\n"
              "💡 LIGHTING MOOD\n🎥 CAMERA STYLE\n✨ OVERALL VIBE\nUnder 220 words.")
    return jsonify({"success": True, "text": ask(prompt, max_tokens=450)})


@app.route("/api/content/hooks", methods=["POST"])
def content_hooks():
    data  = request.json or {}
    node  = data.get("node", "")
    topic = data.get("topic", "")
    prompt = (f"5 TikTok hooks (first 3s) for '{node}' from a video about '{topic}'. "
              "Label each: Curiosity/Shock/Relatability/FOMO/Humor. Under 200 words.")
    return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})


@app.route("/api/content/shotlist", methods=["POST"])
def content_shotlist():
    data  = request.json or {}
    node  = data.get("node", "")
    topic = data.get("topic", "")
    prompt = (f"B-roll shot list for '{node}' in a video about '{topic}'. "
              "5 shots: 📽️ Shot type | 🎯 Subject | ⏱️ Duration | 💭 Why it works. Under 200 words.")
    return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})


# ════════════════════════════════════════
#  RUN
# ════════════════════════════════════════
if __name__ == "__main__":
    app.run(debug=True, port=5000)
