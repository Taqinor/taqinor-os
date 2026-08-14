"""Routes du module Marketing (``apps.marketing``) — ODX10.

Préfixe ``/api/django/marketing/…``. PACT26 — le double montage historique
qui re-servait ces mêmes ViewSets/vues publiques sous ``apps.compta.urls``
(``/api/django/compta/…``) a été retiré : seul ``campagnes`` avait un
appelant frontend vivant (``CampagnesScreen.jsx`` via ``comptaApi``), migré
vers ce module. Les ViewSets gardent le scoping ``request.user.company`` +
l'assignation forcée de ``company`` (hérité de ``_ComptaBaseViewSet`` =
``TenantMixin``).

Basenames explicitement préfixés ``mkt-…`` (héritage de l'époque où le routeur
compta reversait ``campagne-list`` etc. sous les mêmes noms) : conservé pour
ne pas risquer de collision ailleurs.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .public_views import (
    formulaire_intake_public,
    formulaire_intake_soumettre,
    preferences_publiques,
)
from .views import (
    AbonnementListeViewSet,
    AppelTelephoniqueViewSet,
    ArcJourneyViewSet,
    ApprobationEnvoiCampagneViewSet,
    AvisClientViewSet,
    BilletEvenementViewSet,
    BlocContenuViewSet,
    CampagneViewSet,
    CommunicationEvenementViewSet,
    CompteFideliteViewSet,
    DomaineEnvoiViewSet,
    EnqueteNPSViewSetNotifiant,
    EnqueteViewSet,
    EnvoiCampagneViewSet,
    EtapeSequenceViewSet,
    EvenementMarketingViewSet,
    FormulaireIntakeViewSet,
    InscriptionEvenementViewSet,
    InscriptionSequenceViewSet,
    ListeDiffusionViewSet,
    MessageWhatsAppEntrantViewSet,
    ModeleJourneyViewSet,
    MouvementFideliteViewSet,
    NoeudJourneyViewSet,
    OuverturePartageViewSet,
    QuestionEvenementViewSet,
    RegleUpsellViewSet,
    RelanceDevisAbandonneViewSet,
    SegmentMarketingViewSet,
    SequenceRelanceViewSet,
    SupportOfflineViewSet,
    TypeEvenementViewSet,
    VersionFormulaireIntakeViewSet,
    attribution_comparaison_view,
    campagne_rapport_pdf_view,
    desinscription_publique,
    double_optin_confirmer,
    enquete_certificat_pdf,
    enquete_publique,
    enquete_soumettre,
    evenement_inscription_publique_notifiante,
    export_campagnes_xlsx_view,
    export_envois_campagne_csv_view,
    export_membres_segment_xlsx_view,
    heatmap_engagement_view,
    importer_couts_publicitaires_view,
    importer_inscriptions_evenement_view,
    parametres_marketing_view,
    redirection_lien_tracke,
    registre_consentement_export_pdf_view,
    score_maturite_lead_view,
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
# ── Blocs de contenu réutilisables (NTMKT23) ────────────────────────────────
router.register(r'blocs-contenu', BlocContenuViewSet,
                basename='mkt-bloc-contenu')
# ── Séquences de relance (FG202, XMKT1) ─────────────────────────────────────
router.register(r'sequences-relance', SequenceRelanceViewSet,
                basename='mkt-sequence-relance')
router.register(r'etapes-sequence', EtapeSequenceViewSet,
                basename='mkt-etape-sequence')
router.register(r'inscriptions-sequence', InscriptionSequenceViewSet,
                basename='mkt-inscription-sequence')
# ── Journey en graphe (NTMKT12) ─────────────────────────────────────────────
router.register(r'noeuds-journey', NoeudJourneyViewSet,
                basename='mkt-noeud-journey')
router.register(r'arcs-journey', ArcJourneyViewSet,
                basename='mkt-arc-journey')
# ── Bibliothèque de modèles de journeys (NTMKT15) ───────────────────────────
router.register(r'modeles-journey', ModeleJourneyViewSet,
                basename='mkt-modele-journey')
# ── Récupération devis / ouvertures / formulaires / capture (FG203–208) ─────
router.register(r'relances-devis-abandonnes', RelanceDevisAbandonneViewSet,
                basename='mkt-relance-devis-abandonne')
router.register(r'ouvertures-partage', OuverturePartageViewSet,
                basename='mkt-ouverture-partage')
router.register(r'formulaires-intake', FormulaireIntakeViewSet,
                basename='mkt-formulaire-intake')
# ── Landing pages versionnées (NTMKT16) ─────────────────────────────────────
router.register(r'versions-formulaire-intake', VersionFormulaireIntakeViewSet,
                basename='mkt-version-formulaire-intake')
router.register(r'messages-whatsapp', MessageWhatsAppEntrantViewSet,
                basename='mkt-message-whatsapp')
router.register(r'appels', AppelTelephoniqueViewSet, basename='mkt-appel')
# ── Enquêtes / NPS / avis / fidélité / upsell (FG238–241) ───────────────────
# NTMKT44 — EnqueteNPSViewSetNotifiant (étend la classe compta SANS la
# modifier) : notifie le commercial du lead sur une réponse détractrice.
router.register(r'enquetes-nps', EnqueteNPSViewSetNotifiant,
                basename='mkt-enquete-nps')
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
    # NTMKT24 — heatmap d'engagement jour x heure (lecture seule, informative)
    path('heatmap-engagement/', heatmap_engagement_view,
         name='mkt-heatmap-engagement'),
    # NTMKT26 — import CSV de coûts publicitaires externes (Meta/Google Ads)
    path('campagnes/importer-couts/', importer_couts_publicitaires_view,
         name='mkt-campagnes-importer-couts'),
    # NTMKT27 — bilan de campagne PDF (usage interne)
    path('campagnes/<int:pk>/rapport-pdf/', campagne_rapport_pdf_view,
         name='mkt-campagne-rapport-pdf'),
    # NTMKT39 — export XLSX des campagnes filtrées + CSV de la trace d'envoi
    # d'une campagne (montés AVANT le routeur — un `pk` de routeur DRF
    # avalerait sinon `export` comme s'il s'agissait d'un id).
    path('campagnes/export/', export_campagnes_xlsx_view,
         name='mkt-campagnes-export-xlsx'),
    path('campagnes/<int:pk>/envois/export/',
         export_envois_campagne_csv_view,
         name='mkt-campagne-envois-export-csv'),
    # NTMKT40 — export XLSX des membres résolus d'un segment (audit RGPD/CNDP)
    path('segments-marketing/<int:pk>/export/',
         export_membres_segment_xlsx_view,
         name='mkt-segment-export-membres'),
    # NTMKT41 — import CSV/XLSX d'inscrits en masse (hors formulaire public)
    path('evenements-marketing/<int:pk>/importer-inscrits/',
         importer_inscriptions_evenement_view,
         name='mkt-evenement-importer-inscrits'),
    # NTMKT28 — export PDF du registre de consentement (CNDP)
    path('registre-consentement/export-pdf/',
         registre_consentement_export_pdf_view,
         name='mkt-registre-consentement-export-pdf'),
    # NTMKT31 — réglages tenant du module Marketing
    path('parametres/', parametres_marketing_view,
         name='mkt-parametres-marketing'),
    # NTMKT18/19 — score de maturité d'un lead (fiche/kanban)
    path('scores-maturite/<int:lead_id>/', score_maturite_lead_view,
         name='mkt-score-maturite-lead'),
    # NTMKT20 — comparaison des 4 modèles d'attribution pour un devis signé
    path('attribution/comparaison/', attribution_comparaison_view,
         name='mkt-attribution-comparaison'),
    # Vues publiques (token, sans login) — préfixées de noms `mkt-…` pour ne
    # pas entrer en collision avec les mêmes vues servies sous /compta/….
    # headless: rappel d'etat entrant de Brevo, appele par leur serveur
    path('webhooks/brevo/', webhook_brevo_campagne,
         name='mkt-webhook-brevo-campagne'),
    # headless: rappel STOP entrant de l'operateur SMS, aucun ecran en face
    path('webhooks/sms-stop/', webhook_sms_stop, name='mkt-webhook-sms-stop'),
    # headless: lien de desinscription clique depuis un courriel, hors ERP
    path('desinscription/<str:token>/', desinscription_publique,
         name='mkt-desinscription-publique'),
    # headless: centre de preferences self-service clique depuis un courriel
    # (NTMKT22) — par canal / par liste, jamais une desinscription totale
    path('preferences/<str:token>/', preferences_publiques,
         name='mkt-preferences-publiques'),
    # headless: lien de confirmation double opt-in clique depuis un courriel
    path('double-optin/<str:token>/', double_optin_confirmer,
         name='mkt-double-optin-confirmer'),
    # headless: redirection de lien tracke — le navigateur suit un 302, pas axios
    path('r/<str:token>/', redirection_lien_tracke,
         name='mkt-redirection-lien-tracke'),
    path('enquetes-publiques/<str:token>/', enquete_publique,
         name='mkt-enquete-publique'),
    path('enquetes-publiques/<str:token>/soumettre/', enquete_soumettre,
         name='mkt-enquete-soumettre'),
    path('reponses-enquete/<int:reponse_id>/certificat/', enquete_certificat_pdf,
         name='mkt-enquete-certificat-pdf'),
    # NTMKT44 — enveloppe notifiante (même contrat public, apps.compta.views
    # reste inchangée ; la route legacy /compta/… continue de servir la
    # vue d'origine, sans notification).
    path('evenements-marketing/<int:evenement_id>/inscription-publique/',
         evenement_inscription_publique_notifiante,
         name='mkt-evenement-inscription-publique'),
    # WIR64/FG206 — capture de lead publique (landing tokenisée par slug).
    path('intake/<slug:slug>/', formulaire_intake_public,
         name='mkt-formulaire-intake-public'),
    path('intake/<slug:slug>/soumettre/', formulaire_intake_soumettre,
         name='mkt-formulaire-intake-soumettre'),
    path('', include(router.urls)),
]
