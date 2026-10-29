"""Attribution des leads par le responsable d'équipe — routes (27/10/2026).

* ``GET  /crm/dispatch/`` — la file du responsable (contrat
  ``contract_samples/dispatch_leads.json``) ;
* ``POST /crm/dispatch/<lead_id>/attribuer/`` ``{"owner": <id>}`` — sa
  décision ;
* ``PATCH /crm/dispatch/reglages/<equipe_id>/`` — l'interrupteur
  « Le responsable confirme chaque lead » et le délai d'une équipe ;
* ``/crm/regles-attribution/`` — les règles de Paramètres → Leads (lecture
  tout rôle de la société ; écriture : ``dispatch.peut_regler`` — Admin, le
  responsable de l'équipe ou la tête de son département).

La logique vit dans ``dispatch.py`` ; ce module ne fait que lire la requête.
"""
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core.champs_stricts import EntierStrict
from core.conflit_etat import ConflitEtat
from core.viewsets import CompanyScopedModelViewSet

from . import dispatch
from . import schema_docs as sd
from .champs_api import MAPPING_STRICT_COMPLET, BooleenStrict
from .models import Lead
from .models_clients import RegleAttribution
from .params_requete import corps_objet, entier_param
from .serializers import _CompanyScopedRelationsMixin


def _sans_doublons(valeurs):
    """Ordre de saisie gardé, doublons retirés (``[]`` = tous)."""
    return list(dict.fromkeys(valeurs))


class RegleAttributionSerializer(_CompanyScopedRelationsMixin,
                                 serializers.ModelSerializer):
    """Une règle de proposition. Décimaux en CHAÎNE (``"1500.00"``), entiers
    JSON réels. ``membre`` doit être un membre ACTIF de l'équipe (409 sinon :
    c'est l'état de l'équipe qui s'y oppose)."""
    scoped_relations = ('equipe', 'membre')
    serializer_field_mapping = MAPPING_STRICT_COMPLET

    # Choix multiples (fondateur, 28/10/2026) — liste JSON stricte (un
    # non-tableau → 400 nommant le champ), chaque valeur dans les choix du
    # lead, doublons retirés ; ``[]`` = tous.
    types_installation = serializers.ListField(
        child=serializers.ChoiceField(choices=Lead.TypeInstallation.choices),
        required=False)
    sources = serializers.ListField(
        child=serializers.ChoiceField(choices=Lead.Canal.choices),
        required=False)
    membre_nom = serializers.SerializerMethodField()

    class Meta:
        model = RegleAttribution
        fields = ['id', 'equipe', 'ordre', 'villes', 'types_installation',
                  'sources', 'facture_min', 'facture_max', 'membre',
                  'membre_nom', 'actif']
        extra_kwargs = {'membre': {'required': True, 'allow_null': False},
                        'facture_min': {'min_value': 0},
                        'facture_max': {'min_value': 0}}

    def get_membre_nom(self, obj) -> str:
        return dispatch.nom_affiche(obj.membre) or ''

    def validate_types_installation(self, valeur):
        return _sans_doublons(valeur)

    def validate_sources(self, valeur):
        return _sans_doublons(valeur)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        inst = self.instance
        bas = attrs.get('facture_min', inst.facture_min if inst else None)
        haut = attrs.get('facture_max', inst.facture_max if inst else None)
        if bas is not None and haut is not None and bas > haut:
            # api-fuzz-full 28/10 (ENF11) : règle entre deux champs,
            # inexprimable au schéma OpenAPI 3.0 — refus d'état 409.
            raise ConflitEtat(
                {'facture_max': 'La facture maximale doit dépasser la minimale.'})
        equipe = attrs.get('equipe', inst.equipe if inst else None)
        membre = attrs.get('membre', inst.membre if inst else None)
        if equipe is not None and not dispatch.membre_actif(equipe, membre):
            raise ConflitEtat("Ce commercial n'est pas un membre actif de l'équipe.")
        return attrs


def _verifier_ecriture(user, *equipes):
    """Écriture d'une règle : ``dispatch.peut_regler`` sur CHAQUE équipe
    touchée (Admin ; responsable de l'équipe ; tête de son département) —
    jamais l'équipe d'un autre (403)."""
    for equipe in equipes:
        if not dispatch.peut_regler(user, equipe):
            raise PermissionDenied(
                "Seuls le responsable de l'équipe, le directeur commercial et "
                "la Direction modifient ses règles.")


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
        'equipes_reglables': file['equipes_reglables'],
    })


class ReglagesEquipeSerializer(serializers.Serializer):
    """Corps de ``PATCH crm/dispatch/reglages/<equipe_id>/`` — types JSON
    exacts (``1`` n'est pas un booléen, ``"5"`` n'est pas un entier)."""
    confirmation_responsable = BooleenStrict(required=False)
    # Minutes OUVRÉES, bornées à une journée de travail (comme l'équipe).
    delai_minutes = EntierStrict(min_value=1, max_value=480, required=False)


@extend_schema(request=ReglagesEquipeSerializer,
               # ``inline_serializer`` direct : ``sd.corps(nom, **champs)``
               # entrerait en collision avec le champ « nom » de la réponse.
               responses=inline_serializer('CrmDispatchReglagesReponse', {
                   'id': serializers.IntegerField(),
                   'nom': serializers.CharField(),
                   'confirmation_responsable': serializers.BooleanField(),
                   'delai_minutes': serializers.IntegerField()}))
@api_view(['PATCH'])
@parser_classes([JSONParser])
@permission_classes([IsAnyRole])
def dispatch_reglages(request, equipe_id):
    """Interrupteur « Le responsable confirme chaque lead » et délai d'une
    équipe : responsable, directeur commercial (tête du département) ou
    Direction/Admin. 404 hors société, 403 sans droit."""
    corps = ReglagesEquipeSerializer(data=corps_objet(request))
    corps.is_valid(raise_exception=True)
    return Response(dispatch.modifier_reglages(
        request.user, equipe_id, corps.validated_data))


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
