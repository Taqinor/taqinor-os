"""Routes du module Marketing (``apps.marketing``) — ODX10.

Nouveau préfixe ``/api/django/marketing/…``. Les mêmes ViewSets/vues publiques
sont AUSSI servis par ``apps.compta.urls`` sous ``/api/django/compta/…`` (routes
historiques conservées à l'identique pour ne casser aucun client). Les ViewSets
gardent le scoping ``request.user.company`` + l'assignation forcée de
``company`` (hérité de ``_ComptaBaseViewSet`` = ``TenantMixin``).

Basenames explicitement préfixés ``mkt-…`` pour NE PAS entrer en collision avec
les noms d'URL du routeur compta (qui reverse ``campagne-list`` etc.).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .public_views import (
    formulaire_intake_public,
    formulaire_intake_soumettre,
)
from .views import (
    AbonnementListeViewSet,
    AppelTelephoniqueViewSet,
    ApprobationEnvoiCampagneViewSet,
    AvisClientViewSet,
    BilletEvenementViewSet,
    CampagneViewSet,
    CommunicationEvenementViewSet,
    CompteFideliteViewSet,
    DomaineEnvoiViewSet,
    EnqueteNPSViewSet,
    EnqueteViewSet,
    EnvoiCampagneViewSet,
    EtapeSequenceViewSet,
    EvenementMarketingViewSet,
    FormulaireIntakeViewSet,
    InscriptionEvenementViewSet,
    InscriptionSequenceViewSet,
    ListeDiffusionViewSet,
    MessageWhatsAppEntrantViewSet,
    MouvementFideliteViewSet,
    OuverturePartageViewSet,
    QuestionEvenementViewSet,
    RegleUpsellViewSet,
    RelanceDevisAbandonneViewSet,
    SegmentMarketingViewSet,
    SequenceRelanceViewSet,
    SupportOfflineViewSet,
    TypeEvenementViewSet,
    desinscription_publique,
    double_optin_confirmer,
    enquete_certificat_pdf,
    enquete_publique,
    enquete_soumettre,
    evenement_inscription_publique,
    redirection_lien_tracke,
    webhook_brevo_campagne,
    webhook_sms_stop,
)

router = DefaultRouter()
# ── Mailing / campagnes (FG201, XMKT*) ──────────────────────────────────────
router.register(r'campagnes', CampagneViewSet, basename='mkt-campagne')
router.register(r'envois-campagne', EnvoiCampagneViewSet,
                basename='mkt-envoi-campagne')
router.register(r'approbations-envoi-campagne', ApprobationEnvoiCampagneViewSet,
                basename='mkt-approbation-envoi-campagne')
router.register(r'listes-diffusion', ListeDiffusionViewSet,
                basename='mkt-liste-diffusion')
router.register(r'abonnements-liste', AbonnementListeViewSet,
                basename='mkt-abonnement-liste')
router.register(r'segments-marketing', SegmentMarketingViewSet,
                basename='mkt-segment-marketing')
# ── Séquences de relance (FG202, XMKT1) ─────────────────────────────────────
router.register(r'sequences-relance', SequenceRelanceViewSet,
                basename='mkt-sequence-relance')
router.register(r'etapes-sequence', EtapeSequenceViewSet,
                basename='mkt-etape-sequence')
router.register(r'inscriptions-sequence', InscriptionSequenceViewSet,
                basename='mkt-inscription-sequence')
# ── Récupération devis / ouvertures / formulaires / capture (FG203–208) ─────
router.register(r'relances-devis-abandonnes', RelanceDevisAbandonneViewSet,
                basename='mkt-relance-devis-abandonne')
router.register(r'ouvertures-partage', OuverturePartageViewSet,
                basename='mkt-ouverture-partage')
router.register(r'formulaires-intake', FormulaireIntakeViewSet,
                basename='mkt-formulaire-intake')
router.register(r'messages-whatsapp', MessageWhatsAppEntrantViewSet,
                basename='mkt-message-whatsapp')
router.register(r'appels', AppelTelephoniqueViewSet, basename='mkt-appel')
# ── Enquêtes / NPS / avis / fidélité / upsell (FG238–241) ───────────────────
router.register(r'enquetes-nps', EnqueteNPSViewSet, basename='mkt-enquete-nps')
router.register(r'avis-clients', AvisClientViewSet, basename='mkt-avis-client')
router.register(r'comptes-fidelite', CompteFideliteViewSet,
                basename='mkt-compte-fidelite')
router.register(r'mouvements-fidelite', MouvementFideliteViewSet,
                basename='mkt-mouvement-fidelite')
router.register(r'regles-upsell', RegleUpsellViewSet,
                basename='mkt-regle-upsell')
# ── Enquêtes configurables (XMKT27) ─────────────────────────────────────────
router.register(r'enquetes', EnqueteViewSet, basename='mkt-enquete')
# ── Événements marketing (XMKT28, ZMKT14–17) ────────────────────────────────
router.register(r'evenements-marketing', EvenementMarketingViewSet,
                basename='mkt-evenement-marketing')
router.register(r'inscriptions-evenement', InscriptionEvenementViewSet,
                basename='mkt-inscription-evenement')
router.register(r'types-evenement', TypeEvenementViewSet,
                basename='mkt-type-evenement')
router.register(r'billets-evenement', BilletEvenementViewSet,
                basename='mkt-billet-evenement')
router.register(r'questions-evenement', QuestionEvenementViewSet,
                basename='mkt-question-evenement')
router.register(r'communications-evenement', CommunicationEvenementViewSet,
                basename='mkt-communication-evenement')
# ── Supports offline QR (XMKT29) ────────────────────────────────────────────
router.register(r'supports-offline', SupportOfflineViewSet,
                basename='mkt-support-offline')
# ── Domaines d'envoi (XMKT33) ───────────────────────────────────────────────
router.register(r'domaines-envoi', DomaineEnvoiViewSet,
                basename='mkt-domaine-envoi')

urlpatterns = [
    # Vues publiques (token, sans login) — préfixées de noms `mkt-…` pour ne
    # pas entrer en collision avec les mêmes vues servies sous /compta/….
    path('webhooks/brevo/', webhook_brevo_campagne,
         name='mkt-webhook-brevo-campagne'),
    path('webhooks/sms-stop/', webhook_sms_stop, name='mkt-webhook-sms-stop'),
    path('desinscription/<str:token>/', desinscription_publique,
         name='mkt-desinscription-publique'),
    path('double-optin/<str:token>/', double_optin_confirmer,
         name='mkt-double-optin-confirmer'),
    path('r/<str:token>/', redirection_lien_tracke,
         name='mkt-redirection-lien-tracke'),
    path('enquetes-publiques/<str:token>/', enquete_publique,
         name='mkt-enquete-publique'),
    path('enquetes-publiques/<str:token>/soumettre/', enquete_soumettre,
         name='mkt-enquete-soumettre'),
    path('reponses-enquete/<int:reponse_id>/certificat/', enquete_certificat_pdf,
         name='mkt-enquete-certificat-pdf'),
    path('evenements-marketing/<int:evenement_id>/inscription-publique/',
         evenement_inscription_publique,
         name='mkt-evenement-inscription-publique'),
    # WIR64/FG206 — capture de lead publique (landing tokenisée par slug).
    path('intake/<slug:slug>/', formulaire_intake_public,
         name='mkt-formulaire-intake-public'),
    path('intake/<slug:slug>/soumettre/', formulaire_intake_soumettre,
         name='mkt-formulaire-intake-soumettre'),
    path('', include(router.urls)),
]
