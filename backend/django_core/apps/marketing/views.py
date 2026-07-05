"""Vues du module Marketing (``apps.marketing``).

ODX10 — ré-export TRANSITOIRE des ViewSets et vues publiques marketing qui
vivent encore dans ``apps.compta.views`` (interleavés avec les ViewSets
comptables et adossés à ``_ComptaBaseViewSet`` = ``TenantMixin`` +
``ModelViewSet``, avec le scoping ``request.user.company`` et l'assignation
forcée de ``company`` en ``perform_create``). Ce module donne aux nouvelles
routes ``/api/django/marketing/…`` un point d'entrée ``apps.marketing.views``
stable ; les anciennes routes ``/api/django/compta/…`` continuent de servir les
MÊMES classes. ODX22 re-logera le corps ici.
"""

from apps.compta.views import (  # noqa: F401
    # ViewSets marketing (mailing, séquences, tracking, formulaires, appels).
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
    # Vues publiques (token, sans login) : désinscription, opt-in, redirection
    # de lien tracké, enquêtes publiques + certificat, inscription événement,
    # webhooks Brevo / STOP SMS.
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
