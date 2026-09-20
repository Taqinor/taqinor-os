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
from rest_framework.routers import SimpleRouter

from .views.calepinages import CalepinageViewSet
from .views.consommation import ProfilsTypesView
from .views.moteur import (
    MoteurCalculerView,
    MoteurPoseView,
    MoteurResultatView,
)
from .views.parametres import (
    ParametresCalepinageView,
    SuggestionPenteIGNView,
)
# CAL243 — rattache l'action ``equipements`` au ``CalepinageViewSet`` par
# import (affectation d'attribut de classe, voir la docstring du module) ;
# doit s'exécuter AVANT ``router.register`` pour que le routeur la découvre.
from .views import equipements as _equipements_action  # noqa: F401
# CAL92/93 — même patron : rattache l'action ``horizon`` (profil d'horizon
# PVGIS ``printhorizon``, contrat CAL92).
from .views import horizon as _horizon_action  # noqa: F401
# CAL144 — même forme pour l'export CSV (``calepinages/<pk>/export-csv/``) :
# code dans un fichier neuf, enregistrement en une ligne additive.
from .views import export_csv as _export_csv_action  # noqa: F401
# CAL246 — même patron : rattache l'action ``modeles`` (bibliothèque).
from .views import bibliotheque as _bibliotheque_action  # noqa: F401
# CAL207 — même patron : rattache l'action ``deverrouiller``.
from .views import verrou as _verrou_action  # noqa: F401
# CAL208 — même patron : rattache ``archiver``/``restaurer-corbeille``.
from .views import archivage as _archivage_action  # noqa: F401
# CAL216 — même patron : rattache ``export-layout``/``import-layout``.
from .views import io_layout as _io_layout_action  # noqa: F401
# CAL159 — même discipline pour l'action ``pompage`` (dimensionnement du
# pompage solaire, services CAL155-CAL158) : code dans son propre fichier,
# rattachement par cet import, AVANT ``router.register``.
from .views import pompage as _pompage_action  # noqa: F401
# CAL139 — même patron : rattache ``pertes``/``enregistrer-pertes``.
from .views import simulation as _simulation_actions  # noqa: F401
# CAL191 — même patron : rattache ``dossiers-reglementaires`` (contrat CAL247).
from .views import reglementaire as _reglementaire_action  # noqa: F401

# ``SimpleRouter`` et non ``DefaultRouter`` (même choix qu'``apps/ai_governance``)
# : ``DefaultRouter`` ajoute une vue « api-root » que personne n'appelle ET un
# suffixe de format par ressource (``calepinages.json``) — soit une SECONDE
# forme d'URL pour le même objet, exactement ce que CAL233 interdit et ce que
# ``tests/test_structure_urls.py`` mesure.
router = SimpleRouter()
router.register(r'calepinages', CalepinageViewSet, basename='calepinage')

urlpatterns = [
    # CAL22 — la porte NEUTRE du moteur. Ce n'est PAS une seconde famille
    # d'URL pour l'objet métier (le calepinage reste servi sous
    # ``calepinages/<pk>/…``) : c'est un CALCUL sans état, sans identifiant,
    # qui n'appartient à aucun calepinage — le chemin est celui que le contrat
    # `contract_samples/moteur_calculer.json` fige depuis le jour 1.
    path('moteur/calculer/', MoteurCalculerView.as_view(),
         name='calepinage-moteur-calculer'),
    # CAL78 — LA POSE et son régime de preuve, même famille ``moteur`` (un
    # calcul sans état, sans identifiant) ; chemin figé depuis le jour 1 par
    # ``contract_samples/pose.json``.
    path('moteur/pose/', MoteurPoseView.as_view(),
         name='calepinage-moteur-pose'),
    # CAL23 — le suivi d'un calcul lancé en tâche de fond (même famille
    # ``moteur`` : un calcul, pas l'objet métier).
    path('moteur/resultat/<int:job_id>/', MoteurResultatView.as_view(),
         name='calepinage-moteur-resultat'),
    # CAL45/CAL16 — les réglages société : UNE ressource unique par société,
    # donc une vue GET/PUT à plat plutôt qu'une collection à identifiants (il
    # n'y a jamais deux jeux de réglages pour une même société).
    path('parametres/', ParametresCalepinageView.as_view(),
         name='calepinage-parametres'),
    # CAL237 — la suggestion de pente/azimut IGN (France seule). Elle vit sous
    # le préfixe ``parametres`` parce que c'est un RÉGLAGE société qui la
    # commande (``imagerie.pays == 'fr'``, CAL47) : elle ne sert aucun objet
    # métier, aucun identifiant de calepinage n'y entre, et elle ne persiste
    # rien — elle PROPOSE.
    path('parametres/suggestion-pente/', SuggestionPenteIGNView.as_view(),
         name='calepinage-parametres-suggestion-pente'),
    # CAL149 — les PROFILS TYPES de consommation de la société. Même raison
    # que ci-dessus : c'est un RÉGLAGE société (aucun identifiant de
    # calepinage n'y entre), donc il vit sous le préfixe ``parametres`` et
    # n'ouvre aucune seconde famille d'URL pour l'objet métier.
    path('parametres/profils-types/', ProfilsTypesView.as_view(),
         name='calepinage-parametres-profils-types'),
    path('', include(router.urls)),
]
