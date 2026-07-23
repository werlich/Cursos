"""Cliente HTTP Asaas (PIX QR) com modo DEMO para desenvolvimento."""

from __future__ import annotations

import base64
import logging
import uuid
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class AsaasError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class AsaasClient:
    def __init__(self) -> None:
        self.api_key = (getattr(settings, "ASAAS_API_KEY", "") or "").strip()
        self.base_url = getattr(
            settings, "ASAAS_API_URL", "https://sandbox.asaas.com/api/v3"
        ).rstrip("/")
        self.demo = bool(getattr(settings, "ASAAS_DEMO", True)) or not self.api_key

    def _headers(self) -> dict[str, str]:
        return {
            "access_token": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Cursos-SIGNAU/1.0",
        }

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(
                method, url, headers=self._headers(), timeout=30, **kwargs
            )
        except requests.RequestException as exc:
            raise AsaasError(f"Falha de rede Asaas: {exc}") from exc
        try:
            data = resp.json() if resp.content else {}
        except ValueError:
            data = {"raw": resp.text}
        if resp.status_code >= 400:
            msg = data.get("errors") or data.get("message") or resp.text
            raise AsaasError(str(msg), status_code=resp.status_code, payload=data)
        return data if isinstance(data, dict) else {"data": data}

    def ensure_customer(self, *, nome: str, email: str, whatsapp: str) -> str:
        if self.demo:
            return f"cus_demo_{uuid.uuid4().hex[:12]}"

        phone = "".join(c for c in whatsapp if c.isdigit())
        existing = self._request(
            "GET", "/customers", params={"email": email, "limit": 1}
        )
        items = existing.get("data") or []
        if items:
            return items[0]["id"]

        created = self._request(
            "POST",
            "/customers",
            json={
                "name": nome,
                "email": email,
                "mobilePhone": phone[-11:] if len(phone) >= 11 else phone,
                "notificationDisabled": True,
            },
        )
        return created["id"]

    def create_pix_charge(
        self,
        *,
        customer_id: str,
        valor: Decimal,
        descricao: str,
        external_reference: str,
    ) -> dict[str, str]:
        """Retorna payment_id, qr (base64/data-uri), copia_cola, invoice_url."""
        if self.demo:
            payload = f"00020126580014BR.GOV.BCB.PIX0136{uuid.uuid4()}520400005303986540{valor:.2f}5802BR5925SIGNAU CURSOS LIVE6009FLORIANOPOLIS62070503***6304ABCD"
            # QR placeholder: data URI SVG
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220">'
                f'<rect width="100%" height="100%" fill="#fff"/>'
                f'<text x="20" y="110" font-size="14" fill="#111">PIX DEMO R$ {valor}</text>'
                f"</svg>"
            )
            b64 = base64.b64encode(svg.encode()).decode()
            return {
                "payment_id": f"pay_demo_{uuid.uuid4().hex[:16]}",
                "pix_qr_code": f"data:image/svg+xml;base64,{b64}",
                "pix_copia_cola": payload,
                "invoice_url": "",
            }

        payment = self._request(
            "POST",
            "/payments",
            json={
                "customer": customer_id,
                "billingType": "PIX",
                "value": float(valor),
                "description": descricao[:400],
                "externalReference": external_reference,
            },
        )
        payment_id = payment["id"]
        qr = self._request("GET", f"/payments/{payment_id}/pixQrCode")
        encoded = qr.get("encodedImage") or ""
        if encoded and not encoded.startswith("data:"):
            encoded = f"data:image/png;base64,{encoded}"
        return {
            "payment_id": payment_id,
            "pix_qr_code": encoded,
            "pix_copia_cola": qr.get("payload") or "",
            "invoice_url": payment.get("invoiceUrl") or "",
        }

    def refund(self, payment_id: str, *, valor: Decimal | None = None) -> dict[str, Any]:
        if self.demo or payment_id.startswith("pay_demo_"):
            return {"id": payment_id, "status": "REFUNDED", "demo": True}
        body: dict[str, Any] = {}
        if valor is not None:
            body["value"] = float(valor)
        return self._request("POST", f"/payments/{payment_id}/refund", json=body or None)
