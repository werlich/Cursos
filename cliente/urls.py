from django.urls import path

from . import views

app_name = "cliente"

urlpatterns = [
    path("", views.home, name="home"),
    path("cadastro/", views.cadastro, name="cadastro"),
    path("pagamento/<str:token>/", views.pagamento, name="pagamento"),
    path(
        "pagamento/<str:token>/retorno/",
        views.pagamento_retorno,
        name="pagamento_retorno",
    ),
    path(
        "pagamento/<str:token>/demo-confirmar/",
        views.pagamento_demo_confirmar,
        name="pagamento_demo_confirmar",
    ),
    path("pagamento/<str:token>/status/", views.status_pagamento, name="status_pagamento"),
    path("sala/<str:token>/", views.sala, name="sala"),
    path("webhooks/livepix/", views.livepix_webhook, name="livepix_webhook"),
]
