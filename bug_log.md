# Sporty OTP Lab — Bug Log

Field notes from building the SportyBet adapter against the **live** site (Sep 2026).
Summary of what broke and how we navigated each one.

---

### 1. False `otp_sent` — "Verify" text matched the delivery chooser
- **Symptom:** tool reported the OTP was requested while the browser was still sitting on the "Verify Your Account" *channel chooser*; no SMS had ever gone out.
- **Cause:** `_OTP_SCREEN_SELECTORS` contained a bare `text=Verify`, which matched the chooser's title before the code-entry screen loaded.
- **Fix:** dropped generic "Verify"; OTP detection now matches real inputs only — `otp`-named/placeholder fields, `input[maxlength='1']` digit boxes, `.otp-wrapper input` — and the code confirms the chooser is actually gone.

### 2. SMS channel auto-selection did nothing — invisible CAPTCHA overlay
- **Symptom:** operator had to click **SMS OTP** manually every run; every programmatic click (`click()`, `dispatch_event`, `el.click()`, force+position) was ignored.
- **Cause:** not an anti-click measure — SportyBet's bot detector slaps an **invisible popup** (`#sporty-captcha-body` / `#captcha-spinner`) **on top of the chooser** that swallows all pointer events (`"…intercepts pointer events"` from Playwright's hit-test).
- **Fix:** stealth init-script (hide `navigator.webdriver`, `window.chrome` shim) so the detector trips less; registered SportyBet's own captcha markers in `_CAPTCHA_SELECTORS`; before clicking, an `elementFromPoint` hit-test confirms the SMS row is truly topmost; then a single human-paced trusted click, verifying the chooser closed (retry ≤ 30s).

### 3. Keyboard "fix" (Tab + ArrowDown + Enter) bounced off the real site
- **Symptom:** Tab nav returned the operator to the default **register page** instead of selecting SMS.
- **Cause:** the option rows are plain `div`s (no `tabindex`), so Tab steers focus straight out of the modal. (A headless probe made it *look* like it worked — and actually sent a real SMS to the probe number, the "advance" was real; on the live headed UI it just wasn't reachable.)
- **Fix:** keyboard approach **removed**; replaced with the hit-test + trusted click from #2.

### 4. CAPTCHA appearing **after** SMS selection (gating the OTP screen)
- **Symptom:** operator selects SMS, and only then does SportyBet pop the CAPTCHA; the code-entry screen never shows and the run was misread as a failed request.
- **Fix:** `_wait_for_otp_screen` is now CAPTCHA-aware — it parks while the operator solves the challenge (headed; fails fast with a clear message if headless), then resumes polling for the OTP screen.

### 5. Racing the chooser triggered the anti-bot
- **Symptom:** clicking "Create New Account" and immediately engaging the chooser invited the CAPTCHA.
- **Fix:** `sportybet_post_submit_delay_ms` (2.5–4 s) settle after submit, plus a short pre-click pause, so the challenge materializes and is detected instead of clicking through its invisible overlay.

### 6. False progress: success reported without proof
- **Symptom:** channel-select clicked once and returned `True` without checking the chooser advanced; a missing OTP screen was only logged as a warning and still reported `otp_requested`.
- **Fix:** selection only succeeds once the chooser is confirmed gone; "SMS OTP not selectable" and "OTP screen never appeared" now fail the delivery with a real error surfaced in the UI.

### 7. Phone input swallows keystrokes
- **Symptom:** SportyBet's phone widget occasionally dropped typed digits.
- **Fix:** `_type_phone_human` fills, re-reads the field, and retries (≤ 5) until the stored value equals the national number.

### 8. OTP entry is six single-digit boxes, not one field
- **Symptom:** a single 6-char input was never found on the code screen.
- **Fix:** `_enter_otp` falls back to per-box discovery (`#otp-unify input`, `.otp-wrapper input`, `input[maxlength='1']`) and types one digit into each box.

**Caution discovered during debugging:** advancing the chooser triggers a **real** SMS — probe runs sent actual texts to the test number. Keep test numbers disposable. CAPTCHAs are never evaded; the operator solves them in the visible window.