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
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import HasPermissionOrLegacy
from core.viewsets import CompanyScopedModelViewSet

from ..models import PlanCommission
from ..serializers import PlanCommissionSerializer

# GARDE MARGE — un seul palier pour toutes les actions (lecture comprise).
PLAN_COMMISSION_PERMISSION = HasPermissionOrLegacy('prix_achat_voir')

VRAI = {'1', 'true', 'True', 'oui', 'vrai'}
FAUX = {'0', 'false', 'False', 'non', 'faux'}


class PlanCommissionViewSet(CompanyScopedModelViewSet):
    """XSAL6 — CRUD des plans de commission de la société.

    ``owner`` nul = plan PAR DÉFAUT de la société. La société est TOUJOURS
    forcée côté serveur (jamais acceptée du corps) et le queryset est scopé à
    celle du demandeur."""
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
        owner_id = request.query_params.get('owner') or None
        owner = None
        if owner_id:
            # Le commercial est résolu DANS la société du demandeur : un id
            # étranger se comporte comme « aucun commercial », jamais comme un
            # accès à une autre société.
            from django.contrib.auth import get_user_model
            owner = get_user_model().objects.filter(
                pk=owner_id, company=company).first()
            if owner is None:
                raise ValidationError({'owner': 'Commercial inconnu.'})

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
