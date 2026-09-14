# Sporty OTP Lab

Hackathon cybersecurity project: an operator dashboard that takes a **Nigeria or
Kenya** phone number, generates a **strong, unique password** (or reuses an
operator-supplied one), triggers a **real SportyBet registration** that texts a
**real OTP** to the client's phone, and tracks the OTP → verification lifecycle
inline.

```
Phone ──► generate password ──► real SportyBet signup ──► OTP hits client's phone ──► operator reads code back ──► type code ──► verified
```

There is **no demo/simulated provider** and no "reveal" OTP: every OTP is the
real SMS that **SportyBet itself sends**. The operator reads the code back from
the client and enters it into the UI; the system feeds it into the **same live
browser session** to complete the signup.

SportyBet only requires a **phone number** and a **password** (no username, no
names). Supported countries: **Nigeria (+234)** and **Kenya (+254)**; anything
else is rejected at registration.

See [`api.md`](api.md) for the full API spec.

---

## Architecture (separation of concerns)

```
┌────────────────────┐        ┌─────────────────────┐        ┌─────────────────┐
│  UI (React + Vite) │  HTTP  │  API (Python/FastAPI)│  ORM   │  DB (SQLAlchemy) │
│  shadcn/ui         │ ─────► │  routers/ services/ │ ─────► │  SQLite/Postgres │
│  one-number form   │  JSON  │  providers/ security│        │  registrations   │
│  per-number table  │        │                     │        └─────────────────┘
└────────────────────┘        └─────────────────────┘
```

| Layer | Tech | Responsibility |
|---|---|---|
| `ui/` | React 18, Vite, TypeScript, Tailwind, shadcn/ui | country picker (Nigeria/Kenya) + phone + optional password, live status table, password reveal/copy, inline OTP entry |
| `api/` | Python, FastAPI, SQLAlchemy, Pydantic, Fernet | REST API, business rules, password generation, encryption at rest, provider dispatch |
| `db/` | SQLAlchemy ORM (SQLite default, Postgres-ready) | `registrations` row per number: phone, encrypted password, status, provider ref |

---

## Quick start

### 0. Prerequisites

- Python 3.11+ (built/tested on 3.14)
- Node.js 20+ and npm
- `playwright install chromium` (the SportyBet provider drives a real browser)

### 1. Backend

```bash
cd api
cp .env.example .env          # defaults: sportybet provider, SQLite, no auth
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium   # if not already installed

uvicorn app.main:app --port 8011
```

Recommended: set `ENCRYPT_KEY` so passwords are encrypted at rest. Generate a key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep `SPORTYBET_HEADLESS=false` on your desktop so the browser window is visible
(needed for CAPTCHA fallback); flip it to `true` for server runs.

### 2. Frontend

```bash
cd ui
npm install
npm run dev                  # http://localhost:5273, proxies /api -> 127.0.0.1:8011
```

Open http://localhost:5273, pick the country, enter the client's national
number, hit **Register & request OTP**. The row shows the generated password.
SportyBet texts the real code to the phone; type it back into the row and the
adapter feeds it into the same live browser to complete the signup.

### 3. Run the tests

```bash
cd api && pytest -q
```

### Optional: enable API auth

Set `API_TOKEN` in `api/.env`; every request then needs `Authorization: Bearer <token>`.

---

## How the real OTP flow works

1. `send_otp` spawns a headed Chromium worker pointed at the number's country
   URL (`https://www.sportybet.com/ng/` for +234, `https://www.sportybet.com/ke/`
   for +254). The page's register form already shows the correct dial-code
   prefix (`+234` / `+254`).
2. The worker opens the **Register** tab, types the **national digits** into the
   phone field and the password into **Set Password** (human-paced, 40–120ms/char).
3. It clicks **Create New Account**. SportyBet then shows a delivery chooser
   ("Please select how you'd like to receive your 6-digit code" — SMS / Voice /
   Telegram); the adapter **auto-selects SMS OTP (the top option)**, the only
   channel this lab uses, and waits for the OTP screen — meaning SportyBet
   accepted the registration and **queued the real SMS**.
4. The job parks the browser on the OTP screen and flips the row to `otp_sent`.
5. The operator reads the code from the client and enters it in the UI.
6. `complete_signup` feeds the code into the **same live session**, presses
   verify, and reports `otp_verified`.

Selectors were verified against the live SportyBet KE/NG register form
(static-anchored, see `app/providers/sportybet.py`).

### CAPTCHA fallback

If a challenge appears, the adapter pauses and the operator solves it in the
visible browser window (`SPORTYBET_CAPTCHA_TIMEOUT_SECONDS` window). We never
try to evade CAPTCHAs.

---

## Success-criteria checklist

- [x] Country-scoped registration — **Nigeria (+234)** and **Kenya (+254)** only
- [x] SportyBet needs only **phone + password** — no username/names anywhere
- [x] Password field **optional** — blank ⇒ strong CSPRNG password generated
  (meets SportyBet's rule: ≥8 chars, upper/lower/number)
- [x] Real OTPs only — sent by SportyBet to the client's phone; no demo, no reveal
- [x] Status lifecycle: `pending → otp_sent → otp_verified` (or `failed`)
- [x] OTP expiry, attempt limits, duplicate-number filtering
- [x] Passwords encrypted at rest when `ENCRYPT_KEY` is set

---

## Security considerations

- At-rest encryption (Fernet) when `ENCRYPT_KEY` is set; otherwise a loud
  startup warning is emitted.
- Optional bearer-token auth for the API.
- The UI is a single-operator tool (hackathon scope). For wider deployment:
  real auth + TLS, a managed DB, rate limiting, and CSRF protection.
- Authorized-use only. Registering accounts on live services is typically a
  ToS violation and can enable fraud; only drive real signups for clients who
  have explicitly requested it and with operator sign-off.