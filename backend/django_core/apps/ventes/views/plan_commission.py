"""WIR281/XSAL6 — exposition REST des plans de commission.

Le modèle ``ventes.PlanCommission`` et le résolveur
``ventes.selectors.resoudre_plan_commission`` existaient depuis XSAL6, mais
AUCUNE route ne les servait : un plan ne pouvait naître que dans l'admin
Django, donc le reporting commercial retombait toujours sur
``CompanyProfile.commission_mode``.

Endpoints :
  GET/POST            /ventes/plans-commission/            list/create
  GET/PATCH/DELETE    /ventes/plans-commission/{id}/       retrieve/update/destroy
  GET                 /ventes/plans-commission/resoudre/?owner=<id>

GARDE MARGE (WIR281, explicite) : aucun montant de marge ni prix d'achat n'est
exposé — le payload ne porte qu'une ÉTIQUETTE de base, un pourcentage de règle
et un barème MAD/kWc. L'endpoint ENTIER est gaté
``HasPermissionOrLegacy('prix_achat_voir')`` : un plan peut porter la base
``marge_interne``, le sujet appartient au même palier de confidentialité que
les prix d'achat.

La priorité de résolution (plan dédié → plan par défaut société → mode société)
n'est JAMAIS réimplémentée ici : l'action ``resoudre`` appelle le sélecteur
existant, l'unique source de vérité, celle que ``reporting/insights`` utilise
déjà. Contrat partagé : ``apps/ventes/contract_samples/plan_commission.json``.
"""
import re

from drf_spectacular.utils import extend_schema_view
from ..openapi_params import entier_requete, qstr
from drf_spectacular.utils import extend_schema
from . import openapi_docs as D
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework.parsers import JSONParser
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from authentication.permissions import HasPermissionOrLegacy
from core.viewsets import CompanyScopedModelViewSet

from ..models import PlanCommission
from ..serializers import PlanCommissionSerializer

# GARDE MARGE — un seul palier pour toutes les actions (lecture comprise).
PLAN_COMMISSION_PERMISSION = HasPermissionOrLegacy('prix_achat_voir')

VRAI = {'1', 'true', 'True', 'oui', 'vrai'}
FAUX = {'0', 'false', 'False', 'non', 'faux'}


#: ENF11 — le barème suit la base (``PlanCommissionSerializer.validate``) :
#: « par_kwc » exige ``montant_par_kwc``, les bases au pourcentage exigent
#: ``taux_pct`` (non nuls, non vides) — publié sur la création et le PUT.
_BAREME_SELON_BASE = D.corps_resserre({'anyOf': [
    {'properties': {'base': {'enum': ['par_kwc']},
                    'montant_par_kwc': {'type': 'string', 'minLength': 1}},
     'required': ['montant_par_kwc']},
    {'properties': {'base': {'enum': ['ca_devis_signe', 'marge_interne']},
                    'taux_pct': {'type': 'string', 'minLength': 1}},
     'required': ['taux_pct']},
]})
#: api-fuzz-pr 30/10 (ENF11) — PATCH : le barème ENVOYÉ suit la base ENVOYÉE
#: (``{"base": "ca_devis_signe", "taux_pct": null}`` était « conforme » puis
#: refusé 400) ; chaque clé reste facultative. Ce que le corps ne dit pas est
#: complété par le plan stocké — un refus qui en vient est un 409 d'état.
_BAREME_SELON_BASE_PATCH = D.corps_resserre({'anyOf': [
    {'properties': {'base': {'enum': ['par_kwc']},
                    'montant_par_kwc': {'type': 'string', 'minLength': 1}}},
    {'properties': {'base': {'enum': ['ca_devis_signe', 'marge_interne']},
                    'taux_pct': {'type': 'string', 'minLength': 1}}},
]})


#: Vide (plans par défaut) ou identifiant entier (9 chiffres au plus, comme MOTIF_IDS du stock).
MOTIF_OWNER = r'^(|[1-9][0-9]{0,8})$'


