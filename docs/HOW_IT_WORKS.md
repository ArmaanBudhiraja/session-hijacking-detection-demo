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
    "screen_width":  "1440",
    "screen_height": "900",
    "timezone":      "Asia/Kolkata",
}
```

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
   |  JS collects fingerprint fields       |
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
   |                          │   Compare incoming fp vs stored fp
   |                          │   If mismatch_ratio > 0.5 → revoke
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
   |  JS collects THIS browser's fp fields |
   |── POST /demo/test-session             |
   |      {token: "abc123...", fp_*} ─────>|
   |                          ┌────────────┤
   |                          │ Look up SESSIONS[token]
   |                          │ Compare incoming fp vs original fp
   |                          │ mismatch_ratio > 0.5?
   |                          │   YES → revoke + log HIJACK_BLOCKED
   |                          │   NO  → log FP_MATCH (same browser)
   |                          └────────────┤
   |<── render result (hijack/match) ──────|
```

---

## Fingerprint Comparison Algorithm

```python
FINGERPRINT_FIELDS = ["user_agent", "screen_width", "screen_height", "timezone"]
MISMATCH_THRESHOLD = 0.5  # >50% fields must differ to flag

def _compare_fingerprints(original, incoming):
    mismatched = [f for f in FIELDS if original[f] != incoming[f]]
    ratio = len(mismatched) / len(FIELDS)
    return {
        "suspicious": ratio > MISMATCH_THRESHOLD,
        "mismatch_ratio": ratio,
        ...
    }
```

### Why >50%?

Using a majority threshold (>50%) prevents false positives from single-field noise (e.g., a browser updating its user-agent string). A genuine hijack from a different device typically causes all 4 fields to differ.

---

## Security Notes (Intentional Simplifications)

| Simplification | Real-World Equivalent |
|---|---|
| In-memory `SESSIONS` dict | Redis / database session store |
| `httponly=False` on cookie | Should be `True` (JS shouldn't read it) |
| No HTTPS | Tokens should only travel over TLS |
| 4-field fingerprint | Production systems use 10+ signals |
| No rate limiting | Brute-force of token space would be trivial |

These are intentional for demo clarity — not bugs.

---

## File-by-File Breakdown

### `app.py`

| Section | Lines | Purpose |
|---|---|---|
| In-memory stores | 28–31 | `SESSIONS` dict + `EVENT_LOG` list |
| Demo credentials | 36–37 | Hardcoded `student` / `student123` |
| `_hash_fingerprint()` | 48–50 | SHA-256 hash of fingerprint for display |
| `_compare_fingerprints()` | 53–67 | Core detection algorithm |
| `_log()` | 70–75 | Append to EVENT_LOG + print to console |
| `/login` route | 98–137 | Auth + fingerprint capture + token issuance |
| `/dashboard` route | 140–185 | Token validation + fingerprint re-check |
| `/demo/test-session` | 204–272 | Attacker simulation endpoint |
| `/api/events` | 275–280 | JSON event feed for dashboard auto-refresh |

### `templates/login.html`

Captures fingerprint via JavaScript on form submit:
```javascript
document.getElementById("fp_user_agent").value    = navigator.userAgent;
document.getElementById("fp_screen_width").value  = screen.width;
document.getElementById("fp_screen_height").value = screen.height;
document.getElementById("fp_timezone").value      = Intl.DateTimeFormat().resolvedOptions().timeZone;
```

### `templates/dashboard.html`

- Displays session token, fingerprint hash, and comparison result
- Auto-refreshes event log every 5 seconds via `fetch("/api/events")`
- "Copy Token" button writes token to clipboard for the demo

### `templates/test_session.html`

- Accepts a pasted token via POST form
- Collects the current browser's fingerprint via the same JS as login
- Shows a side-by-side fingerprint comparison table with match/mismatch per field
