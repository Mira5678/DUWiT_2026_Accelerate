# ╔══════════════════════════════════════════════════╗
# ║  Sprout — The Aesthetic Visual Mapping OS        ║
# ║  Backend: Flask + Groq                           ║
# ╚══════════════════════════════════════════════════╝

import os
import json
import sqlite3
import hashlib
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = Flask(__name__)
# ✅ Fixed: use a stable secret key so sessions survive Flask restarts
app.secret_key = os.environ.get("SECRET_KEY", "sprout-dev-secret-key")

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

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

MODEL = "llama-3.3-70b-versatile"

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
    # ✅ Always redirect to login first if not logged in
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
    # ✅ Clears session and sends user back to login
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
        data  = request.json or {}
        node  = data.get("node", "")
        topic = data.get("topic", "")
        prompt = (f"Write a 30-second TikTok script for '{node}' angle of a video about '{topic}'. "
                  "Format:\n🎬 HOOK (0-3s):\n📖 MIDDLE (3-25s):\n✨ CTA (25-30s):\nUnder 200 words.")
        return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/content/moodboard", methods=["POST"])
def content_moodboard():
    try:
        data  = request.json or {}
        node  = data.get("node", "")
        topic = data.get("topic", "")
        prompt = (f"Visual moodboard brief for '{node}' in a video about '{topic}':\n"
                  "🎨 COLOR PALETTE — 5 colorblind-friendly pastel hex codes with names\n"
                  "📷 VISUAL AESTHETIC — 3 style references\n"
                  "💡 LIGHTING MOOD\n🎥 CAMERA STYLE\n✨ OVERALL VIBE\nUnder 220 words.")
        return jsonify({"success": True, "text": ask(prompt, max_tokens=450)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/content/hooks", methods=["POST"])
def content_hooks():
    try:
        data  = request.json or {}
        node  = data.get("node", "")
        topic = data.get("topic", "")
        prompt = (f"5 TikTok hooks (first 3s) for '{node}' from a video about '{topic}'. "
                  "Label each: Curiosity/Shock/Relatability/FOMO/Humor. Under 200 words.")
        return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/content/shotlist", methods=["POST"])
def content_shotlist():
    try:
        data  = request.json or {}
        node  = data.get("node", "")
        topic = data.get("topic", "")
        prompt = (f"B-roll shot list for '{node}' in a video about '{topic}'. "
                  "5 shots: 📽️ Shot type | 🎯 Subject | ⏱️ Duration | 💭 Why it works. Under 200 words.")
        return jsonify({"success": True, "text": ask(prompt, max_tokens=400)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ════════════════════════════════════════
#  RUN
# ════════════════════════════════════════
if __name__ == "__main__":
    app.run(debug=True, port=5000)