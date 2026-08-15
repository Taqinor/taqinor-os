"""NTP2P4 — Budgets d'engagement par département.

CRUD des enveloppes (``BudgetDepartement``) + consultation de leur
consommation (``engagé`` vs ``réalisé``). Les ENGAGEMENTS eux-mêmes ne sont
pas écrits par l'API : ils sont posés côté serveur à la soumission d'une
demande d'achat (``stock.services.engager_budget``), donc exposés en LECTURE
SEULE ici.
"""
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.mixins import TenantMixin
from core.viewsets import CompanyScopedModelViewSet

from .. import selectors
from ..models import BudgetDepartement, EngagementBudget


class BudgetDepartementSerializer(serializers.ModelSerializer):
    departement_nom = serializers.CharField(
        source='departement.nom', read_only=True, default=None)
    periodicite_display = serializers.CharField(
        source='get_periodicite_display', read_only=True, default=None)

    class Meta:
        model = BudgetDepartement
        fields = [
            'id', 'departement', 'departement_nom', 'periodicite',
            'periodicite_display', 'annee', 'mois', 'montant_alloue',
            'actif', 'note', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        def valeur(champ, defaut=None):
            if champ in attrs:
                return attrs[champ]
            return getattr(self.instance, champ, defaut)

        periodicite = valeur('periodicite', BudgetDepartement.Periodicite.ANNUELLE)
        mois = valeur('mois', 0) or 0
        if periodicite == BudgetDepartement.Periodicite.MENSUELLE:
            if not 1 <= mois <= 12:
                raise serializers.ValidationError(
                    {'mois': 'Un budget mensuel exige un mois entre 1 et 12.'})
        elif mois:
            raise serializers.ValidationError(
                {'mois': 'Un budget annuel ne porte pas de mois (0).'})
        montant = valeur('montant_alloue', 0)
        if montant is not None and montant < 0:
            raise serializers.ValidationError(
                {'montant_alloue': 'Le montant alloué ne peut pas être négatif.'})
        return attrs


class EngagementBudgetSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)

    class Meta:
        model = EngagementBudget
        fields = [
            'id', 'budget', 'demande_achat', 'bon_commande', 'montant',
            'statut', 'statut_display', 'note', 'date_creation',
        ]
        read_only_fields = fields


class BudgetDepartementViewSet(CompanyScopedModelViewSet):
    """NTP2P4 — enveloppes budgétaires d'achat par département.

    Lecture tout rôle (un demandeur doit voir ce qu'il reste avant de
    soumettre — NTP2P23), écriture responsable/admin. Société posée serveur.
    Filtres : ``?departement=``, ``?annee=``, ``?actif=``.
    """
    queryset = BudgetDepartement.objects.select_related('departement').all()
    serializer_class = BudgetDepartementSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'consommation', 'disponible'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for key, col in (('departement', 'departement_id'),
                         ('annee', 'annee'), ('mois', 'mois')):
            val = params.get(key)
            if val:
                qs = qs.filter(**{col: val})
        actif = params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs

    def _check_tenant(self, serializer):
        """Le département doit appartenir à la société de l'appelant."""
        departement = serializer.validated_data.get('departement')
        company = self.request.user.company
        if departement is not None and getattr(
                departement, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError(
                {'departement': 'Département inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        super().perform_update(serializer)

    @action(detail=True, methods=['get'])
    def consommation(self, request, pk=None):
        """NTP2P4 — engagé vs réalisé vs restant pour cette enveloppe."""
        budget = self.get_object()
        detail = selectors.consommation_budget(budget)
        detail['departement_nom'] = (
            budget.departement.nom if budget.departement_id else '')
        detail['engagements'] = EngagementBudgetSerializer(
            budget.engagements.order_by('-date_creation', '-id')[:100],
            many=True).data
        return Response(detail)

    @action(detail=False, methods=['get'])
    def disponible(self, request):
        """NTP2P23 — simulateur : reste-t-il ``montant`` sur ce département ?

        LECTURE SEULE — AUCUN engagement n'est posé : le simulateur tourne
        AVANT la soumission, c'est tout l'intérêt (voir le mur avant de le
        heurter). ``?montant=<mad>`` suffit : sans ``?departement=<id>``, le
        département de l'APPELANT est résolu côté serveur (via
        ``rh.selectors``), pour que l'écran n'ait pas à le deviner."""
        from decimal import Decimal, InvalidOperation

        departement_id = request.query_params.get('departement')
        if not departement_id:
            departement_id = self._departement_de_lappelant(request)
        try:
            montant = Decimal(request.query_params.get('montant') or '0')
        except (InvalidOperation, TypeError):
            montant = Decimal('0')
        verdict = selectors.verifier_budget_disponible(
            request.user.company, departement_id, None, montant)
        budget = verdict.pop('budget', None)
        verdict['budget_id'] = budget.pk if budget is not None else None
        verdict['departement_id'] = departement_id
        verdict['montant_alloue'] = (
            budget.montant_alloue if budget is not None else None)
        verdict['montant_demande'] = montant
        return Response(verdict)

    @staticmethod
    def _departement_de_lappelant(request):
        """Département RH de l'appelant (lecture via ``rh.selectors``)."""
        from apps.rh import selectors as rh_selectors

        company = request.user.company
        dossier = rh_selectors.dossier_employe_for_user(
            company, request.user.pk)
        if dossier is None:
            return None
        mapping = rh_selectors.departements_par_employe(company, [dossier.id])
        return (mapping.get(dossier.id) or {}).get('departement_id')


class EngagementBudgetViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """NTP2P4 — engagements budgétaires, LECTURE SEULE.

    Un engagement n'est jamais créé par l'API : il naît de la soumission d'une
    demande d'achat (``stock.services.engager_budget``)."""
    queryset = EngagementBudget.objects.all()
    serializer_class = EngagementBudgetSerializer
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for key, col in (('budget', 'budget_id'), ('statut', 'statut'),
                         ('demande', 'demande_achat_id')):
            val = params.get(key)
            if val:
                qs = qs.filter(**{col: val})
        return qs.order_by('-date_creation', '-id')
