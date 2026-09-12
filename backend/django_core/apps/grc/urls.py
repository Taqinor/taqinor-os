"""Routes du module GRC & Conformité (NTGRC).

Monté par ``erp_agentique/urls.py`` sous ``api/django/grc/`` (et donc aussi
sous ``api/v1/grc/``). Le 2ᵉ segment correspond à la clé
``module_manifest['key']`` (``grc``) pour que le gatage 404 des modules
désactivés vise le bon module.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .public_views import (
    deposer_demande_droit, questionnaire_public, suivre_demande_droit,
)
from .views import (
    AnalyseImpactDPIAViewSet,
    AttestationPolitiqueViewSet, ControleInterneViewSet,
    DeficienceControleViewSet, JournalDestructionViewSet, LegalHoldViewSet,
    IncidentSecuriteViewSet, ModeleQuestionnaireViewSet,
    PlanTraitementRisqueViewSet,
    PolitiqueInterneViewSet, PolitiqueRetentionObjetViewSet,
    QuestionnaireFournisseurViewSet, ReponseQuestionnaireViewSet,
    RevueRisqueViewSet, RisqueEntrepriseViewSet, TestControleViewSet,
    ViolationDonneesViewSet, tableau_bord_dpo,
)

router = DefaultRouter()
# NTGRC4 — durées de conservation par type d'objet (pilote les balayages
# `core.retention` enregistrés par crm/ventes/sav/audit).
router.register(r'politiques-retention-objet', PolitiqueRetentionObjetViewSet,
                basename='grc-politique-retention-objet')
# NTGRC5 — journal APPEND-ONLY des destructions/anonymisations réelles.
router.register(r'journal-destruction', JournalDestructionViewSet,
                basename='grc-journal-destruction')
# NTGRC6 — registre des violations de données + délai légal de 72 h.
router.register(r'violations-donnees', ViolationDonneesViewSet,
                basename='grc-violation-donnees')
# NTGRC8 — mises sous séquestre transverses (legal hold), au-delà de la GED.
router.register(r'legal-holds', LegalHoldViewSet, basename='grc-legal-hold')
# NTGRC13 — registre des risques d'entreprise (ERM) + matrice 5×5.
router.register(r'risques-entreprise', RisqueEntrepriseViewSet,
                basename='grc-risque-entreprise')
# NTGRC14 — plans de traitement du risque + suivi des retards.
router.register(r'plans-traitement-risque', PlanTraitementRisqueViewSet,
                basename='grc-plan-traitement-risque')
# NTGRC15 — revues périodiques du risque (journal + cadence).
router.register(r'revues-risque', RevueRisqueViewSet,
                basename='grc-revue-risque')
# NTGRC16 — bibliothèque des contrôles internes (SOX-lite).
router.register(r'controles-internes', ControleInterneViewSet,
                basename='grc-controle-interne')
# NTGRC17 — tests de contrôle planifiés + preuves.
router.register(r'tests-controle', TestControleViewSet,
                basename='grc-test-controle')
# NTGRC18 — constats de déficience + liens risque / CAPA QHSE.
router.register(r'deficiences-controle', DeficienceControleViewSet,
                basename='grc-deficience-controle')
# NTGRC19 — référentiel des politiques internes versionnées.
router.register(r'politiques-internes', PolitiqueInterneViewSet,
                basename='grc-politique-interne')
# NTGRC20 — attestations de lecture des politiques (preuve loi 53-05).
router.register(r'attestations-politique', AttestationPolitiqueViewSet,
                basename='grc-attestation-politique')
# NTGRC22 — questionnaires de conformité fournisseurs + leurs réponses.
router.register(r'questionnaires-fournisseur', QuestionnaireFournisseurViewSet,
                basename='grc-questionnaire-fournisseur')
router.register(r'reponses-questionnaire', ReponseQuestionnaireViewSet,
                basename='grc-reponse-questionnaire')
# NTGRC23 — trames réutilisables + instanciation d'un questionnaire.
router.register(r'modeles-questionnaire', ModeleQuestionnaireViewSet,
                basename='grc-modele-questionnaire')
# NTGRC25 — registre des incidents de sécurité (≠ violations de données).
router.register(r'incidents-securite', IncidentSecuriteViewSet,
                basename='grc-incident-securite')
# NTGRC27 — analyses d'impact (AIPD) des traitements à haut risque.
router.register(r'analyses-dpia', AnalyseImpactDPIAViewSet,
                basename='grc-analyse-dpia')

urlpatterns = [
    # NTGRC2 — portail PUBLIC de dépôt/suivi d'une demande de droit
    # (loi 09-08). AllowAny + throttle ; déclarés AVANT le routeur pour que
    # « public » ne puisse jamais être capté par un préfixe de viewset.
    path('public/demande-droit/', deposer_demande_droit,
         name='grc-demande-droit-depot'),
    path('public/demande-droit/<str:token>/', suivre_demande_droit,
         name='grc-demande-droit-suivi'),
    # NTGRC24 — portail PUBLIC du fournisseur : il répond à SON questionnaire
    # sans compte, par un jeton opaque à durée de vie bornée.
    path('public/questionnaire/<str:token>/', questionnaire_public,
         name='grc-questionnaire-public'),
    # NTGRC28 — cockpit de conformité du DPO (7 compteurs en un appel).
    path('tableau-bord-dpo/', tableau_bord_dpo, name='grc-tableau-bord-dpo'),
    path('', include(router.urls)),
]
