from django.urls import path

from .views import (
    PublicIncidentDetailView, PublicIncidentsView, public_status,
    publier_postmortem,
)

urlpatterns = [
    # NTOBS1 — endpoints publics (AllowAny), montés sous
    # `api/django/statuspage/…` (voir erp_agentique/urls.py::_APP_URLS).
    path('public/', public_status, name='statuspage-public-status'),
    path('public/incidents/', PublicIncidentsView.as_view(),
         name='statuspage-public-incidents'),
    # NTOBS2 — détail d'un incident (post-mortem inclus s'il est publié).
    path('public/incidents/<int:pk>/', PublicIncidentDetailView.as_view(),
         name='statuspage-public-incident-detail'),
    # NTOBS2 — action interne (Directeur/Administrateur), authentifiée.
    path('incidents/<int:pk>/publier-postmortem/', publier_postmortem,
         name='statuspage-publier-postmortem'),
]
