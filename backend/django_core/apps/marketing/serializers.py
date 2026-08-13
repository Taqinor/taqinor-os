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
from rest_framework import serializers

from .models import ArcJourney, ModeleJourney, NoeudJourney


# ── NTMKT12 — Journey en graphe ─────────────────────────────────────────────
# ``company`` n'est JAMAIS acceptée du corps de requête : elle est forcée en
# ``perform_create`` côté ViewSet depuis ``request.user.company``.

class _CompanyScopedSerializer(serializers.ModelSerializer):
    """Refuse toute référence à un objet d'une AUTRE société (fuite inter-
    sociétés) : la société de référence vient de ``request.user``, jamais du
    corps de la requête."""

    #: champs FK dont la société doit correspondre à celle de l'utilisateur
    champs_scopes = ()

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None:
            for champ in self.champs_scopes:
                objet = attrs.get(champ)
                if objet is not None and objet.company_id != company.id:
                    raise serializers.ValidationError(
                        {champ: "Référence hors de votre société."})
        return attrs


class NoeudJourneySerializer(_CompanyScopedSerializer):
    champs_scopes = ('sequence',)

    class Meta:
        model = NoeudJourney
        fields = [
            'id', 'sequence', 'type_noeud', 'libelle',
            'position_x', 'position_y', 'config',
        ]


class ArcJourneySerializer(_CompanyScopedSerializer):
    champs_scopes = ('source', 'cible')

    class Meta:
        model = ArcJourney
        fields = ['id', 'source', 'cible', 'condition', 'valeur', 'ordre']


class ModeleJourneySerializer(serializers.ModelSerializer):
    """NTMKT15 — gabarit de journey (graphe pré-construit) prêt à instancier."""

    class Meta:
        model = ModeleJourney
        fields = ['id', 'nom', 'categorie', 'description', 'graphe',
                  'date_creation']
        read_only_fields = ['date_creation']
