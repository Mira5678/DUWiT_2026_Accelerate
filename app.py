# ╔══════════════════════════════════════════════════╗
# ║  Sprout — The Aesthetic Visual Mapping OS        ║
# ║  Backend: Flask + Groq                           ║
# ╚══════════════════════════════════════════════════╝

import os
import json
import sqlite3
import hashlib
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = Flask(__name__)
import secrets
app.secret_key = secrets.token_hex(16)  # random every restart = sessions always clear

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# In-memory boards store (persists while server is running)
boards_store = {}

# ════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════
DB_PATH = os.path.join(os.path.dirname(__file__), "sprout.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT    NOT NULL,
                email    TEXT    UNIQUE NOT NULL,
                password TEXT    NOT NULL
            )
        """)
        conn.commit()

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

init_db()
MODEL  = "llama-3.3-70b-versatile"

SYSTEM = (
    "You are Lumi, a warm and creative AI companion inside Sprout, "
    "a cozy visual mapping app. Be helpful, specific, and delightful."
)


# ════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════
def ask(prompt, max_tokens=400):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def parse_json(text):
    clean = text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


# ════════════════════════════════════════
#  PAGE ROUTES
# ════════════════════════════════════════

@app.route("/")
def index():
    if not session.get("user"):
        return redirect(url_for("login"))
    if not session.get("mode"):
        return redirect(url_for("mode_select"))
    return render_template("index.html")

@app.route("/login")
def login():
    if session.get("user"):
        if session.get("mode"):
            return redirect(url_for("index"))
        return redirect(url_for("mode_select"))
    return render_template("login.html")

@app.route("/mode-select")
def mode_select():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template("mode_select.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ════════════════════════════════════════
#  AUTH ROUTES
# ════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def api_login():
    data     = request.json or {}
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"success": False, "error": "Please fill in all fields"}), 400
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT name, email FROM users WHERE email=? AND password=?",
            (email, hash_pw(password))
        ).fetchone()
    if row:
        session["user"] = {"email": row[1], "name": row[0]}
        session.pop("mode", None)
        return jsonify({"success": True, "user": {"email": row[1], "name": row[0]}})
    return jsonify({"success": False, "error": "Wrong email or password"}), 401


@app.route("/api/signup", methods=["POST"])
def api_signup():
    data     = request.json or {}
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not name or not email or not password:
        return jsonify({"success": False, "error": "Please fill in all fields"}), 400
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hash_pw(password))
            )
            conn.commit()
        session["user"] = {"email": email, "name": name}
        session.pop("mode", None)
        return jsonify({"success": True, "user": {"email": email, "name": name}})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Email already registered — try logging in!"}), 409


@app.route("/api/set-mode", methods=["POST"])
def api_set_mode():
    data = request.json or {}
    mode = data.get("mode", "")
    if mode in ("study", "content"):
        session["mode"] = mode
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid mode"}), 400


# ════════════════════════════════════════
#  AI — SHARED
# ════════════════════════════════════════

@app.route("/api/generate-ideas", methods=["POST"])
def generate_ideas():
    try:
        data         = request.json or {}
        topic        = data.get("topic", "")
        existing     = data.get("existing", [])
        mode         = data.get("mode", "study")
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
    except Exception as e:
        print(f"[generate-ideas error] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/expand-node", methods=["POST"])
def expand_node():
    try:
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
    except Exception as e:
        print(f"[expand-node error] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/refine-idea", methods=["POST"])
def refine_idea():
    try:
        data   = request.json or {}
        idea   = data.get("idea", "")
        parent = data.get("parent", "")
        prompt = (
            f"Refine and improve this idea: '{idea}'"
            + (f" (belongs to '{parent}')" if parent else "")
            + ". Make it more vivid and specific. Return ONLY the improved phrase (2-6 words). No punctuation at end."
        )
        return jsonify({"success": True, "refined": ask(prompt, max_tokens=60).strip(".")})
    except Exception as e:
        print(f"[refine-idea error] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ════════════════════════════════════════
#  AI — STUDY HUB
# ════════════════════════════════════════

@app.route("/api/study/explain", methods=["POST"])
def study_explain():
    try:
        data  = request.json or {}
        node  = data.get("node", "")
        topic = data.get("topic", "")
        prompt = (f"Explain '{node}' (part of {topic}) in 2-3 warm friendly sentences using one fun analogy. "
                  "Use 1-2 emojis. Under 80 words.")
        return jsonify({"success": True, "text": ask(prompt, max_tokens=200)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/study/quiz", methods=["POST"])
def study_quiz():
    try:
        data  = request.json or {}
        node  = data.get("node", "")
        topic = data.get("topic", "")
        prompt = (f"Give 3 quiz questions about '{node}' in the context of {topic}, easiest to hardest. "
                  "After each add a blank line then '✅ Answer: ...'. Friendly tone. Under 200 words.")
        return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/study/flashcards", methods=["POST"])
def study_flashcards():
    try:
        data  = request.json or {}
        node  = data.get("node", "")
        topic = data.get("topic", "")
        prompt = (f"Create 4 flashcards for '{node}' in the context of {topic}. "
                  "Format: 🃏 FRONT: [question]\n🌸 BACK: [answer]\n\nUnder 200 words.")
        return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/study/connect", methods=["POST"])
def study_connect():
    try:
        data  = request.json or {}
        node  = data.get("node", "")
        topic = data.get("topic", "")
        prompt = (f"Explain how '{node}' connects to other parts of {topic}. "
                  "What breaks if you skip it? What does mastering it unlock? "
                  "2-3 short paragraphs with emojis. Under 150 words.")
        return jsonify({"success": True, "text": ask(prompt, max_tokens=350)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ════════════════════════════════════════
#  AI — CREATIVE STUDIO
# ════════════════════════════════════════

@app.route("/api/content/script", methods=["POST"])
def content_script():
    try:
        data     = request.json or {}
        node     = data.get("node", "")
        topic    = data.get("topic", "")
        branches = data.get("branches", [])
        all_scenes = branches if branches else [node]
        scenes_str = ", ".join(all_scenes)
        prompt = (
            f"Write a 30-second TikTok script for a '{topic}' video that covers ALL of these scenes: {scenes_str}.\n"
            "The script must naturally flow through every single scene listed — not just one.\n"
            "Format:\n"
            "🎬 HOOK (0-3s): tease the whole day/journey, mention 1-2 specific scenes\n"
            f"📖 MIDDLE (3-25s): move through EACH scene ({scenes_str}) with a specific detail per scene\n"
            "✨ CTA (25-30s): wrap up the full journey, feel personal not promotional\n"
            "Under 220 words. Every scene must appear in the script."
        )
        return jsonify({"success": True, "text": ask(prompt, max_tokens=450)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/content/plan", methods=["POST"])
def content_plan():
    try:
        data     = request.json or {}
        node     = data.get("node", "")
        topic    = data.get("topic", "")
        branches = data.get("branches", [])
        all_scenes = branches if branches else [node]
        scenes_str = ", ".join(all_scenes)
        prompt = (
            f"Create a 7-day content posting plan for a creator making a '{topic}' series.\n"
            f"They have these specific scenes/moments to film: {scenes_str}.\n\n"
            "Rules:\n"
            "- Spread ALL the scenes across the 7 days — every scene must appear at least once\n"
            "- Some days can combine 2 scenes into one video\n"
            "- Do NOT invent new topics — only use the scenes listed above\n\n"
            "For each day:\n"
            "📅 Day N: Platform\n"
            "🎬 Video idea (must name the specific scene from the list)\n"
            "⚡ Hook (first 3s) — reference that exact scene\n"
            "🏷️ 3 hashtags\n\n"
            "Under 320 words."
        )
        return jsonify({"success": True, "text": ask(prompt, max_tokens=650)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/content/hooks", methods=["POST"])
def content_hooks():
    try:
        data     = request.json or {}
        node     = data.get("node", "")
        topic    = data.get("topic", "")
        branches = data.get("branches", [])
        all_scenes = branches if branches else [node]
        scenes_str = ", ".join(all_scenes)
        prompt = (
            f"Write 5 TikTok hooks (first 3 seconds) for a '{topic}' video.\n"
            f"The video covers ALL of these moments: {scenes_str}.\n"
            "Each hook should tease the full video — not just one scene.\n"
            "Label each: Curiosity / Shock / Relatability / FOMO / Humor\n"
            f"Mention at least 2 of these specific scenes per hook: {scenes_str}\n"
            "No generic filler — every hook must feel like it\'s about THIS specific video. Under 180 words."
        )
        return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/content/shotlist", methods=["POST"])
def content_shotlist():
    try:
        data     = request.json or {}
        node     = data.get("node", "")
        topic    = data.get("topic", "")
        branches = data.get("branches", [])
        all_scenes = branches if branches else [node]
        scenes_str = ", ".join(all_scenes)
        prompt = (
            f"Create a B-roll shot list for a '{topic}' video.\n"
            f"The video must cover ALL of these scenes: {scenes_str}.\n"
            f"Give at least one dedicated shot per scene, plus 1-2 transition shots between scenes.\n"
            "For each shot:\n"
            "📽️ Shot type (wide/close-up/POV/cutaway) | 🎯 Exact subject from the scene | ⏱️ Duration | 💭 Why it works\n"
            "Every scene in the list must have a shot. Under 220 words."
        )
        return jsonify({"success": True, "text": ask(prompt, max_tokens=450)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ════════════════════════════════════════
#  BOARDS — Save & Load
# ════════════════════════════════════════

@app.route("/api/boards/save", methods=["POST"])
def save_board():
    if not session.get("user"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    data  = request.json or {}
    nodes = data.get("nodes", {})
    topic = data.get("topic", "Untitled")
    mode  = data.get("mode", "study")
    board_id = str(uuid.uuid4())[:8]
    boards_store[board_id] = {
        "id":         board_id,
        "topic":      topic,
        "mode":       mode,
        "nodes":      nodes,
        "created_at": datetime.utcnow().isoformat()
    }
    return jsonify({"success": True, "id": board_id})


@app.route("/api/boards", methods=["GET"])
def list_boards():
    if not session.get("user"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    summaries = [
        {k: v for k, v in b.items() if k != "nodes"}
        for b in boards_store.values()
    ]
    return jsonify({"success": True, "boards": summaries})


@app.route("/api/boards/<board_id>", methods=["GET"])
def get_board(board_id):
    if not session.get("user"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    board = boards_store.get(board_id)
    if not board:
        return jsonify({"success": False, "error": "Board not found"}), 404
    return jsonify({"success": True, "board": board})


@app.route("/api/boards/<board_id>", methods=["DELETE"])
def delete_board(board_id):
    if not session.get("user"):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    if board_id not in boards_store:
        return jsonify({"success": False, "error": "Board not found"}), 404
    del boards_store[board_id]
    return jsonify({"success": True})


# ════════════════════════════════════════
#  RUN
# ════════════════════════════════════════
if __name__ == "__main__":
    app.run(debug=True, port=5000)
