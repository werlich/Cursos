"""Context processors públicos."""

from django.conf import settings

from .whatsapp import school_whatsapp_link


def site_extras(request):
    return {
        "whatsapp_url": school_whatsapp_link(
            "Olá! Vim pelo site live.signau.cc e quero saber mais sobre as lives."
        ),
        "whatsapp_base_url": school_whatsapp_link(),
        "whatsapp_school": getattr(settings, "WHATSAPP_SCHOOL_NUMBER", "47933835108"),
    }
