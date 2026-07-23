from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from cliente.forms import AdminEmailAuthenticationForm

admin.site.login_form = AdminEmailAuthenticationForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("cliente.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
