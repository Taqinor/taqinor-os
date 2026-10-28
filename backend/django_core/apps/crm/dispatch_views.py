"""Attribution des leads par le responsable d'équipe — routes (27/10/2026).

* ``GET  /crm/dispatch/`` — la file du responsable (contrat
  ``contract_samples/dispatch_leads.json``) ;
* ``POST /crm/dispatch/<lead_id>/attribuer/`` ``{"owner": <id>}`` — sa
  décision ;
* ``/crm/regles-attribution/`` — les règles de Paramètres → Leads (lecture
  tout rôle ; écriture Admin, ou le responsable pour SA seule équipe).

La logique vit dans ``dispatch.py`` ; ce module ne fait que lire la requête.
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core.conflit_etat import ConflitEtat
from core.viewsets import CompanyScopedModelViewSet

from . import dispatch
from . import schema_docs as sd
from .champs_api import MAPPING_STRICT_COMPLET
from .models import Lead
from .models_clients import RegleAttribution
from .params_requete import corps_objet, entier_param
from .serializers import _CompanyScopedRelationsMixin

_TYPES = [('', 'Tous')] + list(Lead.TypeInstallation.choices)
_SOURCES = [('', 'Toutes')] + list(Lead.Canal.choices)


class RegleAttributionSerializer(_CompanyScopedRelationsMixin,
                                 serializers.ModelSerializer):
    """Une règle de proposition. Décimaux en CHAÎNE (``"1500.00"``), entiers
    JSON réels. ``membre`` doit être un membre ACTIF de l'équipe (409 sinon :
    c'est l'état de l'équipe qui s'y oppose)."""
    scoped_relations = ('equipe', 'membre')
    serializer_field_mapping = MAPPING_STRICT_COMPLET

    type_installation = serializers.ChoiceField(
        choices=_TYPES, required=False, allow_blank=True)
    source = serializers.ChoiceField(
        choices=_SOURCES, required=False, allow_blank=True)
    membre_nom = serializers.SerializerMethodField()

    class Meta:
        model = RegleAttribution
        fields = ['id', 'equipe', 'ordre', 'villes', 'type_installation',
                  'source', 'facture_min', 'facture_max', 'membre',
                  'membre_nom', 'actif']
        extra_kwargs = {'membre': {'required': True, 'allow_null': False},
                        'facture_min': {'min_value': 0},
                        'facture_max': {'min_value': 0}}

    def get_membre_nom(self, obj) -> str:
        return dispatch.nom_affiche(obj.membre) or ''

    def validate(self, attrs):
        attrs = super().validate(attrs)
        inst = self.instance
        bas = attrs.get('facture_min', inst.facture_min if inst else None)
        haut = attrs.get('facture_max', inst.facture_max if inst else None)
        if bas is not None and haut is not None and bas > haut:
            raise serializers.ValidationError(
                {'facture_max': 'La facture maximale doit dépasser la minimale.'})
        equipe = attrs.get('equipe', inst.equipe if inst else None)
        membre = attrs.get('membre', inst.membre if inst else None)
        if equipe is not None and not dispatch.membre_actif(equipe, membre):
            raise ConflitEtat("Ce commercial n'est pas un membre actif de l'équipe.")
        return attrs


def _verifier_ecriture(user, *equipes):
    """Admin : toute équipe. Sinon : uniquement l'équipe dont on est le
    responsable — jamais celle d'un autre (403)."""
    if getattr(user, 'is_admin_role', False):
        return
    for equipe in equipes:
        if equipe is None or equipe.responsable_id != user.pk:
            raise PermissionDenied(
                "Seul le responsable de l'équipe modifie ses règles.")


@extend_schema_view(list=extend_schema(parameters=[
    sd.param_entier_ou_vide('equipe', "Identifiant de l'équipe.")]))
class RegleAttributionViewSet(CompanyScopedModelViewSet):
    """Règles d'attribution (Paramètres → Leads). Société forcée côté serveur."""
    parser_classes = [JSONParser]
    queryset = RegleAttribution.objects.select_related('membre').all()
    serializer_class = RegleAttributionSerializer
    permission_classes = [IsAnyRole]
    # YAPIC2/YAPIC11 — tri et recherche explicites (jamais un champ libre).
    ordering_fields = ['ordre', 'id']
    ordering = ['equipe_id', 'ordre', 'id']
    search_fields = ['villes']

    def get_queryset(self):
        qs = super().get_queryset()
        equipe = entier_param(self.request, 'equipe')
        if equipe is not None:
            qs = qs.filter(equipe_id=equipe)
        return qs.order_by('equipe_id', 'ordre', 'id')

    def get_object(self):
        obj = super().get_object()
        if self.request.method not in ('GET', 'HEAD', 'OPTIONS'):
            _verifier_ecriture(self.request.user, obj.equipe)
        return obj

    def perform_create(self, serializer):
        _verifier_ecriture(self.request.user, serializer.validated_data.get('equipe'))
        super().perform_create(serializer)

    def perform_update(self, serializer):
        _verifier_ecriture(
            self.request.user,
            serializer.validated_data.get('equipe', serializer.instance.equipe))
        super().perform_update(serializer)


@extend_schema(responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([IsAnyRole])
def dispatch_file(request):
    """La file d'attente du responsable d'équipe (Direction/Admin : toutes)."""
    file = dispatch.file_attente(request.user)
    return Response({
        'equipe': file['equipe'],
        'en_attente': file['en_attente'],
        'leads': file['leads'],
        'membres': file['membres'],
    })


@extend_schema(request=sd.corps('CrmDispatchAttribuerRequest',
                                owner=serializers.IntegerField()),
               responses=sd.OBJ)
@api_view(['POST'])
@parser_classes([JSONParser])
@permission_classes([IsAnyRole])
def dispatch_attribuer(request, lead_id):
    """Décision du responsable : ``{"owner": <id>}`` (Entrée = la proposition)."""
    owner = corps_objet(request).get('owner')
    if isinstance(owner, bool) or not isinstance(owner, int):
        raise serializers.ValidationError(
            {'owner': 'Un identifiant entier est attendu.'})
    lead = dispatch.attribuer(request.user, lead_id, owner)
    return Response({'id': lead.pk, 'owner': lead.owner_id,
                     'owner_nom': dispatch.nom_affiche(lead.owner)})