@extend_schema_view(list=extend_schema(
    # ENF11 (nocturne 15/10) — `owner` : vide (plans par défaut) OU un id entier,
    # le motif PUBLIÉ est celui que le filtre applique (400 sinon).
    parameters=[OpenApiParameter('owner', {'type': 'string', 'pattern': MOTIF_OWNER},
                                 description='id du commercial ; vide = plans par défaut.'),
                qstr('actif', desc='1/0.')]),
    create=extend_schema(extensions=_BAREME_SELON_BASE),
    update=extend_schema(extensions=_BAREME_SELON_BASE),
    partial_update=extend_schema(extensions=_BAREME_SELON_BASE_PATCH))
class PlanCommissionViewSet(CompanyScopedModelViewSet):
    """XSAL6 — CRUD des plans de commission de la société.

    ``owner`` nul = plan PAR DÉFAUT de la société. La société est TOUJOURS
    forcée côté serveur (jamais acceptée du corps) et le queryset est scopé à
    celle du demandeur."""
    parser_classes = [JSONParser]  # ENF11/D2 : aucun envoi de fichier
    queryset = PlanCommission.objects.select_related('owner').all()
    serializer_class = PlanCommissionSerializer
    permission_classes = [PLAN_COMMISSION_PERMISSION]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()

        params = self.request.query_params
        # `?owner=` (vide) cible explicitement les plans PAR DÉFAUT ; un id
        # cible ce commercial. Paramètre absent = aucun filtre.
        if 'owner' in params:
            owner = params.get('owner')
            if not re.fullmatch(MOTIF_OWNER, owner):
                raise ValidationError({'owner': ['Vide ou identifiant entier attendu.']})
            qs = qs.filter(owner__isnull=True) if not owner \
                else qs.filter(owner_id=owner)
        actif = params.get('actif')
        if actif in VRAI:
            qs = qs.filter(actif=True)
        elif actif in FAUX:
            qs = qs.filter(actif=False)
        return qs

    def _check_owner_tenant(self, serializer):
        """Le commercial visé doit appartenir à la société du demandeur — sans
        cette garde, un id d'utilisateur d'une AUTRE société créerait un plan
        croisé (fuite inter-tenant)."""
        owner = serializer.validated_data.get('owner')
        if owner is None:
            return
        company_id = getattr(self.request.user.company, 'id', None)
        if getattr(owner, 'company_id', None) != company_id:
            raise ValidationError({'owner': 'Commercial inconnu.'})

    def perform_create(self, serializer):
        self._check_owner_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_owner_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @extend_schema(
        parameters=[OpenApiParameter('owner', OpenApiTypes.INT, required=False)],
        responses=D.ResoudrePlanResponse)
    @action(detail=False, methods=['get'], url_path='resoudre')
    def resoudre(self, request):
        """XSAL6 — plan RÉELLEMENT appliqué à un commercial.

        Délègue au sélecteur existant ``resoudre_plan_commission`` : la
        priorité (plan dédié → plan par défaut société) n'est jamais
        réimplémentée ici. ``source`` dit d'où vient le plan ; ``mode_societe``
        avec ``plan: null`` signifie que l'appelant retombe sur
        ``CompanyProfile.commission_mode`` (comportement historique)."""
        from ..selectors import resoudre_plan_commission

        company = request.user.company
        # ENF11 — ``?owner=`` publié entier : illisible = 400 ; un id bien
        # formé mais inconnu de la société (``0`` compris) = 404, comme
        # n'importe quelle ressource introuvable — jamais un 400.
        owner_id = entier_requete(request, 'owner')
        owner = None
        if owner_id is not None:
            # Le commercial est résolu DANS la société du demandeur : un id
            # étranger répond comme un id inexistant.
            from django.contrib.auth import get_user_model
            owner = get_user_model().objects.filter(
                pk=owner_id, company=company).first() if (
                    0 < owner_id < 2 ** 31) else None
            if owner is None:
                raise NotFound('Commercial inconnu.')

        plan = resoudre_plan_commission(company, owner)
        if plan is None:
            source = 'mode_societe'
        elif plan.owner_id is None:
            source = 'plan_defaut_societe'
        else:
            source = 'plan_dedie'
        return Response({
            'owner': owner.id if owner is not None else None,
            'source': source,
            'plan': PlanCommissionSerializer(plan).data if plan else None,
        })
