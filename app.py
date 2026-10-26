"""
Behavioral Fingerprint-Based Detection of Session Hijacking
College Demo — Flask backend
"""

import secrets
import hashlib
import datetime
from flask import (
    Flask, request, render_template,
    redirect, url_for, make_response, jsonify
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

# sessions[token] = {
#   "username": str,
#   "fingerprint": dict,
#   "fp_hash": str,
#   "created_at": datetime,
#   "status": "active" | "suspicious" | "revoked",
# }
SESSIONS: dict = {}

# Simple event log — list of (timestamp, event_type, message)
EVENT_LOG: list = []

# ---------------------------------------------------------------------------
# Demo credentials
# ---------------------------------------------------------------------------
DEMO_USERNAME = "student"
DEMO_PASSWORD = "student123"

# ---------------------------------------------------------------------------
# Fingerprint helpers
# ---------------------------------------------------------------------------

FINGERPRINT_FIELDS = ["user_agent", "platform", "language", "screen_width", "screen_height", "timezone"]
# Fraction of fields that must differ to flag as suspicious
# Chrome vs Firefox on same laptop: user_agent is ALWAYS different = 1/6 = 16.7%
# Setting threshold to 0.15 ensures any cross-browser access is detected
MISMATCH_THRESHOLD = 0.15


def _hash_fingerprint(fp: dict) -> str:
    raw = "|".join(str(fp.get(f, "")) for f in FINGERPRINT_FIELDS)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _compare_fingerprints(original: dict, incoming: dict) -> dict:
    matched = []
    mismatched = []
    for field in FINGERPRINT_FIELDS:
        if str(original.get(field, "")).strip() == str(incoming.get(field, "")).strip():
            matched.append(field)
        else:
            mismatched.append(field)
    ratio = len(mismatched) / len(FINGERPRINT_FIELDS)
    return {
        "matched": matched,
        "mismatched": mismatched,
        "mismatch_ratio": round(ratio, 2),
        "suspicious": ratio > MISMATCH_THRESHOLD,
    }


def _log(event_type: str, message: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    EVENT_LOG.append((ts, event_type, message))
    print(f"[{ts}] [{event_type}] {message}")
    if len(EVENT_LOG) > 50:
        EVENT_LOG.pop(0)


def _get_session_from_cookie():
    token = request.cookies.get("session_token")
    if not token:
        return None, None
    session = SESSIONS.get(token)
    return token, session


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    token, session = _get_session_from_cookie()
    if token and session and session["status"] == "active":
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == DEMO_USERNAME and password == DEMO_PASSWORD:
            fp = {
                "user_agent":    request.form.get("fp_user_agent", ""),
                "platform":      request.form.get("fp_platform", ""),
                "language":      request.form.get("fp_language", ""),
                "screen_width":  request.form.get("fp_screen_width", ""),
                "screen_height": request.form.get("fp_screen_height", ""),
                "timezone":      request.form.get("fp_timezone", ""),
            }

            token = secrets.token_urlsafe(32)
            SESSIONS[token] = {
                "username":   username,
                "fingerprint": fp,
                "fp_hash":    _hash_fingerprint(fp),
                "created_at": datetime.datetime.now(),
                "status":     "active",
            }

            _log("LOGIN",
                 f"Successful login for '{username}'. "
                 f"Token: {token[:8]}... FP hash: {_hash_fingerprint(fp)}")

            resp = make_response(redirect(url_for("dashboard")))
            resp.set_cookie(
                "session_token", token,
                httponly=False, samesite="Lax", max_age=3600
            )
            return resp
        else:
            error = "Invalid username or password."
            _log("LOGIN_FAIL",
                 f"Failed login attempt for username='{username}'.")

    return render_template("login.html", error=error)


@app.route("/dashboard", methods=["GET"])
def dashboard():
    token, session = _get_session_from_cookie()

    if not token or not session:
        return redirect(url_for("login"))

    if session["status"] in ("revoked", "suspicious"):
        resp = make_response(redirect(url_for("login")))
        resp.delete_cookie("session_token")
        return resp

    # Re-check fingerprint (passed as query params by the page JS on load)
    incoming_fp = {
        "user_agent":    request.args.get("fp_user_agent", request.user_agent.string),
        "platform":      request.args.get("fp_platform", ""),
        "language":      request.args.get("fp_language", ""),
        "screen_width":  request.args.get("fp_screen_width", ""),
        "screen_height": request.args.get("fp_screen_height", ""),
        "timezone":      request.args.get("fp_timezone", ""),
    }

    if any(request.args.get(f"fp_{k}") for k in ("user_agent", "platform", "language", "screen_width", "screen_height", "timezone")):
        comparison = _compare_fingerprints(session["fingerprint"], incoming_fp)
        if comparison["suspicious"]:
            session["status"] = "revoked"
            _log("SUSPICIOUS",
                 f"Fingerprint mismatch on dashboard for token {token[:8]}... "
                 f"Mismatched: {comparison['mismatched']}. Revoking.")
            resp = make_response(render_template("blocked.html"))
            resp.delete_cookie("session_token")
            return resp
        _log("FP_MATCH",
             f"Fingerprint matched for token {token[:8]}... "
             f"Matched: {comparison['matched']}.")
    else:
        comparison = {"matched": FINGERPRINT_FIELDS, "mismatched": [], "mismatch_ratio": 0.0, "suspicious": False}

    return render_template(
        "dashboard.html",
        username=session["username"],
        token=token,
        fp=session["fingerprint"],
        fp_hash=session["fp_hash"],
        comparison=comparison,
        created_at=session["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
        event_log=list(reversed(EVENT_LOG)),
    )


@app.route("/logout", methods=["POST"])
def logout():
    token, session = _get_session_from_cookie()
    if token and session:
        session["status"] = "revoked"
        _log("LOGOUT", f"User logged out. Token {token[:8]}... revoked.")
        SESSIONS.pop(token, None)
    resp = make_response(redirect(url_for("login")))
    resp.delete_cookie("session_token")
    return resp


# ---------------------------------------------------------------------------
# Demo-only endpoint: test a pasted token (no cookie needed)
# ---------------------------------------------------------------------------

@app.route("/demo/test-session", methods=["GET", "POST"])
def test_session():
    if request.method == "GET":
        return render_template("test_session.html", result=None)

    pasted_token     = request.form.get("token", "").strip()
    fp_user_agent    = request.form.get("fp_user_agent", "")
    fp_screen_width  = request.form.get("fp_screen_width", "")
    fp_screen_height = request.form.get("fp_screen_height", "")
    fp_timezone      = request.form.get("fp_timezone", "")

    if not pasted_token:
        return render_template("test_session.html", result={
            "status": "error",
            "message": "No token provided.",
        })

    session = SESSIONS.get(pasted_token)
    if not session:
        _log("HIJACK_ATTEMPT", "Test-session request with unknown/expired token.")
        return render_template("test_session.html", result={
            "status": "invalid",
            "message": "Token not found. It may have expired or been revoked already.",
        })

    if session["status"] in ("revoked", "suspicious"):
        _log("HIJACK_BLOCKED",
             f"Test-session request with already-revoked token {pasted_token[:8]}...")
        return render_template("test_session.html", result={
            "status": "revoked",
            "message": "This session has already been revoked or flagged as suspicious.",
        })

    incoming_fp = {
        "user_agent":    fp_user_agent,
        "platform":      request.form.get("fp_platform", ""),
        "language":      request.form.get("fp_language", ""),
        "screen_width":  fp_screen_width,
        "screen_height": fp_screen_height,
        "timezone":      fp_timezone,
    }

    comparison = _compare_fingerprints(session["fingerprint"], incoming_fp)

    if comparison["suspicious"]:
        session["status"] = "revoked"
        _log("HIJACK_BLOCKED",
             f"Session hijacking detected! Token {pasted_token[:8]}... "
             f"Mismatched: {comparison['mismatched']}. Session revoked.")
        return render_template("test_session.html", result={
            "status": "hijack_detected",
            "message": (
                "Suspicious session detected. "
                "Your browser fingerprint does not match the original session. "
                "Access blocked. Please log in again."
            ),
            "comparison": comparison,
            "original_fp": session["fingerprint"],
            "incoming_fp": incoming_fp,
        })
    else:
        _log("FP_MATCH",
             f"Test-session fingerprint matched for token {pasted_token[:8]}... "
             f"(same browser). Matched: {comparison['matched']}.")
        return render_template("test_session.html", result={
            "status": "match",
            "message": "Fingerprint matched. This appears to be the same browser — no hijacking detected.",
            "comparison": comparison,
            "original_fp": session["fingerprint"],
            "incoming_fp": incoming_fp,
        })


@app.route("/api/events", methods=["GET"])
def api_events():
    return jsonify([
        {"timestamp": e[0], "type": e[1], "message": e[2]}
        for e in reversed(EVENT_LOG)
    ])


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
