"""Serializers du module Marketing (``apps.marketing``).

ODX10 — ré-export TRANSITOIRE des serializers marketing qui vivent encore dans
``apps.compta.serializers`` (interleavés avec les serializers comptables). Ce
module expose ``apps.marketing.serializers`` pour les ViewSets marketing et les
nouvelles routes ``/api/django/marketing/…`` ; ODX22 re-logera leur corps ici.
"""

from apps.compta.serializers import (  # noqa: F401
    AbonnementListeSerializer,
    AppelTelephoniqueSerializer,
    ApprobationEnvoiCampagneSerializer,
    AvisClientSerializer,
    BilletEvenementSerializer,
    CampagneSerializer,
    CommunicationEvenementSerializer,
    CompteFideliteSerializer,
    DomaineEnvoiSerializer,
    EnqueteNPSSerializer,
    EnqueteSerializer,
    EnvoiCampagneSerializer,
    EtapeSequenceSerializer,
    EvenementMarketingSerializer,
    ExecutionEtapeSequenceSerializer,
    FormulaireIntakeSerializer,
    InscriptionEvenementSerializer,
    InscriptionSequenceSerializer,
    ListeDiffusionSerializer,
    MessageWhatsAppEntrantSerializer,
    MouvementFideliteSerializer,
    OuverturePartageSerializer,
    QuestionEvenementSerializer,
    RegleUpsellSerializer,
    RelanceDevisAbandonneSerializer,
    ReponseEnqueteSerializer,
    SegmentMarketingSerializer,
    SequenceRelanceSerializer,
    SupportOfflineSerializer,
    TypeEvenementSerializer,
)
