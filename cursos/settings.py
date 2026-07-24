"""Configuração Django — Cursos SIGNAU (local e produção via env)."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-cursos-signau-change-in-production",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,live.signau.cc"
    ).split(",")
    if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "https://live.signau.cc,http://live.signau.cc,http://127.0.0.1:8000",
    ).split(",")
    if o.strip()
]

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "cliente",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cursos.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cliente.context_processors.site_extras",
            ],
        },
    },
]

WSGI_APPLICATION = "cursos.wsgi.application"

_db_name = os.environ.get("DJANGO_DB_NAME", "").strip()
if _db_name:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": _db_name,
            "USER": os.environ.get("DJANGO_DB_USER", ""),
            "PASSWORD": os.environ.get("DJANGO_DB_PASSWORD", ""),
            "HOST": os.environ.get("DJANGO_DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DJANGO_DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/"

AUTHENTICATION_BACKENDS = [
    "cliente.auth_backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"

SITE_URL = os.environ.get("SITE_URL", "https://live.signau.cc").rstrip("/")

# LivePix
LIVEPIX_CLIENT_ID = os.environ.get("LIVEPIX_CLIENT_ID", "")
LIVEPIX_CLIENT_SECRET = os.environ.get("LIVEPIX_CLIENT_SECRET", "")
LIVEPIX_API_URL = os.environ.get("LIVEPIX_API_URL", "https://api.livepix.gg").rstrip("/")
LIVEPIX_OAUTH_URL = os.environ.get("LIVEPIX_OAUTH_URL", "https://oauth.livepix.gg").rstrip("/")
LIVEPIX_SCOPE = os.environ.get(
    "LIVEPIX_SCOPE",
    "payments:write payments:read webhooks account:read",
)
LIVEPIX_DEMO = os.environ.get("LIVEPIX_DEMO", "true").lower() in ("1", "true", "yes")

# WhatsApp
WHATSAPP_SCHOOL_NUMBER = os.environ.get("WHATSAPP_SCHOOL_NUMBER", "47933835108")
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_EVOLUTION_URL = os.environ.get("WHATSAPP_EVOLUTION_URL", "")
WHATSAPP_EVOLUTION_KEY = os.environ.get("WHATSAPP_EVOLUTION_KEY", "")

MIN_ALUNOS_TURMA = int(os.environ.get("MIN_ALUNOS_TURMA", "5"))
PRECO_PADRAO = os.environ.get("PRECO_PADRAO", "29.90")

JAZZMIN_SETTINGS = {
    "site_title": "SIGNAU Cursos",
    "site_header": "SIGNAU Cursos Live",
    "site_brand": "SIGNAU Cursos",
    "site_logo": "img/signau-logo.png",
    "login_logo": "img/signau-logo.png",
    "site_logo_classes": "img-circle",
    "welcome_sign": "Entre com seu e-mail e senha",
    "copyright": "SIGNAU — Sistemas Integrados em Gestão Náutica",
    "custom_css": "css/admin-jazzmin-v2.css",
    "search_model": ["cliente.Cliente", "cliente.Inscricao"],
    "topmenu_links": [
        {"name": "Site", "url": "/", "new_window": True},
    ],
    "order_with_respect_to": [
        "cliente.Curso",
        "cliente.Live",
        "cliente.Cliente",
        "cliente.Inscricao",
        "cliente.Pagamento",
        "cliente.Credito",
        "cliente.Depoimento",
    ],
    "icons": {
        "cliente.Curso": "fas fa-graduation-cap",
        "cliente.Live": "fas fa-broadcast-tower",
        "cliente.Cliente": "fas fa-user",
        "cliente.Inscricao": "fas fa-clipboard-list",
        "cliente.Pagamento": "fas fa-qrcode",
        "cliente.Credito": "fas fa-wallet",
        "cliente.Depoimento": "fas fa-comment-dots",
    },
}

JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "navbar": "navbar-white navbar-light",
    "navbar_fixed": True,
    "accent": "accent-primary",
    "sidebar": "sidebar-dark-primary",
}
