from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Garante usuário admin sc7online@gmail.com"

    def handle(self, *args, **options):
        User = get_user_model()
        email = "sc7online@gmail.com"
        password = "303009"
        # username sem @ evita confusão no formulário Jazzmin
        username = "sc7online"

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.filter(username__iexact=username).first()
        if user is None:
            user = User.objects.filter(username__iexact=email).first()

        if user is None:
            user = User(username=username, email=email)
            created = True
        else:
            created = False

        user.username = username
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        # remove duplicata com username = email se existir outro registro
        User.objects.filter(username__iexact=email).exclude(pk=user.pk).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Criado' if created else 'Atualizado'}: {user.username} / {user.email}"
            )
        )
