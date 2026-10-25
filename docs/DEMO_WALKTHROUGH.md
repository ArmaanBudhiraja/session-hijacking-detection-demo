# 🧪 Demo Walkthrough — Step-by-Step Guide

This guide walks through the full session hijacking demonstration from start to finish.

---

## Prerequisites

- The app is running at `http://127.0.0.1:5050`
- You have two different browsers available (e.g., Chrome + Firefox), OR one browser + an incognito/private window

---

## Part 1 — Normal Login (Victim's Perspective)

### Step 1 — Open the app

Navigate to **http://127.0.0.1:5050** in **Browser A** (e.g., Chrome).

You'll be redirected to the login page automatically.

---

### Step 2 — Log in

Use the demo credentials:

| Field | Value |
|---|---|
| Username | `student` |
| Password | `student123` |

Click **Log In**.

> Behind the scenes, before the form is submitted, JavaScript silently captures your browser's fingerprint and appends it to the POST request as hidden fields.

---

### Step 3 — Explore the Dashboard

After login you'll see the **Protected Dashboard** with:

- ✅ **Session Information** — your username, session status, fingerprint status, creation time, and fingerprint hash
- 🖥️ **Browser Fingerprint** — the exact values captured at login (User Agent, Screen Resolution, Timezone)
- 🎛️ **Demo Controls** — your full session token + a "Copy Token" button
- 📋 **Server Event Log** — live log showing `LOGIN` event (auto-refreshes every 5s)

---

### Step 4 — Copy the Session Token

In the **Demo Controls** card, click **"Copy Token"**.

The full session token is now in your clipboard. This simulates what happens in a real attack when an attacker intercepts the cookie (e.g., via XSS, network sniffing, or physical access).

---

## Part 2 — Simulating the Attack (Attacker's Perspective)

### Step 5 — Open the Test Page in a Different Browser

Open **Browser B** (e.g., Firefox) and navigate to:

```
http://127.0.0.1:5050/demo/test-session
```

> **Why a different browser?** To produce a different fingerprint. Chrome and Firefox report different `User-Agent` strings, which is enough to cross the 50% mismatch threshold (1 out of 4 fields).
>
> Using a different device (phone vs laptop) will also work and usually mismatches all 4 fields.

---

### Step 6 — Paste the Token and Submit

1. Paste the copied token into the **"Session Token"** textarea
2. Click **"Test Session"**

> JavaScript again silently captures Browser B's fingerprint and submits it alongside the token.

---

### Step 7 — See the Detection Result

**Expected result:** 🚨 **"Hijacking Detected!"**

You'll see:
- A red alert: *"Suspicious session detected. Your browser fingerprint does not match the original session. Access blocked."*
- A **Fingerprint Comparison table** showing which fields matched vs mismatched
- The mismatch ratio (e.g., 75% — 3 out of 4 fields differ)
- Confirmation that the session has been revoked on the server

---

### Step 8 — Verify Revocation (Back in Browser A)

Switch back to **Browser A** (Chrome) and refresh the dashboard.

You'll be **kicked out** — redirected to the login page with the cookie cleared. The original victim's session is gone.

Check the **Server Event Log** on the login redirect — it will show:
```
HIJACK_BLOCKED  Session hijacking detected! Token abc12345... Mismatched: [user_agent, timezone, screen_width]. Session revoked.
```

---

## Part 3 — Baseline Test (Same Browser — No Detection)

To show the system works correctly when the **same** browser accesses the test page:

1. Copy the token from the dashboard (after a fresh login)
2. Open the test page in the **same browser** (new tab)
3. Paste the token and submit

**Expected result:** ✅ **"Fingerprint matched. This appears to be the same browser — no hijacking detected."**

This demonstrates the system doesn't produce false positives for legitimate same-device access.

---

## Event Types Reference

| Event Type | When It Fires |
|---|---|
| `LOGIN` | Successful login |
| `LOGIN_FAIL` | Wrong username or password |
| `FP_MATCH` | Fingerprint verified and matched |
| `SUSPICIOUS` | Mismatch detected on dashboard visit |
| `HIJACK_ATTEMPT` | Token submitted to test page but not found |
| `HIJACK_BLOCKED` | Hijacking detected — session revoked |
| `LOGOUT` | User manually logged out |

---

## Tips for Presentations

- **Side-by-side windows** work great: show the dashboard on one half, the test page in a different browser on the other
- The **event log auto-refreshes** every 5 seconds — the audience can watch the `HIJACK_BLOCKED` entry appear in real time
- Use the `/api/events` endpoint (`http://127.0.0.1:5050/api/events`) to show the raw JSON events as a bonus
- After a hijack demo, **log in again** to reset — the server generates a new token each time
