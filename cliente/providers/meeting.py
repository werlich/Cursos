"""MeetingProvider — sala de aula (Meet / Zoom / Teams / Jitsi / etc.)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from cliente.models import Live


@dataclass(frozen=True)
class MeetingJoinInfo:
    status: str  # antes | aberta | encerrada
    url: str
    pode_entrar: bool
    label: str


class MeetingProvider(ABC):
    """Interface para provedores de sala (Google Meet API, Zoom, …)."""

    @abstractmethod
    def join_info(self, live: Live) -> MeetingJoinInfo:
        raise NotImplementedError


class ManualUrlMeetingProvider(MeetingProvider):
    """
    Versão 1: administrador cola o link (Google Meet).
    Sem APIs externas — usa Live.stream_url + janela de 5 minutos.
    """

    def join_info(self, live: Live) -> MeetingJoinInfo:
        status = live.meet_status
        url = (live.stream_url or "").strip()
        pode = bool(url) and status == live.MeetStatus.ABERTA
        if status == live.MeetStatus.ANTES:
            label = "Disponível 5 minutos antes da aula"
        elif status == live.MeetStatus.ENCERRADA:
            label = "Aula Encerrada"
        elif not url:
            label = "Link da aula ainda não publicado"
        else:
            label = "Entrar na Aula"
        return MeetingJoinInfo(status=status, url=url, pode_entrar=pode, label=label)


def get_meeting_provider() -> MeetingProvider:
    name = getattr(settings, "MEETING_PROVIDER", "manual_url")
    if name == "manual_url":
        return ManualUrlMeetingProvider()
    # Futuro: google_meet_api, zoom, teams, jitsi, …
    return ManualUrlMeetingProvider()
