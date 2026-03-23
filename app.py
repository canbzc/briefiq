import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from agents.requirements_agent import RequirementsAgent
from agents.risk_agent import RiskAgent
from agents.proposal_agent import ProposalAgent
from agents.cover_letter_agent import CoverLetterAgent
from agents.negotiation_agent import NegotiationAgent
from database import (
    init_db, save_analysis, get_recent, delete_analysis, update_status, get_stats,
    create_user, get_user_by_email, get_user_by_id, verify_password,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

# Flask-Login kurulumu
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

init_db()


# Flask-Login için User modeli
class User(UserMixin):
    def __init__(self, user_dict):
        self.id = user_dict["id"]
        self.username = user_dict["username"]
        self.email = user_dict["email"]


@login_manager.user_loader
def load_user(user_id):
    user = get_user_by_id(int(user_id))
    return User(user) if user else None


# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_email(email)
        if user and verify_password(user, password):
            login_user(User(user))
            return redirect(url_for("index"))
        error = "Invalid email or password."

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "GET":
        return redirect(url_for("login"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if len(password) < 6:
            error = "Password must be at least 6 characters."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        else:
            user = create_user(username, email, password)
            if user:
                login_user(User(user))
                return redirect(url_for("index"))
            else:
                error = "Email or username already in use."

    return render_template("login.html", reg_error=error, error=None)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ─── Ana Uygulama ─────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return render_template("index.html", username=current_user.username)


def _groq_error(e: Exception) -> str:
    msg = str(e)
    if "rate_limit" in msg.lower() or "429" in msg:
        return "Groq API rate limit exceeded. Please wait a moment and try again."
    if "api_key" in msg.lower() or "authentication" in msg.lower():
        return "Groq API key is missing or invalid. Check your .env file."
    if "connection" in msg.lower() or "timeout" in msg.lower():
        return "Could not reach Groq API. Check your internet connection."
    return msg


@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    data = request.get_json()
    brief = data.get("brief", "").strip()

    if not brief:
        return jsonify({"error": "Brief boş olamaz."}), 400

    try:
        requirements = RequirementsAgent().run(brief)
        risks = RiskAgent().run(requirements)
        proposal = ProposalAgent().run(requirements, risks)

        result = {"requirements": requirements, "risks": risks, "proposal": proposal}
        save_analysis(brief, result, user_id=current_user.id)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": _groq_error(e)}), 500


@app.route("/history")
@login_required
def history():
    return jsonify(get_recent(20, user_id=current_user.id))


@app.route("/history/<int:analysis_id>", methods=["DELETE"])
@login_required
def delete_history(analysis_id):
    delete_analysis(analysis_id, user_id=current_user.id)
    return jsonify({"ok": True})


@app.route("/history/<int:analysis_id>/status", methods=["PATCH"])
@login_required
def set_status(analysis_id):
    data = request.get_json()
    status = data.get("status")
    update_status(analysis_id, status, user_id=current_user.id)
    return jsonify({"ok": True})


@app.route("/stats")
@login_required
def stats():
    data = get_stats(current_user.id)
    return render_template("stats.html", username=current_user.username, stats=data)


@app.route("/cover_letter", methods=["POST"])
@login_required
def cover_letter():
    data = request.get_json()
    requirements = data.get("requirements")
    risks = data.get("risks")
    proposal = data.get("proposal")

    if not requirements or not risks or not proposal:
        return jsonify({"error": "Eksik veri."}), 400

    try:
        letter = CoverLetterAgent().run(requirements, risks, proposal, data.get("lang", "en"))
        return jsonify({"cover_letter": letter})
    except Exception as e:
        return jsonify({"error": _groq_error(e)}), 500


@app.route("/negotiate", methods=["POST"])
@login_required
def negotiate():
    data = request.get_json()
    requirements = data.get("requirements")
    risks = data.get("risks")
    proposal = data.get("proposal")

    if not requirements or not risks or not proposal:
        return jsonify({"error": "Eksik veri."}), 400

    try:
        script = NegotiationAgent().run(requirements, risks, proposal, data.get("lang", "en"))
        return jsonify({"script": script})
    except Exception as e:
        return jsonify({"error": _groq_error(e)}), 500


@app.errorhandler(404)
def not_found(e):
    if current_user.is_authenticated:
        return render_template("404.html", username=current_user.username), 404
    return render_template("404.html", username=None), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(debug=True)
