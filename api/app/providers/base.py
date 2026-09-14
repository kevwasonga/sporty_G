import abc
from dataclasses import dataclass


@dataclass
class SendContext:
    """Everything a provider needs to start an OTP flow for one number."""

    phone: str
    password: str


@dataclass
class SendResult:
    """Result of telling the provider to start signup / deliver an OTP."""

    success: bool
    message: str
    provider_ref: str | None = None
    error: str | None = None


@dataclass
class CompleteResult:
    """Result of completing signup with the code the operator typed in."""

    success: bool
    message: str
    verified: bool = False
    error: str | None = None


class ProviderAdapter(abc.ABC):
    """One logical integration behind the OTP/signup flow.

    Implementations are deliberately small:
      * ``send_otp(ctx)``        - start registration for a phone; an OTP is
                                    delivered to the number (by us or the target).
      * ``complete_signup(...)`` - submit the code that arrived on the phone,
                                    finalizing the signup.
    Everything else (status tracking, password lifecycle, storage) lives in the
    services layer, so providers stay swappable.
    """

    name: str = "base"

    @abc.abstractmethod
    def send_otp(self, ctx: SendContext) -> SendResult: ...

    @abc.abstractmethod
    def complete_signup(self, phone: str, password: str, otp: str, provider_ref: str | None) -> CompleteResult: ...