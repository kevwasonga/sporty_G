"""Live-session bridge between an OTP send and its later verification.

SportyBet's browser session is opened on a background thread. When SportyBet
sends the real code to the phone we must keep that browser *alive* so the code
the operator later types in the UI can be fed back into the same page and the
signup completed.

``OTPWindow`` is the communication boundary:

* ``send_otp`` runs in a worker thread and reports the delivery result here.
* ``complete_signup`` runs on a FastAPI request thread and pushes the typed
  code back; the browser thread waits for it, enters it, and reports the final
  account-creation outcome.

Only thread-safe Python queues are shared — never Playwright objects across
threads (each OTPWindow is pinned to the thread that owns its browser).
"""

from __future__ import annotations

import logging
import queue
import threading

logger = logging.getLogger("sporty.lab.providers.sessionbus")


class OTPWindow:
    """Holds the hand-off state for one live SportyBet browser session."""

    def __init__(self, provider_ref: str) -> None:
        self.provider_ref = provider_ref
        self._deliver_q: "queue.Queue[tuple[bool, str]]" = queue.Queue(maxsize=1)
        self._otp_q: "queue.Queue[str]" = queue.Queue(maxsize=1)
        self._complete_q: "queue.Queue[tuple[bool, bool, str, str | None]]" = queue.Queue(maxsize=1)
        self._closed = threading.Event()

    # -- report side (browser worker thread) -------------------------------
    def report_delivery(self, ok: bool, message: str) -> None:
        try:
            self._deliver_q.put_nowait((ok, message))
        except queue.Full:
            logger.warning("sessionbus: delivery slot already full for %s", self.provider_ref)

    def wait_delivery(self, timeout: float) -> tuple[bool, str] | None:
        try:
            return self._deliver_q.get(timeout=timeout)
        except queue.Empty:
            return None

    # -- command side (FastAPI request thread) -----------------------------
    def submit_otp(self, otp: str) -> bool:
        try:
            self._otp_q.put_nowait(otp)
            return True
        except queue.Full:
            logger.warning("sessionbus: OTP already submitted for %s", self.provider_ref)
            return False

    def wait_completion(self, timeout: float) -> tuple[bool, bool, str, str | None] | None:
        try:
            return self._complete_q.get(timeout=timeout)
        except queue.Empty:
            return None

    # -- browser worker consuming the typed code --------------------------
    def get_otp(self, timeout: float) -> str | None:
        try:
            return self._otp_q.get(timeout=timeout)
        except queue.Empty:
            return None

    def report_completion(
        self,
        ok: bool,
        verified: bool,
        message: str,
        error: str | None = None,
    ) -> None:
        try:
            self._complete_q.put_nowait((ok, verified, message, error))
        except queue.Full:
            logger.warning("sessionbus: completion slot already full for %s", self.provider_ref)

    def close(self) -> None:
        self._closed.set()


class SessionBus:
    """Thread-safe registry of live OTP windows keyed by provider_ref."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, OTPWindow] = {}

    def register(self, window: OTPWindow) -> None:
        with self._lock:
            self._windows[window.provider_ref] = window

    def get(self, provider_ref: str) -> OTPWindow | None:
        with self._lock:
            return self._windows.get(provider_ref)

    def unregister(self, provider_ref: str) -> None:
        with self._lock:
            window = self._windows.pop(provider_ref, None)
        if window:
            window.close()

    def prune(self, active_refs: set[str]) -> int:
        """Drop windows that no longer correspond to known registrations."""
        with self._lock:
            stale = [ref for ref in self._windows if ref not in active_refs]
            for ref in stale:
                self._windows.pop(ref, None)
        for ref in stale:
            logger.info("sessionbus: pruned stale session %s", ref)
        return len(stale)


session_bus = SessionBus()