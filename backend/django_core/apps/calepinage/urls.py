"""Routes du module « calepinage » (CAL4).

Montées dans ``erp_agentique/urls.py`` sous ``path('calepinage/', …)``, donc
servies à partir de ``/api/django/calepinage/``. Le 2ᵉ segment d'URL est la clé
``module_manifest['key']`` (``calepinage``) : le gatage 404 des modules
désactivés vise le bon module SANS entrée ``PREFIX_TO_MODULE``.

FORME D'URL UNIQUE (CAL233) — tout l'objet métier est servi sous
``/api/django/calepinage/calepinages/<pk>/…`` (sous-ressources en ``@action``
du routeur DRF) et les réglages société sous
``/api/django/calepinage/parametres/``. Aucune autre famille d'URL n'est
admise : deux familles pour un même objet, c'est l'incident PACT10 par
construction. Un test (``tests/test_structure_urls.py``) le vérifie.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views.calepinages import CalepinageViewSet
from .views.moteur import MoteurCalculerView, MoteurResultatView
from .views.parametres import ParametresCalepinageView

router = DefaultRouter()
router.register(r'calepinages', CalepinageViewSet, basename='calepinage')

urlpatterns = [
    # CAL22 — la porte NEUTRE du moteur. Ce n'est PAS une seconde famille
    # d'URL pour l'objet métier (le calepinage reste servi sous
    # ``calepinages/<pk>/…``) : c'est un CALCUL sans état, sans identifiant,
    # qui n'appartient à aucun calepinage — le chemin est celui que le contrat
    # `contract_samples/moteur_calculer.json` fige depuis le jour 1.
    path('moteur/calculer/', MoteurCalculerView.as_view(),
         name='calepinage-moteur-calculer'),
    # CAL23 — le suivi d'un calcul lancé en tâche de fond (même famille
    # ``moteur`` : un calcul, pas l'objet métier).
    path('moteur/resultat/<int:job_id>/', MoteurResultatView.as_view(),
         name='calepinage-moteur-resultat'),
    # CAL45/CAL16 — les réglages société : UNE ressource unique par société,
    # donc une vue GET/PUT à plat plutôt qu'une collection à identifiants (il
    # n'y a jamais deux jeux de réglages pour une même société).
    path('parametres/', ParametresCalepinageView.as_view(),
         name='calepinage-parametres'),
    path('', include(router.urls)),
]
