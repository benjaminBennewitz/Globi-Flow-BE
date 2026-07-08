# config/urls.py

"""URL-Konfiguration für die Globi-Flow-API."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.core.urls')),
    path('api/', include('apps.dashboard.urls')),
    path('api/', include('apps.patients.urls')),
    path('api/', include('apps.imports.urls')),
    path('api/', include('apps.knowledge.urls')),
    path('api/', include('apps.reports.urls')),
    path('api/', include('apps.labs.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
