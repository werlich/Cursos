"""Cliente HTTP LivePix (OAuth2 + PIX checkout) com modo DEMO."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_token_lock = threading.Lock()
_cached_token: str | None = None
_cached_token_expires_at: float = 0.0


class LivePixError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class LivePixClient:
    def __init__(self) -> None:
        self.client_id = (getattr(settings, "LIVEPIX_CLIENT_ID", "") or "").strip()
        self.client_secret = (getattr(settings, "LIVEPIX_CLIENT_SECRET", "") or "").strip()
        self.api_url = getattr(
            settings, "LIVEPIX_API_URL", "https://api.livepix.gg"
        ).rstrip("/")
        self.oauth_url = getattr(
            settings, "LIVEPIX_OAUTH_URL", "https://oauth.livepix.gg"
        ).rstrip("/")
        self.scope = getattr(
            settings,
            "LIVEPIX_SCOPE",
            "payments:write payments:read webhooks account:read",
        )
        self.demo = bool(getattr(settings, "LIVEPIX_DEMO", True)) or not (
            self.client_id and self.client_secret
        )

    def _get_access_token(self) -> str:
        global _cached_token, _cached_token_expires_at
        now = time.time()
        with _token_lock:
            if _cached_token and now < _cached_token_expires_at - 60:
                return _cached_token

        try:
            resp = requests.post(
                f"{self.oauth_url}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": self.scope,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise LivePixError(f"Falha OAuth LivePix: {exc}") from exc

        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}
        if resp.status_code >= 400 or "access_token" not in data:
            raise LivePixError(
                f"OAuth LivePix falhou: {data}",
                status_code=resp.status_code,
                payload=data,
            )

        token = data["access_token"]
        expires_in = int(data.get("expires_in") or 3600)
        with _token_lock:
            _cached_token = token
            _cached_token_expires_at = time.time() + expires_in
        return token

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        url = urljoin(self.api_url + "/", path.lstrip("/"))
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._get_access_token()}"
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("User-Agent", "SIGNAU-Cursos/1.0")
        try:
            resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        except requests.RequestException as exc:
            raise LivePixError(f"Falha de rede LivePix: {exc}") from exc
        try:
            data = resp.json() if resp.content else {}
        except ValueError:
            data = {"raw": resp.text}
        if resp.status_code >= 400:
            raise LivePixError(
                str(data.get("message") or data.get("error") or data),
                status_code=resp.status_code,
                payload=data,
            )
        return data if isinstance(data, dict) else {"data": data}

    def create_payment(
        self,
        *,
        amount: Decimal,
        redirect_url: str,
        currency: str = "BRL",
    ) -> dict[str, str]:
        """
        Inicia pagamento. Retorna payment_id, reference, checkout_url.
        amount em reais (convertido para centavos).
        """
        cents = int((amount * 100).quantize(Decimal("1")))
        if self.demo:
            ref = f"demo_{uuid.uuid4().hex[:16]}"
            return {
                "payment_id": ref,
                "reference": ref,
                "checkout_url": "",
            }

        payload = self._request(
            "POST",
            "/v2/payments",
            json={
                "amount": cents,
                "currency": currency,
                "redirectUrl": redirect_url,
            },
        )
        data = payload.get("data") or payload
        reference = str(data.get("reference") or "")
        checkout = str(data.get("redirectUrl") or "")
        if not checkout and reference:
            checkout = f"https://checkout.livepix.gg/{reference}"
        return {
            "payment_id": reference,
            "reference": reference,
            "checkout_url": checkout,
        }

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        if self.demo or payment_id.startswith("demo_"):
            return {
                "id": payment_id,
                "reference": payment_id,
                "amount": 0,
                "currency": "BRL",
            }
        payload = self._request("GET", f"/v2/payments/{payment_id}")
        return payload.get("data") or payload

    def ensure_webhook(self, url: str) -> dict[str, Any] | None:
        """Registra webhook se a API permitir (idempotente best-effort)."""
        if self.demo:
            return None
        try:
            existing = self._request("GET", "/v2/webhooks")
            items = existing.get("data") or existing.get("webhooks") or []
            if isinstance(items, list):
                for item in items:
                    if (item.get("url") or "") == url:
                        return item
            return self._request("POST", "/v2/webhooks", json={"url": url})
        except LivePixError as exc:
            logger.warning("Não foi possível registrar webhook LivePix: %s", exc)
            return None
