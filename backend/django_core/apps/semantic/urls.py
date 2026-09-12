"""URLs de la couche sémantique (NTDATA9 / NTDATA43).

Deux lectures. Le CRUD des métriques (NTDATA10) viendra s'ajouter ici ; il
n'existe pas encore, et cette liste dit exactement ce qui est servi.

L'HISTORIQUE se lit par IDENTIFIANT — une version appartient à UNE ligne de
définition, même si sa clé change en cours de route. Le LIGNAGE se lit par CLÉ :
c'est par la clé qu'un widget, un rapport ou une alerte référence une métrique,
donc c'est la clé que l'utilisateur a sous les yeux quand il demande « d'où
vient ce chiffre ». Les deux motifs ne se recouvrent pas (``<int:pk>`` contre
``<str:cle>``) et chaque route a SA classe de vue : deux routes sur la même vue
collisionnent d'``operationId`` au schéma OpenAPI (précédent NTDATA5).
"""
from django.urls import path

from .views import MetriqueLignageView, MetriqueVersionsView

urlpatterns = [
    # NTDATA9 — historique figé des définitions successives d'une métrique.
    path('metriques/<int:pk>/versions/', MetriqueVersionsView.as_view(),
         name='metrique-versions'),
    # NTDATA43 — lignage : d'où vient ce chiffre.
    path('metriques/<str:cle>/lignage/', MetriqueLignageView.as_view(),
         name='metrique-lignage'),
]
