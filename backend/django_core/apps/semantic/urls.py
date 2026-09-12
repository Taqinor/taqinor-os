"""URLs de la couche sémantique (NTDATA9).

Une lecture pour l'instant. Le CRUD des métriques (NTDATA10) viendra s'ajouter
ici ; il n'existe pas encore, et cette liste dit exactement ce qui est servi.

L'historique se lit par IDENTIFIANT : une version appartient à UNE ligne de
définition, même si sa clé change en cours de route.
"""
from django.urls import path

from .views import MetriqueVersionsView

urlpatterns = [
    # NTDATA9 — historique figé des définitions successives d'une métrique.
    path('metriques/<int:pk>/versions/', MetriqueVersionsView.as_view(),
         name='metrique-versions'),
]
