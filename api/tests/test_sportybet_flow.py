"""Unit tests for the live-session bridge used by the SportyBet provider.

The real provider drives a headed Chromium (not available on CI). These tests
verify the OTPWindow/SessionBus hand-off contract that send_otp and
complete_signup rely on: delivery reporting, operator OTP submission, and
completion reporting.
"""

import threading
import time

import pytest

from app.providers.sessionbus import OTPWindow, SessionBus


def test_session_bus_register_get_unregister():
    bus = SessionBus()
    w = OTPWindow("sb-ng-1")
    assert bus.get("sb-ng-1") is None
    bus.register(w)
    assert bus.get("sb-ng-1") is w
    bus.unregister("sb-ng-1")
    assert bus.get("sb-ng-1") is None


def test_otp_window_delivery_roundtrip():
    w = OTPWindow("sb-ng-2")

    def worker():
        time.sleep(0.05)
        w.report_delivery(True, "Real OTP sent")

    threading.Thread(target=worker, daemon=True).start()
    ok, msg = w.wait_delivery(timeout=2)
    assert ok is True
    assert msg == "Real OTP sent"


def test_otp_window_submit_and_completion():
    w = OTPWindow("sb-ng-3")

    def worker():
        otp = w.get_otp(timeout=2)
        w.report_completion(True, True, f"verified with {otp}", None)

    threading.Thread(target=worker, daemon=True).start()
    assert w.submit_otp("123456") is True
    ok, verified, msg, err = w.wait_completion(timeout=2)
    assert ok is True
    assert verified is True
    assert err is None
    assert "123456" in msg


def test_otp_window_timeout_returns_none():
    w = OTPWindow("sb-ng-4")
    with pytest.raises(TimeoutError):
        # internal helper: get_otp blocks then returns None on timeout
        got = w.get_otp(timeout=0.05)
        if got is None:
            raise TimeoutError("no otp before timeout")
    assert w.wait_completion(timeout=0.1) is None
    assert w.wait_delivery(timeout=0.1) is None


def test_session_bus_prune():
    bus = SessionBus()
    bus.register(OTPWindow("allocated"))
    bus.register(OTPWindow("stale"))
    assert bus.prune(active_refs={"allocated"}) == 1
    assert bus.get("allocated") is not None
    assert bus.get("stale") is None