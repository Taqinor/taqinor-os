"""NTP2P4 — Budget d'engagement d'achats.

CRUD des enveloppes (``BudgetDepartement``) + consultation de leur
consommation (``engagé`` vs ``réalisé``). Les ENGAGEMENTS eux-mêmes ne sont
pas écrits par l'API : ils sont posés côté serveur à la soumission d'une
demande d'achat (``stock.services.engager_budget``), donc exposés en LECTURE
SEULE ici.

SOLMVP12 (20/09/2026) — la distinction PAR DÉPARTEMENT a été retirée (elle
référençait le module RH, détaché de stock) : une seule enveloppe par
société et par période.
"""
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.mixins import TenantMixin
from core.viewsets import CompanyScopedModelViewSet

from .. import selectors
from ..models import BudgetDepartement, EngagementBudget


class BudgetDepartementSerializer(serializers.ModelSerializer):
    periodicite_display = serializers.CharField(
        source='get_periodicite_display', read_only=True, default=None)

    class Meta:
        model = BudgetDepartement
        fields = [
            'id', 'periodicite',
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
    """NTP2P4 — enveloppe budgétaire d'achat de la société.

    Lecture tout rôle (un demandeur doit voir ce qu'il reste avant de
    soumettre — NTP2P23), écriture responsable/admin. Société posée serveur.
    Filtres : ``?annee=``, ``?actif=``.
    """
    queryset = BudgetDepartement.objects.all()
    serializer_class = BudgetDepartementSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'consommation', 'disponible'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for key, col in (('annee', 'annee'), ('mois', 'mois')):
            val = params.get(key)
            if val:
                qs = qs.filter(**{col: val})
        actif = params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs

    @action(detail=True, methods=['get'])
    def consommation(self, request, pk=None):
        """NTP2P4 — engagé vs réalisé vs restant pour cette enveloppe."""
        budget = self.get_object()
        detail = selectors.consommation_budget(budget)
        detail['engagements'] = EngagementBudgetSerializer(
            budget.engagements.order_by('-date_creation', '-id')[:100],
            many=True).data
        return Response(detail)

    @action(detail=False, methods=['get'])
    def disponible(self, request):
        """NTP2P23 — simulateur : reste-t-il ``montant`` sur le budget de la
        société ? LECTURE SEULE — AUCUN engagement n'est posé : le
        simulateur tourne AVANT la soumission, c'est tout l'intérêt (voir le
        mur avant de le heurter). ``?montant=<mad>`` suffit."""
        from decimal import Decimal, InvalidOperation

        try:
            montant = Decimal(request.query_params.get('montant') or '0')
        except (InvalidOperation, TypeError):
            montant = Decimal('0')
        verdict = selectors.verifier_budget_disponible(
            request.user.company, None, montant)
        budget = verdict.pop('budget', None)
        verdict['budget_id'] = budget.pk if budget is not None else None
        verdict['montant_alloue'] = (
            budget.montant_alloue if budget is not None else None)
        verdict['montant_demande'] = montant
        return Response(verdict)


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
