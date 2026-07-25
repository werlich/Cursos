from django.urls import path

from . import views
from .views_aluno import (
    AlunoAulaDetailView,
    AlunoAulasView,
    GravacaoRedirectView,
    MaterialDownloadView,
)

app_name = "cliente"

urlpatterns = [
    path("", views.home, name="home"),
    path("quem-sou/", views.quem_sou, name="quem_sou"),
    path("avaliacao/", views.avaliacao, name="avaliacao"),
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
    path("aluno/<str:token>/", AlunoAulasView.as_view(), name="aluno_aulas"),
    path(
        "aluno/<str:token>/aula/<int:live_id>/",
        AlunoAulaDetailView.as_view(),
        name="aluno_aula",
    ),
    path(
        "aluno/<str:token>/material/<int:material_id>/",
        MaterialDownloadView.as_view(),
        name="aluno_material",
    ),
    path(
        "aluno/<str:token>/gravacao/<int:gravacao_id>/",
        GravacaoRedirectView.as_view(),
        name="aluno_gravacao",
    ),
    path("webhooks/livepix/", views.livepix_webhook, name="livepix_webhook"),
]
