"""Discover the real input/button selectors on the SportyBet registration page.

Run once (headed) after `python -m playwright install chromium`:

    python tools/probe_sporty.py [--ng]

Probes https://www.sportybet.com/ke/ by default (Ke), or /ng/ with --ng.
Waits for the SPA to hydrate, then prints every input / button visible with
its name, id, placeholder, type and role text.
"""

import sys
import time

from playwright.sync_api import sync_playwright

COUNTRY = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("--ng", "--ke") else "--ke"
URL = "https://www.sportybet.com/ng/" if COUNTRY == "--ng" else "https://www.sportybet.com/ke/"


def main() -> None:
    headless = "--headless" in sys.argv
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(locale="en", viewport={"width": 1366, "height": 900})
        print(f"Opening {URL} …")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector(
                "input[name*=phone], input[name*=Phone], input[placeholder*=phone], input[type=tel], input[type=password], #username",
                timeout=45000,
            )
        except Exception:
            print("WARNING: form widgets did not appear (blocked / page changed)")
        time.sleep(3)

        page.screenshot(path=f"/tmp/opencode/sporty_probe_{URL.strip('/').split('/')[-1]}.png", full_page=True)

        print("---- INPUTS ----")
        for i, el in enumerate(page.locator("input").all()):
            try:
                info = {
                    "name": el.get_attribute("name") or "",
                    "id": el.get_attribute("id") or "",
                    "placeholder": el.get_attribute("placeholder") or "",
                    "type": el.get_attribute("type") or "",
                    "autocomplete": el.get_attribute("autocomplete") or "",
                    "inputmode": el.get_attribute("inputmode") or "",
                    "maxlength": el.get_attribute("maxlength") or "",
                    "visible": el.is_visible(),
                }
            except Exception:
                continue
            print(f"  [{i}] {info}")

        print("---- BUTTONS ----")
        for i, el in enumerate(page.locator("button").all()):
            try:
                txt = (el.inner_text() or "").strip().replace("\n", " ")[:60]
                print(f"  [{i}] <{txt}> visible={el.is_visible()} disabled={el.is_disabled()}")
            except Exception:
                continue

        print("---- TABS / LINKS (auth forms) ----")
        for sel in ["[role=tab]:has-text('Register')", "[role=tab]:has-text('Log')",
                    "a:has-text('Sign up')", "a:has-text('Register')", "[role=tab]:has-text('Sign')"]:
            try:
                n = page.locator(sel).count()
                print(f"  {sel!r}: {n}")
            except Exception:
                pass

        browser.close()


if __name__ == "__main__":
    main()