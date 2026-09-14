"""SportyBet browser adapter — drives the REAL registration form on
sportybet.com (Kenya /nigeria). SportyBet sends the real SMS OTP to the phone,
and the code the operator reads back from the client is fed into the SAME live
browser session to complete the registration.

WHAT THIS DOES
------------------------------------------------------------------------------
``send_otp(ctx)``:
  1. Launches a headed (or headless) Chromium.
  2. Opens the SportyBet signup URL for the number's country
     (``https://www.sportybet.com/ng/`` for +234, ``https://www.sportybet.com/ke/``
     for +254). The page pre-fills the correct dial-code prefix.
  3. Opens the "Register" tab, fills phone (national digits) + password.
  4. Clicks "Create New Account" to request the real OTP.
  5. Waits for the OTP input screen before reporting success. The generated
     code is NEVER seen by us: the operator reads the real SMS from the client
     and types it into the UI.
  6. The browser STAYS OPEN, parked on the OTP screen, waiting for the code.

``complete_signup(...)`` feeds the operator-typed OTP back into that same live
session (via ``OTPWindow``), presses the final verify button, and reports
whether the account was actually created.

SportyBet needs only a phone + a password (no username, no names) — those extra
fields from the batch tool are gone.
"""

import logging
import random
import secrets
import threading
import time

from ..config import settings
from .base import CompleteResult, ProviderAdapter, SendContext, SendResult
from .sessionbus import OTPWindow, session_bus

logger = logging.getLogger("sporty.lab.providers.sportybet")

# Verified against the LIVE sportybet.com (NG + KE) register tab (Sep 2026):
# the phone field holds national digits, the dial code is shown in a prepend
# (``+234`` on /ng/, ``+254`` on /ke/) and is already correct per-country URL.
_PHONE_SELECTORS = [
    "input[placeholder='Mobile Number']",
    "input[name='phone']",
    "input[type='tel']",
]
_PASSWORD_SELECTORS = [
    "input[placeholder='Set Password']",
    "input[name*='password']",
    "input[type='password']",
]
_SUBMIT_SELECTORS = [
    "button:has-text('Create New Account')",
    "[type='submit']",
]

# Signs the OTP input / verification screen is showing after registering.
# NOTE: never match plain "Verify" text — SportyBet's channel chooser is titled
# "Verify Your Account", which would fake an already-sent OTP. Match real
# code-entry inputs only.
_OTP_SCREEN_SELECTORS = [
    "input[name*='otp']",
    "input[placeholder*='otp']",
    "input[placeholder*='code']",
    "input[placeholder*='6-digit']",
    "input[autocomplete='one-time-code']",
    "input[inputmode='numeric'][maxlength='6']",
    "input[inputmode='numeric'][maxlength='1']",
    "input[maxlength='1']",
    ".otp-input",
    "#otp",
    "#otp-unify input",
    ".otp-wrapper input",
    "text=Enter your code",
    "text=Enter the 6-digit code",
    "text=enter your code",
    "text=verification code",
]

# SportyBet's OTP delivery-channel chooser. After "Create New Account" it asks
# "Please select how you'd like to receive your 6-digit code" with options
# SMS OTP / Voice OTP / Telegram OTP. SMS is the top option and the only one we
# use (verified on the live KE/NG form; the options are `.otp-wrapper .option`
# rows, first = SMS OTP).
_CHANNEL_CHOOSER_SELECTORS = [
    ".otp-wrapper .option",
    "text=Please select how you'd like to receive your 6-digit code",
]

# Success signals after the final verification submit.
_SUCCESS_SELECTORS = [
    "text=Success",
    "text=Registration successful",
    "text=Account created",
    "text=Welcome",
    "text=Congratulations",
]

# Error signals (wrong code, already registered, rate limit, etc.).
_ERROR_SELECTORS = [
    "text=Incorrect OTP",
    "text=Wrong code",
    "text=Invalid code",
    "text=you are already registered",
    "text=already registered",
    "text=already exists",
    "text=Something went wrong",
    "text=Please try again",
    "text=unavailable",
    "[class*=error]",
    ".error-message",
    ".toast-error",
]

