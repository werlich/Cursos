"""Abstrações de provedores de reunião e pagamento.

Futuro: Google Meet API, Zoom, Teams, Jitsi, OBS, YouTube Live,
LivePix API de arrecadação, Asaas.
"""

from .meeting import MeetingProvider, ManualUrlMeetingProvider, get_meeting_provider
from .payment import (
    AsaasPaymentProvider,
    LivePixPaymentProvider,
    PaymentProvider,
    get_payment_provider,
)

__all__ = [
    "MeetingProvider",
    "ManualUrlMeetingProvider",
    "get_meeting_provider",
    "PaymentProvider",
    "LivePixPaymentProvider",
    "AsaasPaymentProvider",
    "get_payment_provider",
]
