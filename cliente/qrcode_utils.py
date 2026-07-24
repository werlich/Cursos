"""Geração de QR Code em data URI (SVG)."""

from __future__ import annotations

import base64
from io import BytesIO

import qrcode
from qrcode.image.svg import SvgPathImage


def qr_data_uri(payload: str, *, box_size: int = 8, border: int = 2) -> str:
    """Retorna data:image/svg+xml;base64,… para embutir em <img>."""
    img = qrcode.make(
        payload,
        image_factory=SvgPathImage,
        box_size=box_size,
        border=border,
    )
    buf = BytesIO()
    img.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"
