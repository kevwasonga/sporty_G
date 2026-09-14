# Architecture

## End-to-end flow

```
┌──────────────┐  1. POST /api/registrations/batch {numbers, password?, provider}
│   UI (React) │ ──────────────────────────────────────────────────────────────►┐
│ PhoneBatchForm│                                                                 v
└──────────────┘                                  ┌───────────────────────────────────────┐
                                                 │ API (FastAPI)                           │
2. normalize + validate numbers                    │  ├─ services/registration.create_batch │
   (digits only, 7–15 digits)                     │  │     - dedupe vs DB + within batch   │
                                                 │  │     - password = given  or  generate  │
                                                 │  │     - encrypt password (Fernet?)     │
                                                 │  └─ persist Registration(status=pending)│
                                                 └───────────────────────────────────────┘
                                                              │
┌──────────────┐  3. POST /api/registrations/{id}/send-otp    │
│   UI (React) │ ─────────────────────────────────────────────► v
│  RegistrationTable                                       ┌──────────────────────────────┐
│   · per-number row                                        │ services/registration.send_otp│
│   · status badge                                          │   └─ provider.send_otp()     │
│   · password reveal/copy                                  │        demo: → demo_otp      │
│   · OTP input + Verify                                    │        real: → provider_ref   │
└──────────────┘                                            │   store otp digest + expiry  │
         ▲                                                  │   status -> otp_sent          │
         │ 4. POST /{id}/verify-otp {otp}                   └──────────────────────────────┘
         └──────────────────────────────────────────────────────────┘
            demo: digest compare + provider.complete_signup
            real: forward otp + provider_ref to provider
            status -> otp_verified | failed
```

## Status state machine

```
              send-otp            verify-otp (correct)     verify-otp (bad xN / expired)
┌ pending ───────────► otp_sent ────────────────────────► otp_verified ────────────── (terminal)
│   │                    │   │                                   ▲
│   └── send-otp fails ──┴───┴── verify-otp wrong / expired ─────┴──► failed (terminal)
```

## Data model

`registrations`

| column | type | notes |
|---|---|---|
| id | int PK | |
| phone | str(20) unique | normalized digits, international format |
| password | str(512) null | encrypted when `ENCRYPT_KEY` set; decrypt for UI |
| status | str(20) | pending / otp_sent / otp_verified / failed |
| provider | str(40) | which adapter created this row |
| provider_ref | str(256) null | session/payload handle from a real provider |
| otp_hash | str(256) null | salted BLAKE2b of the demo OTP |
| otp_sent_at | datetime null | used for the TTL window |
| otp_attempts | int | capped at 5 |
| verified_at | datetime null | |
| error | str(512) null | last failure reason |
| created_at / updated_at | datetime | |

## Provider contract (`app/providers/base.py`)

```python
class ProviderAdapter(abc.ABC):
    name: str
    def send_otp(self, phone: str, password: str) -> SendResult: ...
    def complete_signup(self, phone, password, otp, provider_ref) -> CompleteResult: ...
```

Implementations chosen by `PROVIDER` env (see `app/providers/__init__.py`).
The services layer never talks to a platform directly — it calls the adapter,
so the UI/API/DB stay platform-agnostic.

## API reference

| Method | Path | Body / Query | Returns |
|---|---|---|---|
| POST | `/api/registrations/batch` | `{numbers: [], password?: str, provider?: str}` | `{created[], duplicates_skipped[], invalid_skipped[]}` |
| GET | `/api/registrations` | `?status=&page=&page_size=` | `RegistrationOut[]` |
| GET | `/api/registrations/{id}` | — | `RegistrationOut` |
| POST | `/api/registrations/{id}/send-otp` | — | `SendOtpResponse` (may include `demootp`) |
| POST | `/api/registrations/{id}/verify-otp` | `{otp}` | `VerifyOtpResponse` |
| GET | `/api/stats` | — | status counters + provider + password mode |

Interactive docs: http://localhost:8000/docs (FastAPI/OpenAPI).

## Security posts

- **`security.generate_password`** — `secrets`-based, ≥1 lower/upper/digit/symbol.
- **`security.hash_otp` / `check_otp`** — salted BLAKE2b + `hmac.compare_digest`.
- **`security.encrypt_secret` / `decrypt_secret`** — Fernet at-rest encryption.
- Optional bearer auth via `app/auth.py` guarded by `API_TOKEN`.
- CORS restricted to `CORS_ORIGINS` (default localhost:5173).