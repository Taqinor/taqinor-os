from django.urls import path

from .views import PublicIncidentsView, public_status

urlpatterns = [
    # NTOBS1 — endpoints publics (AllowAny), montés sous
    # `api/django/statuspage/…` (voir erp_agentique/urls.py::_APP_URLS).
    path('public/', public_status, name='statuspage-public-status'),
    path('public/incidents/', PublicIncidentsView.as_view(),
         name='statuspage-public-incidents'),
]
