# 🔐 Session Hijacking Detection Demo

> **Behavioral Fingerprint-Based Detection of Session Hijacking**  
> A college-level demonstration built with Python (Flask) — no database, no external services, runs entirely in-memory.

---

## 📌 What This Project Does

This app demonstrates how **session hijacking attacks** work and how they can be detected using **browser fingerprinting**.

When a user logs in, the server records a "fingerprint" of their browser — things like screen resolution, timezone, and user-agent string. On every subsequent request, the server re-checks this fingerprint. If a stolen session token is used from a **different browser or device**, the fingerprints won't match, and the session is **automatically revoked**.

### Key Concepts Demonstrated

| Concept | Description |
|---|---|
| Session Token | A secret random string stored in a cookie — identifies the logged-in user |
| Session Hijacking | An attacker steals this token and tries to use it as if they were the victim |
| Browser Fingerprint | Unique traits of a browser: User-Agent, screen size, timezone |
| Mismatch Detection | If >50% of fingerprint fields differ → session flagged and revoked |

---

## 📁 Project Structure

```
session-hijacking-demo/
├── app.py                  # Flask backend — all logic lives here
├── requirements.txt        # Python dependencies (only Flask)
├── venv/                   # Python virtual environment
├── templates/
│   ├── login.html          # Login page — captures fingerprint on submit
│   ├── dashboard.html      # Protected page — shows token, fingerprint, event log
│   ├── test_session.html   # "Attacker" page — paste a stolen token here
│   └── blocked.html        # Shown when a session is revoked
└── static/
    └── style.css           # App styling
```

---

## 🚀 Quick Start

> **Port 5050 must be free.** If it's already in use, run on a different port:
> `python app.py` — or edit the port in `app.py` line 284.

```bash
# 1. Go to the project directory
cd /path/to/session-hijacking-demo

# 2. Activate the virtual environment
source venv/bin/activate

# 3. Install dependencies (already done if venv exists)
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Open your browser at → **http://127.0.0.1:5050**

**Demo credentials:** `student` / `student123`

---

## 🧪 Running the Hijacking Demo (Step-by-Step)

1. Open **http://127.0.0.1:5050** in **Browser A** (e.g., Chrome)
2. Log in with `student` / `student123`
3. On the dashboard, click **"Copy Token"** to copy the session token
4. Open **http://127.0.0.1:5050/demo/test-session** in **Browser B** (e.g., Firefox or a different device)
5. Paste the token and click **"Test Session"**
6. → The fingerprints will mismatch → **Hijacking detected! Session revoked.**

---

## ⚙️ How It Works

### 1. Login & Fingerprint Capture

When you submit the login form, JavaScript silently collects:

```
navigator.userAgent      → browser + OS string
screen.width / height    → display resolution
Intl.DateTimeFormat()    → timezone (e.g. "Asia/Kolkata")
```

These 4 values are sent to the server alongside your credentials and stored as your **session fingerprint**.

### 2. Session Token

After a successful login, the server:
- Generates a **cryptographically random token** (`secrets.token_urlsafe(32)`)
- Stores the session + fingerprint in memory (`SESSIONS` dict)
- Sets a cookie `session_token=<token>` in your browser (valid 1 hour)

### 3. Fingerprint Re-verification

Every time you visit `/dashboard`, the page JS sends your current fingerprint as query parameters. The server compares them against the stored fingerprint field by field:

```
matched_fields / total_fields → mismatch_ratio
if mismatch_ratio > 0.50 → SUSPICIOUS → session REVOKED
```

### 4. Hijacking Simulation (Test Page)

The `/demo/test-session` page accepts a **raw token** (no cookie needed). It collects the visiting browser's fingerprint and runs the same comparison — simulating what an attacker would face if they stole your token.

### 5. Detection Threshold

| Mismatched Fields | Mismatch Ratio | Result |
|---|---|---|
| 0 / 4 | 0% | ✅ Match — access granted |
| 1 / 4 | 25% | ✅ Match — access granted |
| 2 / 4 | 50% | ✅ Match — access granted (boundary) |
| 3 / 4 | 75% | 🚨 Suspicious — session revoked |
| 4 / 4 | 100% | 🚨 Suspicious — session revoked |

---

## 📡 API & Routes Reference

| Route | Method | Description |
|---|---|---|
| `/` | GET | Redirects to dashboard or login |
| `/login` | GET, POST | Login form + fingerprint capture |
| `/dashboard` | GET | Protected dashboard — shows session info |
| `/logout` | POST | Revokes session and clears cookie |
| `/demo/test-session` | GET, POST | Paste a stolen token and test hijacking |
| `/api/events` | GET | JSON feed of all server-side events |

---

## 🛠️ Troubleshooting

### Port 5050 is already in use

Find and kill the process using port 5050:

```bash
lsof -ti :5050 | xargs kill -9
```

Or run the app on a different port by editing [`app.py`](app.py) line 284:

```python
app.run(host="127.0.0.1", port=5051, debug=True)  # change 5050 → 5051
```

### Venv not activating

```bash
# If venv doesn't exist yet, create it first:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Hijacking not detected (same browser test)

If you open the test page in the **same browser**, your fingerprint will match — that's expected! Use a **genuinely different browser** (Chrome vs Firefox, or a different device) to see detection trigger.

---

## ⚠️ Disclaimer

This project is **for educational purposes only**. It runs entirely in-memory (all session data resets on server restart) and uses simplified fingerprinting. Do not use this code in production.
