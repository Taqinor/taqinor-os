"""Routes du module Appels d'offres (``apps.ao``) — ODX11 puis AOF31.

Préfixe ``/api/django/ao/…``. Les 8 ViewSets HISTORIQUES sont AUSSI servis par
``apps.compta.urls`` sous ``/api/django/compta/…`` (routes conservées à
l'identique pour ne casser aucun client) — les classes, elles, vivent
désormais dans ``apps.ao.views`` (AOF1).

**Tous les basenames sont préfixés ``ao-``.** Ce n'est pas de la cosmétique :
le routeur compta enregistre les mêmes ViewSets et reverse ``appeloffre-list``
etc. Sans le préfixe, deux entrées porteraient le même nom d'URL et
``reverse()`` renverrait silencieusement la mauvaise — un test explicite
(``test_routes_ao``) vérifie qu'aucune collision n'existe.

AOF31 — le contrat d'API (``/contrat/``) est DÉRIVÉ de ce routeur : il ne peut
pas se désynchroniser de la réalité. La pagination est celle du projet
(``core.pagination.StandardPagination``), donc transverse et non redéclarée.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppelOffreViewSet,
    ContratApiAO,
    BatimentAOViewSet,
    BordereauPrixViewSet,
    CautionSoumissionViewSet,
    ChaineCotesViewSet,
    DossierSoumissionViewSet,
    EcheanceAOViewSet,
    ExigenceCPSViewSet,
    KitCalepinageViewSet,
    LigneBordereauViewSet,
    ObstacleAOViewSet,
    PieceConsultationViewSet,
    PieceSoumissionViewSet,
    PlanSourceViewSet,
    PresetCalepinageViewSet,
    ReleveAOViewSet,
    SectionBordereauViewSet,
    QuestionAOViewSet,
    ResultatAOViewSet,
    SerieQuestionsViewSet,
    ToitureAOViewSet,
    VarianteCalepinageViewSet,
)
from .viewsets import (
    DossierAOViewSet, LigneChecklistPartenaireViewSet,
    PieceAdministrativeViewSet, PieceDossierAOViewSet,
)
# AOF157 — l'économie DIRECTEUR vit dans des vues SÉPARÉES, gardées par
# ``ao_rentabilite_voir`` (permission ÉLEVÉE) : jamais mêlée aux vues AO
# générales, sinon la marge suivrait toutes leurs surfaces.
from .views_directeur import (
    CibleFinanciereViewSet, EconomieAOViewSet, LigneCoutRevientViewSet,
)

router = DefaultRouter()
router.register(r'appels-offres', AppelOffreViewSet, basename='ao-appel-offre')
router.register(r'pieces-consultation', PieceConsultationViewSet,
                basename='ao-piece-consultation')
router.register(r'exigences-cps', ExigenceCPSViewSet,
                basename='ao-exigence-cps')
router.register(r'batiments', BatimentAOViewSet, basename='ao-batiment')
router.register(r'toitures', ToitureAOViewSet, basename='ao-toiture')
router.register(r'plans-source', PlanSourceViewSet,
                basename='ao-plan-source')
router.register(r'obstacles', ObstacleAOViewSet,
                basename='ao-obstacle')
router.register(r'chaines-cotes', ChaineCotesViewSet,
                basename='ao-chaine-cotes')
router.register(r'releves', ReleveAOViewSet, basename='ao-releve')
router.register(r'series-questions', SerieQuestionsViewSet,
                basename='ao-serie-questions')
router.register(r'questions', QuestionAOViewSet,
                basename='ao-question')
router.register(r'kits-calepinage', KitCalepinageViewSet,
                basename='ao-kit-calepinage')
router.register(r'presets-calepinage', PresetCalepinageViewSet,
                basename='ao-preset-calepinage')
router.register(r'variantes-calepinage', VarianteCalepinageViewSet,
                basename='ao-variante-calepinage')
router.register(r'bordereaux-prix', BordereauPrixViewSet,
                basename='ao-bordereau-prix')
router.register(r'lignes-bordereau', LigneBordereauViewSet,
                basename='ao-ligne-bordereau')
# AOF120 — sections du bordereau (une par bâtiment + prestations communes).
router.register(r'sections-bordereau', SectionBordereauViewSet,
                basename='ao-section-bordereau')
router.register(r'cautions-soumission', CautionSoumissionViewSet,
                basename='ao-caution-soumission')
router.register(r'dossiers-soumission', DossierSoumissionViewSet,
                basename='ao-dossier-soumission')
router.register(r'pieces-soumission', PieceSoumissionViewSet,
                basename='ao-piece-soumission')
router.register(r'echeances-ao', EcheanceAOViewSet, basename='ao-echeance')
router.register(r'resultats-ao', ResultatAOViewSet, basename='ao-resultat')
# AOF115 — dossier de dépôt (kit ``core/documents.py``) et ses pièces.
router.register(r'dossiers-ao', DossierAOViewSet, basename='ao-dossier-ao')
router.register(r'pieces-dossier-ao', PieceDossierAOViewSet,
                basename='ao-piece-dossier-ao')
# AOF136 — checklist partenaire suivie point par point.
router.register(r'checklist-partenaire', LigneChecklistPartenaireViewSet,
                basename='ao-checklist-partenaire')
# AOF137 — pièces administratives DATÉES, réutilisables d'un AO à l'autre.
router.register(r'pieces-administratives', PieceAdministrativeViewSet,
                basename='ao-piece-administrative')
# AOF157 — ÉCONOMIE DIRECTEUR : routes séparées, garde ``ao_rentabilite_voir``.
router.register(r'economie', EconomieAOViewSet, basename='ao-economie')
router.register(r'lignes-cout-revient', LigneCoutRevientViewSet,
                basename='ao-ligne-cout-revient')
router.register(r'cibles-financieres', CibleFinanciereViewSet,
                basename='ao-cible-financiere')

urlpatterns = [
    # AOF31 — contrat d'API publié, dérivé du routeur ci-dessus.
    path('contrat/', ContratApiAO.as_view(), name='ao-contrat'),
    path('', include(router.urls)),
]

# AOF61/AOF62 — l'API de calepinage (calcul borné, job de fond, actions de
# variante idempotentes) est routée par son PROPRE module. Ajout en fin de
# fichier, sans toucher au routeur historique ci-dessus : celui-ci est
# consommé tel quel par ``ContratApiAO`` et par ``apps.compta.urls``.
urlpatterns += [path('', include('apps.ao.calepinage_urls'))]
