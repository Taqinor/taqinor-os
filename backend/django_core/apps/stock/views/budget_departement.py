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
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.parsers import JSONParser
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.mixins import TenantMixin
from core.champs_stricts import ChampsStrictsMixin
from core.serializers import CompanyScopedRelationsMixin
from ..openapi_helpers import BOOL, INT, NUM, OBJET, P, STR, corps
from ..utils.params import booleen_requete_ou_400, entier_ou_400, valeur_unique_ou_400
from core.viewsets import CompanyScopedModelViewSet

from .. import selectors
from ..permissions import MasqueMontantsAchatMixin, PeutVoirPrixAchat
from ..models import BudgetDepartement, EngagementBudget


class BudgetDepartementSerializer(ChampsStrictsMixin, MasqueMontantsAchatMixin,
                                  serializers.ModelSerializer):
    champs_montants_achat = ('montant_alloue',)  # ERR-STK-PRIX-ACHAT-SUITE
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
        # ERR fuzz : passer en ANNUEL sans envoyer ``mois`` remet le mois à 0
        # (un budget annuel n'en porte pas) au lieu de buter sur l'ancien mois.
        if periodicite == BudgetDepartement.Periodicite.ANNUELLE and 'periodicite' in attrs and 'mois' not in attrs:
            attrs['mois'] = mois = 0
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


class EngagementBudgetSerializer(CompanyScopedRelationsMixin,
                                 MasqueMontantsAchatMixin,
                                 serializers.ModelSerializer):
    # ENF17 — FK en lecture seule (read_only_fields = fields) ; bornées
    # société (mixin) si l'une redevient inscriptible.
    champs_montants_achat = ('montant',)  # ERR-STK-PRIX-ACHAT-SUITE
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)

    class Meta:
        model = EngagementBudget
        fields = [
            'id', 'budget', 'demande_achat', 'bon_commande', 'montant',
            'statut', 'statut_display', 'note', 'date_creation',
        ]
        read_only_fields = fields


@extend_schema_view(list=extend_schema(parameters=[P('annee', INT, mini=0,
                    maxi=2147483647, vide=True), P('mois', INT, mini=0, maxi=12, vide=True), P('actif', BOOL)]))
class BudgetDepartementViewSet(CompanyScopedModelViewSet):
    """NTP2P4 — enveloppe budgétaire d'achat de la société.

    Lecture tout rôle (un demandeur doit voir ce qu'il reste avant de
    soumettre — NTP2P23), écriture responsable/admin. Société posée serveur.
    Filtres : ``?annee=``, ``?actif=``.
    """
    queryset = BudgetDepartement.objects.all()
    serializer_class = BudgetDepartementSerializer

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action == 'consommation':
            # ERR-STK-PRIX-ACHAT-SUITE — engagé/réalisé/restant : montants seuls.
            return [IsAnyRole(), PeutVoirPrixAchat()]
        if self.action in ('list', 'retrieve', 'disponible'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        # CI #997 fuzz — filtres stricts et bornés (``?actif=null`` ignoré en
        # silence, ``?annee=abc`` / hors plage PostgreSQL finissaient en 500).
        for key, maxi in (('annee', 2147483647), ('mois', 12)):
            val = entier_ou_400(valeur_unique_ou_400(self.request, key), key, mini=0, maxi=maxi)
            if val is not None:
                qs = qs.filter(**{key: val})
        actif = booleen_requete_ou_400(self.request, 'actif')
        if actif is not None:
            qs = qs.filter(actif=actif)
        return qs

    @extend_schema(responses=OBJET)
    @action(detail=True, methods=['get'])
    def consommation(self, request, pk=None):
        """NTP2P4 — engagé vs réalisé vs restant pour cette enveloppe."""
        budget = self.get_object()
        detail = selectors.consommation_budget(budget)
        detail['engagements'] = EngagementBudgetSerializer(
            budget.engagements.order_by('-date_creation', '-id')[:100],
            many=True).data
        return Response(detail)

    @extend_schema(parameters=[P('montant', NUM, False, 'Montant demandé (MAD)', vide=True)],
                   responses=corps('BudgetDisponibleReponse', controle_actif=serializers.BooleanField(),
                                   restant=serializers.FloatField(allow_null=True),
                                   depassement=serializers.FloatField(), suffisant=serializers.BooleanField(),
                                   montant_manquant=serializers.FloatField(),
                                   budget_id=serializers.IntegerField(allow_null=True),
                                   montant_alloue=serializers.CharField(allow_null=True),
                                   montant_demande=serializers.FloatField()))
    @action(detail=False, methods=['get'])
    def disponible(self, request):
        """NTP2P23 — simulateur : reste-t-il ``montant`` sur le budget de la
        société ? LECTURE SEULE — AUCUN engagement n'est posé : le
        simulateur tourne AVANT la soumission, c'est tout l'intérêt (voir le
        mur avant de le heurter). ``?montant=<mad>`` suffit."""
        from decimal import Decimal

        from ..utils.params import decimal_ou_400
        montant = decimal_ou_400(
            valeur_unique_ou_400(request, 'montant'), 'montant', Decimal('0'))
        verdict = selectors.verifier_budget_disponible(
            request.user.company, None, montant)
        budget = verdict.pop('budget', None)
        verdict['budget_id'] = budget.pk if budget is not None else None
        verdict['montant_alloue'] = (
            budget.montant_alloue if budget is not None else None)
        verdict['montant_demande'] = montant
        # ERR-STK-PRIX-ACHAT-3-ROUTES (D-ASTK-2) — sans `prix_achat_voir`, le
        # demandeur garde le VERDICT (contrôle actif, suffisant) sans montant.
        if not PeutVoirPrixAchat().has_permission(request, self):
            verdict = {cle: verdict[cle] for cle in (
                'controle_actif', 'suffisant', 'budget_id')}
        return Response(verdict)


@extend_schema_view(list=extend_schema(parameters=[P('budget', INT), P('statut', STR), P('demande', INT)]))
# headless: engagements budgetaires consommes par API/reporting, aucun ecran frontend
class EngagementBudgetViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """NTP2P4 — engagements budgétaires, LECTURE SEULE.

    Un engagement n'est jamais créé par l'API : il naît de la soumission d'une
    demande d'achat (``stock.services.engager_budget``)."""
    queryset = EngagementBudget.objects.all()
    serializer_class = EngagementBudgetSerializer
    permission_classes = [IsAnyRole]

    parser_classes = [JSONParser]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for key, col in (('budget', 'budget_id'), ('statut', 'statut'),
                         ('demande', 'demande_achat_id')):
            val = params.get(key)
            if val:
                qs = qs.filter(**{col: val})
        return qs.order_by('-date_creation', '-id')
