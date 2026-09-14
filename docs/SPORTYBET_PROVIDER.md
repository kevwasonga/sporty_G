# SportyBet provider — browser adapter for REAL OTP delivery

> Status: **implemented and the default provider** (`PROVIDER=sportybet`,
> `SPORTYBET_ENABLED=true`). This adapter drives a real browser at the
> country-specific SportyBet registration page, fills the form, and **SportyBet
> itself sends the real OTP to the phone**. The browser session stays open so
> the code you read from the phone can be fed back in and the account
> completed. Automatic account creation still requires the operator's explicit
> authorization — see `SPORTYBET_ENABLED`.

## What the success criterion now means

> *An OTP is legitimately delivered to the registered phone number.*

With `PROVIDER=sportybet` that criterion is met by SportyBet, not by us:

1. Operator types a phone number (+ country) in the UI and clicks Register.
2. A Chromium browser (headed by default) opens the country-specific register page.
3. The adapter fills phone and password with **randomized human keystroke
   timing** (no robotic instant fills).
4. It submits the form and picks the OTP channel (SMS default, auto-fallback to
   Voice/Telegram); **SportyBet SMSes a real OTP to the phone**.
5. The browser stays open, parked on the OTP screen; the operator reads the code
   from their phone and types it into the UI.
6. `complete_signup` feeds that code back into the SAME live browser session,
   presses verify, and the account is created.

The OTP code is **never** generated, stored, or displayed by us — it exists only
on the phone, which is exactly why this is a real-OTP flow.

## Country support

| Country | URL prefix | Register URL |
|---|---|---|
| Nigeria | `ng` | https://www.sportybet.com/ng/register |
| Kenya | `ke` | https://www.sportybet.com/ke/register |
| Ghana | `gh` | https://www.sportybet.com/gh/register |
| Tanzania | `tz` | https://www.sportybet.com/tz/register |
| Zambia | `zm` | https://www.sportybet.com/zm/register |
| South Africa | `za` | https://www.sportybet.co.za/za/register |
| Cameroon | `cm` | https://www.sportybet.co.cm/cm/register |
| Mozambique | `mz` | https://www.sportybet.co.mz/mz/register |

The UI picks the country; `_COUNTRY_PREFIX` in `app/providers/sportybet.py`
maps it to the register URL.

## Human-likeness (from `sporty.md`)

`app/providers/sportybet.py` implements the behavioural guidance in `sporty.md`:

| Signal | Implementation |
|---|---|
| Keystroke dynamics | char-by-char fill, 40–120ms per keystroke (`SPORTYBET_KEYSTROKE_MIN/MAX_MS`) |
| Inter-field pause | 120–400ms between fields |
| Form dwell | 400–1000ms before submit |
| Batch pacing | UI runs one registration at a time, 15–45s gap, countdown shown |
| OTP delivery latency | 20–60s random wait before marking `otp_sent` |

**Provisioning**

```bash
pip install playwright && playwright install chromium
```

## Selectors and robustness

SportyBet's form is JS-rendered. The adapter discovers fields by
`name`/`placeholder`/`id` patterns with multiple fallbacks:
`input[name*=First]`, `#firstName`, `.firstName`, etc. If the site changes, the
operator can pin selectors via env (`SPORTYBET_REGISTER_SELECTOR`, etc.). When a
field can't be found the adapter fails cleanly and marks the row `failed` with
the reason instead of hanging.

## Enabling (authorized use only)

Automated account creation on sportybet.com likely breaches **SportyBet's Terms
of Service without the operator's explicit authorization**. Enable only with
written operator sign-off for your competition environment. `PROVIDER` and
`SPORTYBET_ENABLED` already default to `sportybet`/`true`; to disable:

```bash
# api/.env
PROVIDER=demo
SPORTYBET_ENABLED=false
```

`app/providers/sportybet.py` refuses to run when `SPORTYBET_ENABLED` is false,
and `docs/SPORTYBET_PROVIDER.md` documents why (device fingerprinting research
condensed from `sporty.md`).

## What remains for a sanctioned competition build

- The final "enter OTP in SportyBet's verification screen" step is now wired:
  the browser session is kept open and the operator-typed code is fed back in.
- If selectors drift, pin them from the live page before the demo
  (`SPORTYBET_*_SELECTOR` env or `_run_browser` in `app/providers/sportybet.py`).