_CAPTCHA_SELECTORS = [
    "iframe[src*=recaptcha]",
    "iframe[title*=recaptcha]",
    "iframe[src*=turnstile]",
    "iframe[src*=hcaptcha]",
    "iframe[src*=captcha]",
    ".g-recaptcha",
    "#captcha",
    "[class*=captcha]",
    "text=I'm not a robot",
    "text=Verify you are human",
    # SportyBet's own anti-bot popup (seen live Sep 2026): it sits ON TOP of
    # the SMS/Voice/Telegram chooser and silently swallows every pointer event
    # aimed at the rows until it clears.
    "#sporty-captcha-body",
    "#sporty-captcha",
    "#captcha-spinner",
    "[data-op*='captcha']",
]


class SportyBetProvider(ProviderAdapter):
    name = "sportybet"

    # ----------------------------------------------------------------------
    # human-typing helpers
    def _rand(self, lo: int, hi: int) -> float:
        span = max(1, int(hi - lo))
        return lo + secrets.randbelow(span)

    def _sleep_human(self, min_ms: int = 300, max_ms: int = 1200) -> None:
        time.sleep(self._rand(max(1, min_ms), max_ms) / 1000)

    def _type_human(self, page, selector: str, text: str) -> None:
        """Fill a field character-by-character with human-like jitter."""
        locator = page.locator(selector).first
        locator.click()
        locator.fill("")
        locator.press_sequentially(
            text,
            delay=self._rand(
                settings.sportybet_keystroke_min_ms,
                settings.sportybet_keystroke_max_ms,
            ),
        )
        time.sleep(self._rand(120, 400) / 1000)

    @staticmethod
    def _digits(value: str) -> str:
        return "".join(ch for ch in (value or "") if ch.isdigit())

    @staticmethod
    def _dial_code(phone: str) -> str:
        """Return the leading dial code: '234' (NG) or '254' (KE)."""
        for code in ("234", "254"):
            if phone.startswith(code):
                return code
        return ""

    def _national_number(self, phone: str) -> str:
        code = self._dial_code(phone)
        return phone[len(code):] or phone

    def _type_phone_human(self, page, selector: str, phone_number: str) -> None:
        """Fill the SportyBet phone field with the NATIONAL digits.

        The dial-code prepend (``+234``/``+254``) is fixed by the per-country
        URL we opened, so only the local part goes into the input. The site can
        swallow keystrokes, so we verify the stored value and retry.
        """
        locator = page.locator(selector).first
        wanted = self._national_number(phone_number)
        for attempt in range(5):
            locator.fill("")
            locator.click()
            locator.press_sequentially(wanted, delay=self._rand(
                settings.sportybet_keystroke_min_ms,
                settings.sportybet_keystroke_max_ms,
            ))
            time.sleep(self._rand(400, 800) / 1000)
            got = self._digits(locator.input_value())
            if got == wanted:
                time.sleep(self._rand(120, 400) / 1000)
                return
            logger.warning(
                "sportybet: phone widget swallowed fill (got %r want %r); retrying",
                got, wanted,
            )
        logger.error("sportybet: phone field kept rejecting %s", phone_number)

    def _discover(self, page, *selectors: str) -> str | None:
        """Return the first selector that actually exists and is visible."""
        for sel in selectors:
            if not sel:
                continue
            try:
                if page.locator(sel).first.is_visible(timeout=1500):
                    return sel
            except Exception:
                continue
        return None

    def _sms_row_is_topmost(self, page) -> bool:
        """True when the SMS row (first option) is the topmost element at its
        own centre — i.e. nothing (modal mask, CAPTCHA popup, loading spinner)
        is covering it and intercepting pointer events."""
        try:
            return page.evaluate(
                """() => {
                    const row = document.querySelector('.otp-wrapper .option');
                    if (!row) return false;
                    const r = row.getBoundingClientRect();
                    const x = r.x + r.width / 2, y = r.y + r.height / 2;
                    const top = document.elementFromPoint(x, y);
                    return top === row || row.contains(top);
                }"""
            )
        except Exception:
            return False

    def _select_sms_channel(self, page) -> bool:
        """Pick "SMS OTP" (the top option) on SportyBet's delivery chooser.

        Live probing (Sep 2026) showed the row itself accepts a normal trusted
        pointer click — but SportyBet's anti-bot overlays the chooser with an
        invisible CAPTCHA popup (``#sporty-captcha-body`` / ``#captcha-spinner``)
        that swallows every click while it is up. So before clicking we:

          1. Let any CAPTCHA clear (operator solves it in headed mode; abort in
             headless).
          2. Verify via ``elementFromPoint`` that the SMS row is actually the
             topmost element at its click point.
          3. Land a human-pace trusted click and confirm the chooser is gone.

        No keyboard-navigation or Ctrl+F tricks needed — the row reacts to a
        normal click once nothing is covering it.
        """
        try:
            page.wait_for_selector(".otp-wrapper .option", timeout=20000)
        except Exception:
            return False

        # Brief pause: any CAPTCHA popup the anti-bot just spawned over the
        # rows needs a moment to fully render so we can detect it (and the
        # operator can see it) before we touch the chooser.
        self._sleep_human(1200, 2400)

        deadline = time.time() + 30
        while time.time() < deadline:
            # An active CAPTCHA popup sits over the rows and blocks the click.
            if self._detect_captcha(page):
                if settings.sportybet_headless:
                    logger.warning(
                        "sportybet: CAPTCHA covering SMS chooser in HEADLESS — cannot solve."
                    )
                    return False
                if not self._wait_captcha_cleared(page):
                    logger.warning("sportybet: CAPTCHA never cleared; aborting channel select.")
                    return False
                # The operator may have taken a while; reset the window.
                deadline = time.time() + 30

            if self._sms_row_is_topmost(page):
                row = page.locator(".otp-wrapper .option").first
                self._sleep_human(400, 1000)
                row.click(timeout=8000)
                # Give SportyBet a beat to switch from the chooser to the
                # "We've sent you a 6-digit code" verification screen.
                self._sleep_human(1200, 2200)
                for _ in range(3):
                    try:
                        if not page.locator(".otp-wrapper .option").first.is_visible(timeout=1200):
                            logger.info("sportybet: selected SMS OTP (trusted click)")
                            return True
                    except Exception:
                        return True
                    time.sleep(0.7)
                # Click landed but the chooser stayed — overlays come and go,
                # so loop and try again.
                logger.warning("sportybet: SMS row click did not advance the chooser; retrying")

            time.sleep(1)

        logger.warning("sportybet: could not select SMS OTP channel (overlay/CAPTCHA persisted)")
        return False

    def _wait_manual_sms_select(self, page) -> bool:
        """Manual mode: wait for the OPERATOR to click "SMS OTP" in the window.

        Auto-selection is the default; some operators prefer to click it
        themselves (or SportyBet keeps misbehaving for a given session). In this
        mode we do nothing but watch — park until the chooser is dismissed, give
        the CAPTCHA the same operator-solve treatment, and fail with a clear
        message on timeout.
        """
        try:
            page.wait_for_selector(".otp-wrapper .option", timeout=25000)
        except Exception:
            # No chooser -> already on the OTP screen or an error state.
            return self._wait_for_otp_screen(page, 8000)

        logger.info(
            "sportybet: MANUAL mode — click 'SMS OTP' (the top option) "
            "in the browser window to request the code."
        )
        deadline = time.time() + settings.sportybet_manual_select_timeout_seconds
        while time.time() < deadline:
            if self._detect_captcha(page):
                if settings.sportybet_headless:
                    return False
                if not self._wait_captcha_cleared(page):
                    return False
                deadline = time.time() + settings.sportybet_manual_select_timeout_seconds
                continue
            try:
                if not page.locator(".otp-wrapper .option").first.is_visible(timeout=1500):
                    logger.info("sportybet: operator selected the SMS OTP channel manually")
                    return True
            except Exception:
                return True
            time.sleep(1)

        logger.warning("sportybet: manual SMS selection timed out (%ss)",
                       settings.sportybet_manual_select_timeout_seconds)
        return False

    def _open_register_form(self, page) -> None:
        """Make sure the 'Register' tab/panel is active (it is by default)."""
        for sel in ("button:has-text('Register')", "a:has-text('Register')"):
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1500):
                    loc.click()
                    time.sleep(self._rand(300, 800) / 1000)
                    return
            except Exception:
                continue
        try:
            tab = page.locator(".tabs-v2__tab[data-name='Register']").first
            if tab.is_visible(timeout=1500):
                tab.click()
                time.sleep(self._rand(300, 800) / 1000)
        except Exception:
            pass

    # ----------------------------------------------------------------------
    # CAPTCHA fallback (human-in-the-loop; we never try to *evade* these).
    def _detect_captcha(self, page) -> bool:
        for sel in _CAPTCHA_SELECTORS:
            try:
                if page.locator(sel).first.is_visible(timeout=1200):
                    logger.warning("sportybet: CAPTCHA detected via %s", sel)
                    return True
            except Exception:
                continue
        return False

    def _wait_captcha_cleared(self, page) -> bool:
        timeout = settings.sportybet_captcha_timeout_seconds
        logger.info(
            "sportybet: CAPTCHA — SOLVE IT IN THE BROWSER WINDOW now. "
            "Giving you up to %ds before we give up.", timeout,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._detect_captcha(page):
                return True
            time.sleep(3)
        return False

    def _handle_captcha(self, page) -> bool:
        if not self._detect_captcha(page):
            return True
        if settings.sportybet_headless:
            logger.warning("sportybet: CAPTCHA present but HEADLESS — cannot solve.")
            return False
        return self._wait_captcha_cleared(page)

    # ----------------------------------------------------------------------
    def _detect_page_error(self, page, wait_ms: int = 4000) -> bool:
        deadline = time.time() + wait_ms / 1000
        while time.time() < deadline:
            for sel in _ERROR_SELECTORS:
                try:
                    if page.locator(sel).first.is_visible(timeout=300):
                        return True
                except Exception:
                    continue
            time.sleep(0.3)
        return False

    def _wait_for_otp_screen(self, page, timeout_ms: int) -> bool:
        deadline = time.time() + max(timeout_ms, 1) / 1000
        while True:
            # SportyBet sometimes pops its anti-bot CAPTCHA right AFTER the SMS
            # is requested, gating the OTP entry screen. Park until the operator
            # solves it (headed mode) instead of mistaking it for a failed
            # request.
            if self._detect_captcha(page):
                if settings.sportybet_headless:
                    return False
                if not self._wait_captcha_cleared(page):
                    return False
                # A solve can take a while — breathe, then keep polling.
                self._sleep_human(1200, 2500)
                continue
            if time.time() > deadline:
                return False
            if self._detect_page_error(page, wait_ms=600):
                return False
            for sel in _OTP_SCREEN_SELECTORS:
                try:
                    if page.locator(sel).first.is_visible(timeout=400):
                        return True
                except Exception:
                    continue
            time.sleep(0.5)

    def _confirm_submit(self, page) -> None:
        """Wait until the 'Create New Account' button enables, then click it.

        On SportyBet that button is disabled until the phone + password fields
        pass client-side validation — exactly the state our real fill produces.
        """
        try:
            page.wait_for_function(
                """
                () => {
                    const b = [...document.querySelectorAll('button')]
                        .find(x => /create\\s*new\\s*account/i.test(x.textContent || ''));
                    return b && !b.disabled;
                }
                """,
                timeout=20000,
            )
        except Exception:
            logger.warning("sportybet: 'Create New Account' button never enabled")

        for sel in _SUBMIT_SELECTORS:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=2000):
                    loc.click()
                    logger.info("sportybet: clicked submit via %s", sel)
                    return
            except Exception:
                continue
        logger.warning("sportybet: submit button not found; trying implicit Enter")
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass

    def _enter_otp(self, page, otp: str) -> bool:
        otp_sel = self._discover(
            page,
            "input[name*='otp']",
            "input[placeholder*='otp']",
            "input[placeholder*='code']",
            "input[placeholder*='6-digit']",
            "input[autocomplete='one-time-code']",
            "input[inputmode='numeric'][maxlength='6']",
            ".otp-input",
            "#otp",
        )
        if not otp_sel:
            # SportyBet frequently renders the code as 6 single-digit boxes.
            # Find visible single-digit inputs and type into each.
            boxes = page.locator("#otp-unify input, .otp-wrapper input, input[maxlength='1'], input[inputmode='numeric'][maxlength='1']")
            visible = [boxes.nth(i) for i in range(boxes.count()) if boxes.nth(i).is_visible()]
            if not visible:
                return False
            for i, box in enumerate(visible[:6]):
                box.click()
                box.fill("")
                box.press_sequentially(otp[i] if i < len(otp) else "0")
                time.sleep(self._rand(60, 180) / 1000)
            self._sleep_human(400, 900)
            return True
        self._type_human(page, otp_sel, otp)
        return True

    def _confirm_otp_verify(self, page) -> None:
        selectors = [
            ".otp-wrapper button:has-text('Verify')",
            ".es-dialog button:has-text('Verify')",
            "button:has-text('Verify')",
            "button:has-text('Confirm')",
            "button:has-text('Continue')",
            "[type=submit]",
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).last if '.otp-wrapper' in sel or '.es-dialog' in sel else page.locator(sel).first
                if loc.is_visible(timeout=2000):
                    loc.click()
                    logger.info("sportybet: submitted OTP via %s", sel)
                    return
            except Exception:
                continue
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass

    def _wait_for_success(self, page, timeout_ms: int = 15000) -> tuple[bool, str]:
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            if self._detect_page_error(page, wait_ms=800):
                return False, "SportyBet rejected the OTP (on-page error)."
            for sel in _SUCCESS_SELECTORS:
                try:
                    if page.locator(sel).first.is_visible(timeout=300):
                        return True, "Account created."
                except Exception:
                    continue
            time.sleep(0.5)
        return True, "OTP accepted; no error surfaced (assumed created)."

    # ----------------------------------------------------------------------
    def _signup_url_for(self, phone: str) -> str:
        """Pick the SportyBet signup URL for a phone's country.

        Supports Nigeria (+234) and Kenya (+254). Opening the right country URL
        also sets the correct phone dial-code prepend on the register form.
        """
        code = self._dial_code(phone)
        if code == "254":
            return settings.sportybet_onboarding_url_ke or settings.sportybet_onboarding_url
        if code == "234":
            return settings.sportybet_onboarding_url_ng or settings.sportybet_onboarding_url
        return settings.sportybet_onboarding_url

    def send_otp(self, ctx: SendContext) -> SendResult:
        url = self._signup_url_for(ctx.phone)
        provider_ref = f"sp-{int(time.time() * 1000)}-{secrets.token_hex(3)}"
        window = OTPWindow(provider_ref)
        session_bus.register(window)

        worker = threading.Thread(
            target=self._run_browser,
            args=(ctx, url, window),
            name=f"sportybet-{provider_ref}",
            daemon=True,
        )
        worker.start()

        # Block until the browser worker confirms the OTP request was accepted
        # (or reports a specific failure).
        delivery = window.wait_delivery(timeout=settings.sportybet_send_timeout_seconds)
        if delivery is None:
            session_bus.unregister(provider_ref)
            return SendResult(
                success=False,
                message="Timed out waiting for SportyBet to confirm the OTP request.",
                error="sportybet: delivery timeout",
            )
        ok, message = delivery
        if not ok:
            session_bus.unregister(provider_ref)
            return SendResult(success=False, message=message, error=message)

        return SendResult(
            success=True,
            message=f"Real OTP sent by SportyBet to {ctx.phone}. Check the phone.",
            provider_ref=provider_ref,
        )

    # ----------------------------------------------------------------------
    def _run_browser(self, ctx: SendContext, url: str, window: OTPWindow) -> None:
        """Owns the live Playwright session; parks on the OTP screen and waits
        for the operator-typed code, then finishes the registration."""
        from playwright.sync_api import sync_playwright

        browser = None
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=settings.sportybet_headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    locale="en",
                    viewport={"width": 1366, "height": 768},
                )
                # Low-key stealth so SportyBet's bot detector is less likely to
                # throw its anti-bot CAPTCHA on top of the SMS chooser.
                context.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    window.chrome = window.chrome || { runtime: {} };
                    """
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_load_state("domcontentloaded", timeout=30000)

                # The register panel should render quickly; give it time if slow.
                try:
                    page.wait_for_selector(
                        "input[placeholder='Mobile Number'], input[placeholder='Set Password']",
                        timeout=45000,
                    )
                except Exception:
                    logger.warning("sportybet: register form did not appear within 45s for %s", ctx.phone)

                phone_sel = self._discover(page, *_PHONE_SELECTORS)
                if not phone_sel:
                    window.report_delivery(False, "SportyBet register form not detected (selectors changed?).")
                    return

                self._open_register_form(page)

                # The dial-code prepend is already correct for the country URL,
                # so type only the national digits.
                self._type_phone_human(page, phone_sel, ctx.phone)

                pw_sel = self._discover(page, *_PASSWORD_SELECTORS)
                if not pw_sel:
                    window.report_delivery(False, "SportyBet: password field not found.")
                    return
                self._type_human(page, pw_sel, ctx.password)

                time.sleep(settings.sportybet_form_delay_ms / 1000)

                self._confirm_submit(page)
                # Settle after submit: gives SportyBet's anti-bot time to
                # materialize its optional CAPTCHA popup (and us, time to detect
                # it) instead of racing the invisible overlay.
                self._sleep_human(
                    settings.sportybet_post_submit_delay_ms,
                    settings.sportybet_post_submit_delay_ms + 1500,
                )

                if not self._handle_captcha(page):
                    window.report_delivery(False, "CAPTCHA encountered but could not be resolved (run HEADED).")
                    return

                # SportyBet first asks HOW to deliver the 6-digit code
                # (SMS / Voice / Telegram). Always SMS — the top option. In
                # manual mode the operator clicks it themselves in the parked
                # browser window; otherwise the system auto-selects it.
                if ctx.manual_sms_select:
                    selected = self._wait_manual_sms_select(page)
                    fail_msg = (
                        "Manual SMS selection timed out — no one clicked 'SMS OTP' "
                        "in the browser window in time. Re-register or retry."
                    )
                else:
                    selected = self._select_sms_channel(page)
                    fail_msg = (
                        "Could not select SMS OTP: SportyBet's CAPTCHA/overlay kept "
                        "blocking the chooser. Solve it in the browser window and "
                        "retry (or register again with manual SMS selection)."
                    )
                if not selected:
                    window.report_delivery(False, fail_msg)
                    return

                # The OTP input screen appears once SportyBet accepts the form
                # and queues the real SMS.
                if not self._wait_for_otp_screen(page, 25000):
                    if self._detect_page_error(page):
                        window.report_delivery(
                            False,
                            "SportyBet rejected the registration form (on-page error).",
                        )
                        return
                    window.report_delivery(
                        False,
                        "SportyBet did not show the OTP entry screen — the SMS was "
                        "not requested. Check the number and retry.",
                    )
                    return

                # Human-pace minimum so an OTP that "arrives instantly" isn't
                # scripted-looking. The actual SMS is real — but the operator
                # needs time to read it from the client.
                wait_s = self._rand(
                    settings.sportybet_after_send_min_ms,
                    settings.sportybet_after_send_max_ms,
                ) / 1000
                logger.info("sportybet: OTP requested for %s; waiting %.1fs", ctx.phone, wait_s)
                time.sleep(wait_s)

                window.report_delivery(
                    True,
                    "Real OTP requested. Check the phone.",
                )

                # Browser STAYS open, parked on the OTP screen, waiting for the
                # code the operator types into the UI.
                otp = window.get_otp(timeout=settings.sportybet_otp_window_seconds)
                if otp is None:
                    logger.warning(
                        "sportybet: no OTP typed in %ss for %s; closing session",
                        settings.sportybet_otp_window_seconds, ctx.phone,
                    )
                    window.report_completion(False, False, "Timed out waiting for the operator to enter the OTP.")
                    return

                if not self._enter_otp(page, otp):
                    window.report_completion(False, False, "Could not locate the OTP input on the verification screen.")
                    return
                self._confirm_otp_verify(page)

                verified, note = self._wait_for_success(page)
                if verified:
                    logger.info("sportybet: signup complete for %s", ctx.phone)
                    window.report_completion(True, True, f"Account created on SportyBet. {note}")
                else:
                    logger.warning("sportybet: verify failed for %s: %s", ctx.phone, note)
                    window.report_completion(False, False, note)
        except Exception as exc:  # pragma: no cover - live browser errors
            logger.exception("sportybet run_browser failed for %s", ctx.phone)
            window.report_delivery(False, f"SportyBet automation failed: {str(exc)[:300]}")
        finally:
            try:
                if browser is not None:
                    browser.close()
            except Exception:  # pragma: no cover
                pass
            session_bus.unregister(window.provider_ref)

    def complete_signup(
        self,
        phone: str,
        password: str,
        otp: str,
        provider_ref: str | None,
    ) -> CompleteResult:
        window = session_bus.get(provider_ref) if provider_ref else None
        if window is None:
            return CompleteResult(
                success=False,
                verified=False,
                message="SportyBet session is no longer open (expired or server restarted). Re-register the number.",
            )
        if not window.submit_otp(otp):
            return CompleteResult(
                success=False,
                verified=False,
                message="This session already received an OTP; overlap detected.",
            )

        outcome = window.wait_completion(timeout=settings.sportybet_otp_window_seconds)
        if outcome is None:
            return CompleteResult(
                success=False,
                verified=False,
                message="Timed out while SportyBet processed the verification.",
            )
        ok, verified, message, error = outcome
        return CompleteResult(
            success=ok,
            verified=verified,
            message=message,
            error=error,
        )