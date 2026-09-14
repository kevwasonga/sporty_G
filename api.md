# Sporty OTP Lab — API Documentation

> **Project**: `sporty` — automated client registration on **sportybet.com**
> (Kenya `sportybet.com/ke/`, Nigeria `sportybet.com/ng/`)
> **Team**: Customer Care / Registration desk
> **Author**: Registered from the approved project plan (use as the official spec).

---

## 1. Purpose

Automate the manual client-registration workflow on SportyBet:

1. The operator enters a **phone number** (required) and optionally a **password**.
2. The system **generates a strong password** when none is given (meeting
   SportyBet's strength rules).
3. The system opens the SportyBet register form (headed browser) for the
   number's **country** — `sportybet.com/ng/` for +234, `sportybet.com/ke/` for
   +254 — fills **phone + password**, and submits. SportyBet sends a **real
   OTP via SMS** to the client's phone.
4. The operator reads the OTP back from the client and enters it.
5. The system feeds the OTP into the **same live browser session** to complete
   registration.
6. The operator emails the credentials to the client using their existing,
   already-automated email pipeline. **The API returns the generated password
   so it can be included in that email.**

> The email step is handled externally and is **out of scope** for this API.
> This API only manages phone → password → OTP → verify → credential output.

---

## 2. Architecture

```
┌──────────────┐   POST /api/registrations  {phone, password?}
│   UI (React) │ ─────────────────────────────────────────────────►┐
│ Registration │                                                  v
│    Form      │                          ┌───────────────────────────────┐
└──────────────┘                          │  API (FastAPI)                │
                                          │  ├─ generate_password() (opt) │
                                          │  ├─ persist Registration      │
                                          │  └─ return credentials incl.  │
                                          │     the PASSWORD              │
   POST /api/registrations/{id}/send-otp  └───────────────────────────────┘
   ─────────────────────────────────────────►  Browser worker (Playwright)
                                               ├─ open /ng/ or /ke/ signup
                                               ├─ fill phone (national digits) + password
                                               ├─ submit "Create New Account" → OTP screen
                                               └─ report back: otp_sent

   POST /api/registrations/{id}/verify-otp {otp}
   ─────────────────────────────────────────►  Feed OTP into the same LIVE
                                               browser session (sessionbus)
                                               ├─ enter OTP + confirm
                                               └─ report: verified | failed
```

### Status state machine

```
pending ──send-otp──► sending ──delivered──► otp_sent ──verify (correct)──► otp_verified (terminal)
   │                        │                   │  │
   │   send-otp fails ──────┴──── verify wrong / │  └── verify bad xN / expired ──► failed (terminal)
   └──────────────o────────────  expired ───────┘
```

| status | meaning |
|---|---|
| `pending` | row created, credentials generated, no OTP requested yet |
| `sending` | OTP request in flight (browser worker running) |
| `otp_sent` | SportyBet delivered the real SMS OTP to the phone — operator should collect it from the client |
| `otp_verified` | registration completed on SportyBet (terminal) |
| `failed` | delivery or verification failed (terminal; may be re-sent when `pending`/`failed`) |

---

## 3. Tech stack

**Backend**
- FastAPI + Uvicorn
- SQLAlchemy 2 (SQLite by default, Postgres ready)
- Pydantic v2 / pydantic-settings
- Playwright (Chromium) — drives the real SportyBet register form
- `cryptography` (Fernet) — passwords encrypted at rest
- `secrets` (CSPRNG) — password generation

**Frontend**
- React 18 + Vite + TypeScript
- Tailwind CSS, lucide-react icons
- shadcn-style component primitives

**Standards**
- Thread-safe bridge between API thread and browser worker (`sessionbus`)
- Optional bearer-token auth (`API_TOKEN`)

---

## 4. Data model — `registrations`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | autoincrement |
| `phone` | str(32) **unique** | normalized digits, e.g. `2348012345678` |
| `password` | str(128) | encrypted at rest (Fernet) when `ENCRYPT_KEY` set |
| `status` | str(24) | `pending/sending/otp_sent/otp_verified/failed` |
| `provider_ref` | str(64) nullable | live browser-session handle |
| `otp_hash` | str(256) nullable | only set by test fakes; real SportyBet OTPs are validated by SportyBet itself |
| `otp_sent_at` | datetime nullable | start of the TTL window |
| `otp_attempts` | int (default 0) | capped at **5** |
| `verified_at` | datetime nullable | |
| `error` | str(512) nullable | last failure reason |
| `created_at` / `updated_at` | datetime | UTC |

> No username, no first/last names: SportyBet only needs phone + password.

---

## 5. Password generation rules

Generated by `security.generate_password()` (CSPRNG via `secrets`):

- Length **≥ 8** (default **16**, configurable via `PASSWORD_LENGTH`)
- At least **1 uppercase** letter (`A–Z`)
- At least **1 lowercase** letter (`a–z`)
- At least **1 number** (`0–9`)
- At least **1 symbol** from `!@#$%^&*()-_=+[]{};:,.<>?`

These satisfy SportyBet's own rule (≥8 chars with upper/lower/number). If the
operator supplies a password it is used as-is (8–128 chars).

The password is generated server-side and **returned in the API response** (in
cleartext) so it can be emailed to the client.

---

## 6. Supported countries

**Nigeria (+234)** and **Kenya (+254)** only. Numbers with any other dial code
are rejected at registration with `422`.

The country also selects the signup URL:

| Dial code | Country | Signup URL |
|---|---|---|
| `234` | Nigeria | `https://www.sportybet.com/ng/` |
| `254` | Kenya | `https://www.sportybet.com/ke/` |

Opening the right country URL sets the register form's phone dial-code prefix
(`+234` on /ng/, `+254` on /ke/) automatically; the adapter types only the
**national digits** into the phone field.

---

## 7. Endpoints

Base URL: `http://localhost:8011` — interactive docs at `/docs` (OpenAPI/Swagger).

### 7.1 `POST /api/registrations`

Create a registration and generate credentials.

**Body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `phone` | string | **yes** | digits only; normalized. 7–15 digits; `+`, spaces, dashes stripped. Must start with a supported dial code. |
| `password` | string | no | optional; a strong password is auto-generated when omitted/blank |

**Supported countries** (dial codes): Nigeria `+234`, Kenya `+254`. Numbers
with any other dial code are rejected with `422`.

**Example**

```json
{
  "phone": "+234 801 234 5678",
  "password": ""
}
```

**Response `201 Created`**

```json
{
  "id": 12,
  "phone": "2348012345678",
  "password": "G7x#mQ2!vLp@9DsT",
  "status": "pending",
  "provider": "sportybet",
  "provider_ref": null,
  "error": null,
  "created_at": "2026-09-14T10:00:00Z",
  "updated_at": "2026-09-14T10:00:00Z"
}
```

| Field | Notes |
|---|---|
| `password` | **cleartext on purpose** — copy into the client email |

**Errors**

| Code | Detail |
|---|---|
| `422` | phone too short/long, not digits, unsupported country, password too short |
| `409` | phone already registered |

### 7.2 `GET /api/registrations`

List registrations, newest first.

**Query params**

| Param | Type | Default | Notes |
|---|---|---|---|
| `status` | string | — | filter: pending/sending/otp_sent/otp_verified/failed |
| `page` | int | 1 | 1-based |
| `page_size` | int | 100 | max 500 |

**Response** — `RegistrationOut[]` (as in 7.1, password decrypted server-side).

### 7.3 `GET /api/registrations/{id}`

Single registration. `404` when missing.

### 7.4 `POST /api/registrations/{id}/send-otp`

Start the real OTP flow. Marks the row `sending`, launches the headed-browser
worker against the number's country signup URL, and parks it on the OTP screen.
Returns immediately; the row flips to `otp_sent` when SportyBet accepts the
registration and queues the SMS.

**Response**

```json
{
  "id": 12,
  "phone": "2348012345678",
  "status": "sending",
  "provider_ref": "sp-...",
  "message": "OTP request started. SportyBet texts the code to the phone."
}
```

May be called on `pending` and `failed` rows (retry).

### 7.5 `POST /api/registrations/{id}/verify-otp`

Submit the OTP the operator read back from the client.

**Body**

```json
{ "otp": "482913" }
```

**Response**

```json
{
  "id": 12,
  "phone": "2348012345678",
  "status": "otp_verified",
  "message": "Account created on SportyBet."
}
```

Rules:
- Only valid when status is `otp_sent`.
- OTP must arrive within `OTP_TTL_SECONDS` (default 300s) of `otp_sent_at`.
- Max **5 attempts**; then the row fails.
- When `otp_verified`, the registration is complete.

### 7.6 `DELETE /api/registrations/{id}`

Delete a registration (e.g. to re-do a messed-up client).

**Response** `{ "deleted": 1 }`

### 7.7 `GET /api/stats`

**Response**

```json
{
  "total": 40,
  "pending": 4,
  "sending": 1,
  "otp_sent": 12,
  "verified": 21,
  "failed": 2,
  "provider": "sportybet",
  "password_mode": "generated"
}
```

### 7.8 `GET /api/health`

Health/root probe used by launchers and uptime checks.

```json
{ "app": "Sporty OTP Lab", "provider": "sportybet" }
```

### 7.9 `GET /` (UI)

When the UI was built (`ui/dist` present at startup), the root path serves the
React SPA from the same origin as the API — no separate frontend process needed
in production. All `/api/*` routes above still take priority. If `ui/dist` is
missing the API logs a warning and runs API-only.

---

## 8. Auth

Optional. When `API_TOKEN` is set in the environment, every request must send:

```
Authorization: Bearer <API_TOKEN>
```

A missing/wrong token returns `401`. When unset, the API is open (single-user
lab desktop tool).

---

## 9. Providers

Chosen via `PROVIDER` env. All implement `ProviderAdapter` (`providers/base.py`).

| `PROVIDER` | Behavior |
|---|---|
| `sportybet` | Real registration on sportybet.com (NG/KE) via Chromium. Real OTP arrives by SMS. **The code is never seen by us** — the operator reads it from the client. |

There is **no demo or SMS-gateway provider**: real OTPs from SportyBet are the
success criterion, and that's the only shipped adapter.

### Provider contract

```python
class ProviderAdapter(abc.ABC):
    name: str
    def send_otp(self, ctx: SendContext) -> SendResult: ...
    def complete_signup(self, phone, password, otp, provider_ref) -> CompleteResult: ...
```

### SportyBet provider (`providers/sportybet.py`)

Supported countries: **Nigeria (+234)** and **Kenya (+254)**. Any other dial
code is rejected at registration with `422`. The signup URL is picked per
country via `SPORTYBET_ONBOARDING_URL_NG/KE` (falling back to
`SPORTYBET_ONBOARDING_URL`).

Flow (selectors verified against the live NG/KE register form):

1. Launch **headed** Chromium.
2. Open the signup URL for the registration's country (`/ng/` or `/ke/`); the
   register form's dial-code prefix is already correct (`+234` / `+254`).
3. Open the **Register** tab.
4. Fill the phone field (**national digits** only) and the **Set Password**
   field with human-like typing (40–120ms per char). SportyBet requires no
   username or names.
5. Click **Create New Account** (the button enables once phone + password pass
   client-side validation). SportyBet shows a delivery chooser ("Please select
   how you'd like to receive your 6-digit code" — SMS / Voice / Telegram); the
   adapter picks **SMS OTP — the top option and the only channel used** — then
   SportyBet sends the SMS OTP and shows the OTP screen.
6. Wait for the OTP-input screen; report `otp_sent`.
7. Browser **stays open**, parked on the OTP input.
8. `complete_signup` feeds the operator-typed code into that same session and
   reports whether the account was created.
9. CAPTCHA: detected by selector heuristics → operator solves it in the visible
   browser window (`SPORTYBET_CAPTCHA_TIMEOUT_SECONDS` window).

### Session bus (`providers/sessionbus.py`)

Thread-safe handoff between the FastAPI request thread and the Playwright
browser worker — only `queue.Queue`s are shared, never browser objects.

| Method | Thread | Purpose |
|---|---|---|
| `report_delivery(ok, msg)` | browser worker | OTP request accepted? |
| `wait_delivery(timeout)` | API | block until above |
| `submit_otp(otp)` | API | push operator-typed code |
| `get_otp(timeout)` | browser worker | consume that code |
| `report_completion(ok, verified, msg)` | browser worker | final outcome |
| `wait_completion(timeout)` | API | block until outcome |

---

## 10. Configuration

`.env` (see `api/.env.example` for the full list).

| Variable | Default | Notes |
|---|---|---|
| `APP_NAME` | `Sporty OTP Lab` | shown in docs/root |
| `CORS_ORIGINS` | `http://localhost:5273` | comma-separated UI origins |
| `DATABASE_URL` | `sqlite:///./sporty.db` | |
| `PROVIDER` | `sportybet` | the only provider shipped (real SportyBet) |
| `SPORTYBET_ONBOARDING_URL` | `https://www.sportybet.com/ng/` | default signup URL (Nigeria) |
| `SPORTYBET_ONBOARDING_URL_NG` | — | per-country signup URL for Nigeria; falls back to `SPORTYBET_ONBOARDING_URL` |
| `SPORTYBET_ONBOARDING_URL_KE` | set | per-country signup URL for Kenya (`https://www.sportybet.com/ke/`); falls back to `SPORTYBET_ONBOARDING_URL` |
| `SPORTYBET_HEADLESS` | `false` | keep false for the operator to see/intervene |
| `SPORTYBET_CAPTCHA_TIMEOUT_SECONDS` | `600` | operator window to solve a CAPTCHA |
| `SPORTYBET_KEYSTROKE_MIN_MS` | `40` | human-typing floor |
| `SPORTYBET_KEYSTROKE_MAX_MS` | `120` | human-typing ceiling |
| `SPORTYBET_FORM_DELAY_MS` | `600` | pause before submit |
| `SPORTYBET_AFTER_SEND_MIN_MS` / `MAX_MS` | `30000`/`60000` | randomized wait after request before reporting `otp_sent` |
| `SPORTYBET_SEND_TIMEOUT_SECONDS` | `120` | max wait for browser to confirm delivery |
| `SPORTYBET_OTP_WINDOW_SECONDS` | `600` | how long the browser waits for the OTP |
| `API_TOKEN` | — | optional bearer token |
| `ENCRYPT_KEY` | — | Fernet key; empty → plaintext (warning logged) |
| `OTP_TTL_SECONDS` | `300` | OTP validity window |
| `PASSWORD_LENGTH` | `16` | generated-password length |

---

## 11. Running

### API

```bash
cd sporty/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env            # then edit
uvicorn app.main:app --port 8011
```

### UI

```bash
cd sporty/ui
npm install
npm run dev                       # http://localhost:5273
```

---

## 12. Operator workflow (customer care)

1. Open the UI or hit `POST /api/registrations` with the client's phone number
   (and optionally a password).
2. Copy the returned `password`.
3. Click **Register & request OTP**.
4. Wait for `otp_sent` (SportyBet texts the client).
5. Read the code back from the client on the phone.
6. Enter it → `otp_verified`.
7. Email the client their password (your existing automated email flow) — app
   login is at `https://www.sportybet.com/`.
8. Repeat for the next client.

---

## 13. Security notes

- Passwords generated with the `secrets` CSPRNG.
- At-rest encryption (Fernet) when `ENCRYPT_KEY` is set.
- Rate caps: `otp_attempts ≤ 5`; OTP TTL `300s`.
- Optional `Authorization: Bearer` gating.
- CORS restricted to `CORS_ORIGINS`.
- This tool registers real accounts on SportyBet. Use it only for clients who
  have explicitly requested registration and authorize it.