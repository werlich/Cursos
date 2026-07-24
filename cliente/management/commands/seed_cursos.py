from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.timezone import make_aware

from cliente.models import Curso, Live


# tipo, nome, descricao, ordem, preco, min_alunos, ativo
CURSOS = [
    (
        Curso.Tipo.ARRAIS_MOTONAUTA,
        "Arrais-Amador e Motonauta",
        "Preparatório ao vivo para Arrais-Amador e Motonauta (NORMAM-211/212).",
        0,
        Decimal("29.90"),
        5,
        True,
    ),
    (
        Curso.Tipo.ARRAIS,
        "Arrais-Amador",
        "Preparatório ao vivo para o exame de Arrais-Amador (NORMAM-211).",
        1,
        Decimal("29.90"),
        5,
        True,
    ),
    (
        Curso.Tipo.MOTONAUTA,
        "Motonauta",
        "Preparatório ao vivo para o exame de Motonauta (NORMAM-212).",
        2,
        Decimal("29.90"),
        5,
        True,
    ),
    (
        Curso.Tipo.MESTRE,
        "Mestre-Amador",
        "Preparatório ao vivo para o exame de Mestre-Amador.",
        3,
        Decimal("150.00"),
        2,
        True,
    ),
    (
        Curso.Tipo.CAPITAO,
        "Capitão-Amador",
        "Preparatório live para exame de Capitão-Amador.",
        4,
        Decimal("29.90"),
        10,
        False,
    ),
]


class Command(BaseCommand):
    help = "Sincroniza catálogo de cursos, preços, mínimos e próximas lives"

    def handle(self, *args, **options):
        # Remove duplicatas ativas com o mesmo nome (mantém o de menor id)
        for nome in ("Arrais-Amador", "Motonauta", "Mestre-Amador", "Arrais-Amador e Motonauta"):
            ids = list(
                Curso.objects.filter(nome=nome, ativo=True).order_by("id").values_list("id", flat=True)
            )
            for dup_id in ids[1:]:
                Curso.objects.filter(pk=dup_id).update(ativo=False)
                self.stdout.write(f"Duplicata desativada: {nome} id={dup_id}")

        for tipo, nome, desc, ordem, preco, min_alunos, ativo in CURSOS:
            curso = Curso.objects.filter(tipo=tipo).order_by("id").first()
            if curso is None:
                curso = Curso(tipo=tipo)
            curso.nome = nome
            curso.descricao = desc
            curso.preco = preco
            curso.min_alunos_padrao = min_alunos
            curso.ativo = ativo
            curso.ordem = ordem
            curso.save()
            # Atualiza lives abertas deste curso
            Live.objects.filter(
                curso=curso,
                status__in=[Live.Status.ABERTA, Live.Status.CONFIRMADA],
            ).update(min_alunos=min_alunos)
            if not ativo:
                Live.objects.filter(
                    curso=curso,
                    status=Live.Status.ABERTA,
                ).update(status=Live.Status.CANCELADA)
            self.stdout.write(f"Curso OK: {nome} (ativo={ativo}, R${preco}, min={min_alunos})")

        hoje = timezone.localdate()
        datas = []
        d = hoje
        while len(datas) < 6:
            d = d + timedelta(days=1)
            if d.weekday() in (0, 2, 4):
                datas.append(make_aware(datetime.combine(d, time(19, 0))))

        cursos = list(Curso.objects.filter(ativo=True).order_by("ordem"))
        criadas = 0
        for i, dt in enumerate(datas):
            curso = cursos[i % len(cursos)]
            obj, created = Live.objects.get_or_create(
                curso=curso,
                data_hora=dt,
                defaults={
                    "titulo": f"Live {curso.nome}",
                    "status": Live.Status.ABERTA,
                    "min_alunos": curso.min_alunos_padrao,
                    "stream_url": "",
                },
            )
            if created:
                criadas += 1
                self.stdout.write(f"Live criada: {obj}")
            else:
                if obj.min_alunos != curso.min_alunos_padrao and obj.status == Live.Status.ABERTA:
                    obj.min_alunos = curso.min_alunos_padrao
                    obj.save(update_fields=["min_alunos"])

        self.stdout.write(self.style.SUCCESS(f"Catálogo sincronizado. {criadas} live(s) nova(s)."))
