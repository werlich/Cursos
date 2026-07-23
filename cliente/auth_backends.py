"""Autenticação por e-mail ou username."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if not username or password is None:
            return None

        user = None
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email__iexact=username)
            except User.DoesNotExist:
                User().set_password(password)
                return None
            except User.MultipleObjectsReturned:
                user = User.objects.filter(email__iexact=username).order_by("id").first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
