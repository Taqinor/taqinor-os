from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.mixins import TenantMixin

from .models import (
    CommentaireVariance, CycleBudgetaire, Departement, HypotheseRecrutement,
    LigneBudgetDepartement, LignePrevisionGlissante, LigneScenario,
    MappingCategorieCompte, PrevisionGlissante, ScenarioBudgetaire,
    SoumissionBudgetDepartement,
)
from .serializers import (
    CommentaireVarianceSerializer, CycleBudgetaireSerializer,
    DepartementSerializer, HypotheseRecrutementSerializer,
    LigneBudgetDepartementSerializer, LignePrevisionGlissanteSerializer,
    LigneScenarioSerializer, MappingCategorieCompteSerializer,
    PrevisionGlissanteSerializer, ScenarioBudgetaireSerializer,
    SoumissionBudgetDepartementSerializer,
)


class DepartementViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA1 — CRUD des départements FP&A, scopé société."""

    queryset = Departement.objects.select_related('responsable', 'parent').all()
    serializer_class = DepartementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom']
    ordering_fields = ['nom', 'code']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai'))
        return qs

    def _to_node(self, dept, by_parent):
        enfants = by_parent.get(dept.pk, [])
        return {
            **DepartementSerializer(dept).data,
            'enfants': [self._to_node(e, by_parent) for e in enfants],
        }

    def list(self, request, *args, **kwargs):
        if request.query_params.get('tree') == '1':
            qs = list(self.filter_queryset(self.get_queryset()))
            by_parent = {}
            for d in qs:
                by_parent.setdefault(d.parent_id, []).append(d)
            racines = by_parent.get(None, [])
            return Response([self._to_node(d, by_parent) for d in racines])
        return super().list(request, *args, **kwargs)


class CycleBudgetaireViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA2 — Cycles budgétaires : machine d'états gardée (brouillon →
    ouvert_saisie → en_validation → clos), transitions illégales refusées
    (400)."""

    queryset = CycleBudgetaire.objects.all()
    serializer_class = CycleBudgetaireSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['date_debut', 'nom']

    @action(detail=True, methods=['post'], url_path='ouvrir-saisie')
    def ouvrir_saisie(self, request, pk=None):
        cycle = self.get_object()
        if cycle.statut != CycleBudgetaire.Statut.BROUILLON:
            return Response(
                {'detail': "Seul un cycle « brouillon » peut être ouvert à la saisie."},
                status=status.HTTP_400_BAD_REQUEST)
        cycle.statut = CycleBudgetaire.Statut.OUVERT_SAISIE
        cycle.save(update_fields=['statut'])
        return Response(CycleBudgetaireSerializer(cycle).data)

    @action(detail=True, methods=['post'], url_path='clore')
    def clore(self, request, pk=None):
        cycle = self.get_object()
        if cycle.statut not in (
                CycleBudgetaire.Statut.OUVERT_SAISIE,
                CycleBudgetaire.Statut.EN_VALIDATION):
            return Response(
                {'detail': "Un cycle brouillon ou déjà clos ne peut pas être clôturé."},
                status=status.HTTP_400_BAD_REQUEST)
        cycle.statut = CycleBudgetaire.Statut.CLOS
        cycle.save(update_fields=['statut'])
        return Response(CycleBudgetaireSerializer(cycle).data)

    @action(detail=True, methods=['post'], url_path='dupliquer')
    def dupliquer(self, request, pk=None):
        cycle_source = self.get_object()
        nouveau_nom = request.data.get('nouveau_nom') or f'{cycle_source.nom} (copie)'
        from .services import dupliquer_cycle_precedent
        nouveau = dupliquer_cycle_precedent(
            request.user.company, cycle_source, nouveau_nom)
        return Response(
            CycleBudgetaireSerializer(nouveau).data,
            status=status.HTTP_201_CREATED)


class LigneBudgetDepartementViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA3 — Lignes de budget départemental (saisie mensuelle par
    catégorie). NTFPA6 — un cycle clos refuse toute écriture (400, via le
    ``ValidationError`` levé par ``LigneBudgetDepartement.save()``)."""

    queryset = LigneBudgetDepartement.objects.select_related(
        'cycle', 'departement').all()
    serializer_class = LigneBudgetDepartementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['mois', 'categorie']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if cycle_id := params.get('cycle'):
            qs = qs.filter(cycle_id=cycle_id)
        if departement_id := params.get('departement'):
            qs = qs.filter(departement_id=departement_id)
        if categorie := params.get('categorie'):
            qs = qs.filter(categorie=categorie)
        return qs

    def _cycle_departement(self, request):
        cycle_id = request.query_params.get('cycle')
        departement_id = request.query_params.get('departement')
        cycle = CycleBudgetaire.objects.filter(
            company=request.user.company, pk=cycle_id).first()
        departement = Departement.objects.filter(
            company=request.user.company, pk=departement_id).first()
        return cycle, departement

    @action(detail=False, methods=['post'], url_path='soumettre')
    def soumettre(self, request):
        cycle, departement = self._cycle_departement(request)
        if cycle is None or departement is None:
            return Response(
                {'detail': 'cycle et departement requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        from django.core.exceptions import ValidationError

        from .services import soumettre_budget_departement
        try:
            soumission = soumettre_budget_departement(
                request.user.company, cycle, departement, request.user)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SoumissionBudgetDepartementSerializer(soumission).data)

    @action(detail=False, methods=['post'], url_path='valider')
    def valider(self, request):
        cycle, departement = self._cycle_departement(request)
        if cycle is None or departement is None:
            return Response(
                {'detail': 'cycle et departement requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        from django.core.exceptions import ValidationError

        from .services import valider_budget_departement
        try:
            soumission = valider_budget_departement(
                request.user.company, cycle, departement, request.user)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SoumissionBudgetDepartementSerializer(soumission).data)

    @action(detail=False, methods=['post'], url_path='rejeter')
    def rejeter(self, request):
        cycle, departement = self._cycle_departement(request)
        if cycle is None or departement is None:
            return Response(
                {'detail': 'cycle et departement requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        from django.core.exceptions import ValidationError

        from .services import rejeter_budget_departement
        try:
            soumission = rejeter_budget_departement(
                request.user.company, cycle, departement, request.user,
                motif=request.data.get('motif', ''))
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SoumissionBudgetDepartementSerializer(soumission).data)


class SoumissionBudgetDepartementViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """NTFPA5 — lecture des soumissions + chatter (historique/note)."""

    queryset = SoumissionBudgetDepartement.objects.select_related(
        'cycle', 'departement').all()
    serializer_class = SoumissionBudgetDepartementSerializer

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        from apps.records.serializers import ActivitySerializer
        from apps.records.services import chatter_qs

        soumission = self.get_object()
        qs = chatter_qs(soumission, company=request.user.company)
        return Response(ActivitySerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='noter')
    def noter(self, request, pk=None):
        from apps.records.services import log_note

        soumission = self.get_object()
        body = request.data.get('body', '')
        activite = log_note(
            soumission, request.user, body, company=request.user.company)
        from apps.records.serializers import ActivitySerializer
        return Response(ActivitySerializer(activite).data)


class PrevisionGlissanteViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA8 — Prévisions glissantes (rolling forecast 12-18 mois) +
    génération depuis la moyenne des 3 derniers mois réels (compta)."""

    queryset = PrevisionGlissante.objects.prefetch_related('lignes').all()
    serializer_class = PrevisionGlissanteSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_reference']

    def get_queryset(self):
        qs = super().get_queryset()
        if departement_id := self.request.query_params.get('departement'):
            qs = qs.filter(departement_id=departement_id)
        return qs

    @action(detail=False, methods=['post'], url_path='generer')
    def generer(self, request):
        departement_id = request.query_params.get('departement') or \
            request.data.get('departement')
        horizon = int(request.query_params.get('horizon')
                      or request.data.get('horizon') or 12)
        date_reference = request.data.get('date_reference')
        if not date_reference:
            from django.utils import timezone
            date_reference = timezone.now().date().replace(day=1)
        prevision, _ = PrevisionGlissante.objects.get_or_create(
            company=request.user.company,
            date_reference=date_reference,
            departement_id=departement_id or None,
            defaults={'horizon_mois': horizon},
        )
        if prevision.horizon_mois != horizon:
            prevision.horizon_mois = horizon
            prevision.save(update_fields=['horizon_mois'])
        from .services import generer_prevision_glissante
        generer_prevision_glissante(prevision)
        prevision.refresh_from_db()
        return Response(PrevisionGlissanteSerializer(prevision).data)


class LignePrevisionGlissanteViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA8 — édition directe des points d'une prévision glissante (une
    modification manuelle pose ``source='manuel'``, jamais réécrasée)."""

    queryset = LignePrevisionGlissante.objects.all()
    serializer_class = LignePrevisionGlissanteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if prevision_id := self.request.query_params.get('prevision'):
            qs = qs.filter(prevision_id=prevision_id)
        return qs


class ScenarioBudgetaireViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA15/16/17/18 — Scénarios what-if : deltas appliqués en lecture,
    comparaison côte-à-côte, promotion en base, analyse de sensibilité."""

    queryset = ScenarioBudgetaire.objects.prefetch_related('lignes').all()
    serializer_class = ScenarioBudgetaireSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'nom']

    def get_queryset(self):
        qs = super().get_queryset()
        if cycle_id := self.request.query_params.get('cycle'):
            qs = qs.filter(cycle_id=cycle_id)
        return qs

    @action(detail=False, methods=['get'], url_path='comparer')
    def comparer(self, request):
        cycle_id = request.query_params.get('cycle')
        scenarios_raw = request.query_params.get('scenarios', '')
        scenario_ids = [s for s in scenarios_raw.split(',') if s.strip()]
        if not cycle_id:
            return Response(
                {'detail': 'cycle requis.'}, status=status.HTTP_400_BAD_REQUEST)
        from .selectors import comparer_scenarios
        result = comparer_scenarios(request.user.company, cycle_id, scenario_ids)
        return Response({
            'base': str(result['base']),
            'scenarios': [
                {'id': r['id'], 'nom': r['nom'],
                 'total': str(r['total']), 'ecart': str(r['ecart'])}
                for r in result['scenarios']
            ],
        })

    @action(detail=True, methods=['post'], url_path='promouvoir')
    def promouvoir(self, request, pk=None):
        scenario = self.get_object()
        from django.core.exceptions import ValidationError

        from .services import promouvoir_scenario_en_base
        try:
            promouvoir_scenario_en_base(scenario, request.user)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        scenario.refresh_from_db()
        return Response(ScenarioBudgetaireSerializer(scenario).data)

    @action(detail=False, methods=['get'], url_path='sensibilite')
    def sensibilite(self, request):
        cycle_id = request.query_params.get('cycle')
        variable = request.query_params.get('variable', 'taux_conversion')
        try:
            plage = int(request.query_params.get('plage', 20))
        except (TypeError, ValueError):
            plage = 20
        if not cycle_id:
            return Response(
                {'detail': 'cycle requis.'}, status=status.HTTP_400_BAD_REQUEST)
        from .services import analyse_sensibilite
        points = analyse_sensibilite(
            request.user.company, cycle_id, variable, plage)
        return Response({'variable': variable, 'points': points})


class LigneScenarioViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA15 — deltas d'un scénario (jamais écrits dans le cycle réel)."""

    queryset = LigneScenario.objects.all()
    serializer_class = LigneScenarioSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if scenario_id := self.request.query_params.get('scenario'):
            qs = qs.filter(scenario_id=scenario_id)
        return qs


class HypotheseRecrutementViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA10 — Hypothèses de recrutement/départ (alimente le driver masse
    salariale NTFPA9)."""

    queryset = HypotheseRecrutement.objects.select_related(
        'departement', 'prevision_glissante').all()
    serializer_class = HypotheseRecrutementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_effet']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if departement_id := params.get('departement'):
            qs = qs.filter(departement_id=departement_id)
        if statut := params.get('statut'):
            qs = qs.filter(statut=statut)
        return qs


class VarianceViewSet(viewsets.ViewSet):
    """NTFPA19 — analyse des écarts (variance) prévu/réel/forecast, en lecture."""

    def list(self, request):
        cycle_id = request.query_params.get('cycle')
        mois = request.query_params.get('mois')
        if not cycle_id or not mois:
            return Response(
                {'detail': 'cycle et mois requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        from .selectors import variance_budget_vs_reel
        rows = variance_budget_vs_reel(
            request.user.company, cycle_id, int(mois))
        # Decimals → str pour la sérialisation JSON.
        payload = []
        for r in rows:
            payload.append({
                k: (str(v) if v is not None and hasattr(v, 'is_signed') else v)
                for k, v in r.items()
            })
        return Response(payload)


class MappingCategorieCompteViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA21 — mapping catégorie FP&A ↔ préfixe de compte CGNC (utilisé par
    la variance NTFPA19 pour traduire les catégories vers les classes
    comptables réelles sans coder en dur le plan CGNC)."""

    queryset = MappingCategorieCompte.objects.all()
    serializer_class = MappingCategorieCompteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if categorie := self.request.query_params.get('categorie'):
            qs = qs.filter(categorie=categorie)
        return qs


class CommentaireVarianceViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA20 — commentaires de variance (un par cellule, historique complet)."""

    queryset = CommentaireVariance.objects.select_related('auteur').all()
    serializer_class = CommentaireVarianceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for champ in ('cycle', 'departement', 'categorie', 'mois'):
            if val := params.get(champ):
                qs = qs.filter(**{champ: val})
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)


class DriversViewSet(viewsets.ViewSet):
    """NTFPA9/11/12 — drivers de planning (endpoints de calcul, aucun modèle
    propre). Company scopée via ``request.user.company``."""

    @action(detail=False, methods=['post'], url_path='masse-salariale/projeter')
    def masse_salariale_projeter(self, request):
        from datetime import date

        from .services import projeter_masse_salariale

        def _parse_date(v):
            if not v:
                return None
            if isinstance(v, date):
                return v
            return date.fromisoformat(str(v))

        mois_debut = _parse_date(request.data.get('mois_debut'))
        mois_fin = _parse_date(request.data.get('mois_fin'))
        if mois_debut is None or mois_fin is None:
            return Response(
                {'detail': 'mois_debut et mois_fin (YYYY-MM-DD) requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        departement_id = request.data.get('departement')
        hypotheses = request.data.get('hypothese_recrutements') or []
        # Normalise les dates des hypothèses passées en JSON.
        for hyp in hypotheses:
            if isinstance(hyp.get('date_effet'), str):
                hyp['date_effet'] = _parse_date(hyp['date_effet'])
        rows = projeter_masse_salariale(
            request.user.company, departement_id, mois_debut, mois_fin,
            hypothese_recrutements=hypotheses)
        return Response({'projection': [
            {'annee': r['annee'], 'mois': r['mois'],
             'masse_salariale_chargee': str(r['masse_salariale_chargee'])}
            for r in rows
        ]})

    @action(detail=False, methods=['get'], url_path='revenu-pipeline')
    def revenu_pipeline(self, request):
        from datetime import date

        from .services import projeter_revenu_pipeline

        def _parse_date(v):
            return date.fromisoformat(str(v)) if v else None

        mois_debut = _parse_date(request.query_params.get('mois_debut'))
        mois_fin = _parse_date(request.query_params.get('mois_fin'))
        if mois_debut is None or mois_fin is None:
            return Response(
                {'detail': 'mois_debut et mois_fin (YYYY-MM-DD) requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        par_mois = projeter_revenu_pipeline(
            request.user.company, mois_debut, mois_fin)
        return Response({'revenu_pipeline': {
            k: str(v) for k, v in sorted(par_mois.items())
        }})

    @action(detail=False, methods=['get'], url_path='revenu-engage')
    def revenu_engage(self, request):
        from datetime import date

        from .selectors import revenu_engage_carnet

        def _parse_date(v):
            return date.fromisoformat(str(v)) if v else None

        mois_debut = _parse_date(request.query_params.get('mois_debut'))
        mois_fin = _parse_date(request.query_params.get('mois_fin'))
        if mois_debut is None or mois_fin is None:
            return Response(
                {'detail': 'mois_debut et mois_fin (YYYY-MM-DD) requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        par_mois = revenu_engage_carnet(
            request.user.company, mois_debut, mois_fin)
        return Response({'revenu_engage': {
            k: str(v) for k, v in sorted(par_mois.items())
        }})
