# ⚙️ How It Works — Technical Deep Dive

## Overview

The app is a single-file Flask backend (`app.py`) with Jinja2 HTML templates. There is **no database** — all state lives in two Python dicts in memory.

---

## Data Structures

### `SESSIONS` dict

```python
SESSIONS[token] = {
    "username":    str,       # e.g. "student"
    "fingerprint": dict,      # captured at login (see below)
    "fp_hash":     str,       # 16-char SHA-256 hex of fingerprint
    "created_at":  datetime,
    "status":      str,       # "active" | "suspicious" | "revoked"
}
```

### Fingerprint dict

```python
{
    "user_agent":    "Mozilla/5.0 (Macintosh; Intel...",
    "platform":      "MacIntel",
    "language":      "en-US",
    "screen_width":  "1440",
    "screen_height": "900",
    "timezone":      "Asia/Kolkata",
}
```

Six fields are tracked. All are collected client-side via JavaScript and submitted as hidden form fields on login and on the test-session page.

### `EVENT_LOG` list

A capped list (max 50 entries) of `(timestamp, event_type, message)` tuples. Displayed live on the dashboard, refreshed every 5 seconds via `/api/events`.

---

## Request Flow

### Login Flow

```
Browser                              Server (app.py)
   |                                       |
   |── GET /login ────────────────────────>|
   |<── render login.html ────────────────-|
   |                                       |
   |  [User clicks Submit]                 |
   |  JS collects 6 fingerprint fields     |
   |── POST /login {user,pass,fp_*} ──────>|
   |                          ┌────────────┤
   |                          │ Verify creds
   |                          │ Generate token (secrets.token_urlsafe)
   |                          │ Store SESSIONS[token] = {username, fp, ...}
   |                          │ Log LOGIN event
   |                          └────────────┤
   |<── Set-Cookie: session_token=<token> ─|
   |<── 302 Redirect → /dashboard ────────-|
```

### Dashboard Flow

```
Browser                              Server (app.py)
   |                                       |
   |── GET /dashboard ─────────────────────>|  (cookie sent automatically)
   |                          ┌────────────┤
   |                          │ Read session_token from cookie
   |                          │ Look up SESSIONS[token]
   |                          │ If fp params in query string:
   |                          │   Compare incoming fp vs stored fp (6 fields)
   |                          │   If mismatch_ratio > 0.15 → revoke
   |                          └────────────┤
   |<── render dashboard.html ─────────────|
   |                                       |
   |  [Page JS sends fp as query params]   |
   |── GET /dashboard?fp_user_agent=...───>|  (re-check fingerprint)
```

### Hijacking Simulation Flow

```
Attacker Browser                     Server (app.py)
   |                                       |
   |── GET /demo/test-session ────────────>|
   |<── render test_session.html ─────────-|
   |                                       |
   |  [Pastes stolen token, clicks Submit] |
   |  JS collects THIS browser's 6 fp fields|
   |── POST /demo/test-session             |
   |      {token: "abc123...", fp_*} ─────>|
   |                          ┌────────────┤
   |                          │ Look up SESSIONS[token]
   |                          │ Compare incoming fp vs original fp (6 fields)
   |                          │ mismatch_ratio > 0.15?
   |                          │   YES → revoke + log HIJACK_BLOCKED
   |                          │   NO  → log FP_MATCH (same browser)
   |                          └────────────┤
   |<── render result (hijack/match) ──────|
```

---

## Fingerprint Comparison Algorithm

```python
FINGERPRINT_FIELDS = ["user_agent", "platform", "language", "screen_width", "screen_height", "timezone"]
MISMATCH_THRESHOLD = 0.15  # >15% fields must differ to flag as suspicious

def _compare_fingerprints(original, incoming):
    matched    = [f for f in FINGERPRINT_FIELDS if original.get(f,"").strip() == incoming.get(f,"").strip()]
    mismatched = [f for f in FINGERPRINT_FIELDS if f not in matched]
    ratio = len(mismatched) / len(FINGERPRINT_FIELDS)
    return {
        "matched":        matched,
        "mismatched":     mismatched,
        "mismatch_ratio": round(ratio, 2),
        "suspicious":     ratio > MISMATCH_THRESHOLD,
    }
```

### Why >15%?

The threshold is set low (>15%) so that **even a single mismatched field** out of 6 triggers detection. Chrome and Firefox always produce different `user_agent` strings (1/6 ≈ 17%), which alone is enough to flag a cross-browser session. This is intentionally aggressive for demo clarity — a real system would tune this based on false-positive tolerance.

---

## Security Notes (Intentional Simplifications)

| Simplification | Real-World Equivalent |
|---|---|
| In-memory `SESSIONS` dict | Redis / database session store |
| `httponly=False` on cookie | Should be `True` (JS shouldn't read session cookies) |
| No HTTPS | Tokens should only travel over TLS |
| 6-field fingerprint | Production systems use 10+ signals (canvas, WebGL, fonts, etc.) |
| No rate limiting | Brute-force of token space would be trivial |
| Single hardcoded user | Real auth uses a user database with hashed passwords |

These are intentional for demo clarity — not bugs.

---

## File-by-File Breakdown

### `app.py`

| Section | Lines | Purpose |
|---|---|---|
| In-memory stores | 28–31 | `SESSIONS` dict + `EVENT_LOG` list |
| Demo credentials | 36–37 | Hardcoded `student` / `student123` |
| `FINGERPRINT_FIELDS` | 43 | 6-element list defining tracked fp fields |
| `MISMATCH_THRESHOLD` | 47 | Set to `0.15` — >15% triggers detection |
| `_hash_fingerprint()` | 50–52 | SHA-256 hash of fingerprint for display |
| `_compare_fingerprints()` | 55–69 | Core detection algorithm |
| `_log()` | 72–77 | Append to EVENT_LOG + print to console |
| `/login` route | 100–141 | Auth + fingerprint capture (6 fields) + token issuance |
| `/dashboard` route | 144–191 | Token validation + fingerprint re-check |
| `/demo/test-session` | 210–280 | Attacker simulation endpoint |
| `/api/events` | 283–288 | JSON event feed for dashboard auto-refresh |

### `templates/login.html`

Captures fingerprint via JavaScript on form submit (all 6 fields):
```javascript
document.getElementById("fp_user_agent").value    = navigator.userAgent;
document.getElementById("fp_platform").value      = navigator.platform;
document.getElementById("fp_language").value      = navigator.language;
document.getElementById("fp_screen_width").value  = screen.width;
document.getElementById("fp_screen_height").value = screen.height;
document.getElementById("fp_timezone").value      = Intl.DateTimeFormat().resolvedOptions().timeZone;
```

### `templates/dashboard.html`

- Displays session token, fingerprint hash, and per-field comparison result
- Auto-refreshes event log every 5 seconds via `fetch("/api/events")`
- "Copy Token" button writes token to clipboard for the demo

### `templates/test_session.html`

- Accepts a pasted token via POST form
- Collects the current browser's 6 fingerprint fields via the same JS as login
- Shows a side-by-side fingerprint comparison table with match/mismatch per field
- Uses `{% set card_mt = ... %}` Jinja2 variables for dynamic inline styles (avoids IDE CSS lint false positives from Jinja2 expressions inside `style="..."` attributes)

### `templates/blocked.html`

- Rendered when a fingerprint mismatch is detected on the dashboard route directly
- Tells the user their session was revoked and directs them to log in again
