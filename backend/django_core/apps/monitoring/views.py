"""
API monitoring (N50/N51/N52).

  * MonitoringConfigViewSet — config de supervision par système (provider /
    enabled / identifiants). Écriture responsable/admin. Action `sync-now`
    appelle le fournisseur et stocke les relevés (no-op sûr si non configuré),
    puis évalue la sous-performance (N52).

  * ProductionReadingViewSet — relevés de production. Lecture filtrable par
    `?installation=`. La création POST est la SAISIE MANUELLE (fallback) :
    source forcée à 'manual' côté serveur.

  * MonitoringSettingsViewSet — réglage société (seuil + auto-ticket), édité
    dans Paramètres. Toujours un seul enregistrement par société (singleton).

Toutes les vues filtrent par société (TenantMixin) et posent `company` côté
serveur ; jamais lue du corps.
"""
import csv
import io
from datetime import timedelta

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from .models import (
    CleaningEvent, MonitoringConfig, MonitoringSettings, ProductionReading,
    ProductionWarranty,
)
from .providers import available_providers
from .serializers import (
    CleaningEventSerializer, MonitoringConfigSerializer,
    MonitoringSettingsSerializer, ProductionReadingSerializer,
    ProductionWarrantySerializer,
)
from .analytics import om_metrics, soiling_assessment
from .services import (
    evaluate_underperformance, production_warranty_status, sync_system,
)

READ_ACTIONS = ['list', 'retrieve']


class MonitoringConfigViewSet(TenantMixin, viewsets.ModelViewSet):
    """Config de supervision par système installé (N50). Lecture tout rôle ;
    écriture responsable/admin. ?installation= pour filtrer."""
    queryset = MonitoringConfig.objects.select_related('installation').all()
    serializer_class = MonitoringConfigSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'providers':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        inst = self.request.query_params.get('installation')
        if inst:
            qs = qs.filter(installation_id=inst)
        return qs

    @action(detail=False, methods=['get'], url_path='providers')
    def providers(self, request):
        """Liste des fournisseurs disponibles (registre swappable)."""
        return Response([
            {'key': k, 'label': lbl} for k, lbl in available_providers()
        ])

    @action(detail=True, methods=['post'], url_path='sync-now',
            permission_classes=[IsResponsableOrAdmin])
    def sync_now(self, request, pk=None):
        """N50 — déclenche la synchro du fournisseur configuré pour ce système.

        No-op sûr (0 relevé) quand aucun fournisseur n'est configuré/actif.
        Enchaîne l'évaluation de sous-performance (N52)."""
        config = self.get_object()
        imported, provider = sync_system(
            config.installation, user=request.user)
        evald = evaluate_underperformance(
            config.installation, user=request.user)
        return Response({
            'ok': True,
            'imported': imported,
            'provider': provider,
            'underperforming': evald['underperforming'],
            'ratio_pct': evald['ratio_pct'],
            'ticket': evald['ticket'].id if evald.get('ticket') else None,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='history',
            permission_classes=[IsAnyRole])
    def history(self, request, pk=None):
        """FG84 — Historique de production mensuelle agrégée avec expected vs actual.

        Renvoie les relevés agrégés par mois + production attendue (basée sur
        expected_annual_kwh). Format : JSON (défaut) ou CSV (?format=csv).
        Fenêtre : ?months=12 (défaut) jusqu'à 60.

        Chaque point : { month, actual_kwh, expected_kwh, ratio_pct }.
        Le ratio_pct < (100 - seuil) indique une sous-performance.
        """
        config = self.get_object()
        months = min(int(request.query_params.get('months', 12)), 60)
        since = timezone.localdate() - timedelta(days=months * 31)

        # Agrégation mensuelle.
        qs = (ProductionReading.objects
              .filter(
                  company=request.user.company,
                  installation=config.installation,
                  date__gte=since)
              .annotate(month=TruncMonth('date'))
              .values('month')
              .annotate(actual_kwh=Sum('energy_kwh'))
              .order_by('month'))

        # Production attendue mensuelle (kWh/mois ≈ annual / 12).
        expected_annual = config.expected_annual_kwh
        expected_monthly = (
            float(expected_annual) / 12 if expected_annual else None)

        rows = []
        for row in qs:
            actual = float(row['actual_kwh'])
            ratio_pct = None
            if expected_monthly and expected_monthly > 0:
                ratio_pct = round(actual / expected_monthly * 100, 1)
            rows.append({
                'month': row['month'].strftime('%Y-%m'),
                'actual_kwh': round(actual, 2),
                'expected_kwh': (
                    round(expected_monthly, 2) if expected_monthly else None),
                'ratio_pct': ratio_pct,
            })

        # CSV export — utilise `export=csv` (pas `format=` pour éviter le conflit
        # avec le mécanisme de suffixe de rendu de DRF).
        if request.query_params.get('export') == 'csv':
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf, fieldnames=['month', 'actual_kwh', 'expected_kwh', 'ratio_pct'])
            writer.writeheader()
            writer.writerows(rows)
            resp = StreamingHttpResponse(
                iter([buf.getvalue()]),
                content_type='text/csv; charset=utf-8')
            fname = f'production-{config.installation_id}-{months}m.csv'
            resp['Content-Disposition'] = f'attachment; filename="{fname}"'
            return resp

        return Response({
            'installation': config.installation_id,
            'months': months,
            'expected_annual_kwh': (
                float(expected_annual) if expected_annual else None),
            'data': rows,
        })

    @action(detail=False, methods=['get'], url_path='fleet',
            permission_classes=[IsAnyRole])
    def fleet(self, request):
        """FG281 — Tableau de bord parc/flotte multi-systèmes : production
        totale, kWc installés, PR moyen et alertes ouvertes sur tous les
        systèmes actifs de la société. ?window_days=365 (défaut)."""
        from .selectors import fleet_overview
        company = request.user.company
        if company is None:
            return Response({'systems': [], 'systems_active': 0})
        window = min(int(request.query_params.get('window_days', 365)), 1825)
        return Response(fleet_overview(company, window_days=window))

    @action(detail=True, methods=['get'], url_path='om-metrics',
            permission_classes=[IsAnyRole])
    def om_metrics(self, request, pk=None):
        """FG279 — Analytique O&M par système (PR, disponibilité, soiling,
        dégradation) depuis `ProductionReading`. Fenêtre : ?window_days=365
        (défaut, jusqu'à 1825 jours). 100 % lecture."""
        config = self.get_object()
        window = min(int(request.query_params.get('window_days', 365)), 1825)
        return Response(om_metrics(config.installation, window_days=window))

    @action(detail=True, methods=['get'], url_path='soiling',
            permission_classes=[IsAnyRole])
    def soiling(self, request, pk=None):
        """FG283 — perte estimée par salissure (chute de PR entre nettoyages)
        + recommandation de nettoyage. ?window_days=365 (défaut)."""
        config = self.get_object()
        window = min(int(request.query_params.get('window_days', 365)), 1825)
        return Response(
            soiling_assessment(config.installation, window_days=window))


class CleaningEventViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG283 — nettoyages de panneaux (bornes pour l'estimation de salissure).
    Lecture tout rôle (filtrable par ?installation=) ; écriture
    responsable/admin. `company` et `created_by` posés côté serveur."""
    queryset = CleaningEvent.objects.select_related('installation').all()
    serializer_class = CleaningEventSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        inst = self.request.query_params.get('installation')
        if inst:
            qs = qs.filter(installation_id=inst)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)


class ProductionReadingViewSet(TenantMixin, viewsets.ModelViewSet):
    """Relevés de production (N51). Lecture tout rôle (filtrable par
    ?installation=) ; saisie manuelle (POST) responsable/admin."""
    queryset = ProductionReading.objects.select_related('installation').all()
    serializer_class = ProductionReadingSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        inst = self.request.query_params.get('installation')
        if inst:
            qs = qs.filter(installation_id=inst)
        return qs

    def perform_create(self, serializer):
        # Saisie MANUELLE : source forcée côté serveur, company depuis l'user.
        serializer.save(
            company=self.request.user.company,
            source=ProductionReading.Source.MANUAL,
            external_id='',
            created_by=self.request.user)
        # Après une saisie manuelle, ré-évaluer la sous-performance (N52).
        installation = serializer.instance.installation
        evaluate_underperformance(installation, user=self.request.user)


class ProductionWarrantyViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG282 — garantie de production par système. Lecture tout rôle
    (filtrable par ?installation=) ; écriture responsable/admin. Action
    `status` : production réelle vs garanti dégradé → manque/compensation."""
    queryset = ProductionWarranty.objects.select_related('installation').all()
    serializer_class = ProductionWarrantySerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'status':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        inst = self.request.query_params.get('installation')
        if inst:
            qs = qs.filter(installation_id=inst)
        return qs

    @action(detail=True, methods=['get'], url_path='status',
            permission_classes=[IsAnyRole])
    def status(self, request, pk=None):
        """Écart production réelle vs productible garanti dégradé d'une année
        (?year=YYYY, défaut année courante) + compensation due."""
        warranty = self.get_object()
        year = request.query_params.get('year')
        result = production_warranty_status(
            warranty.installation, year=int(year) if year else None)
        return Response(result)


class MonitoringSettingsViewSet(TenantMixin, viewsets.ModelViewSet):
    """Réglage société de sous-performance (N52). Singleton par société :
    `list` renvoie l'unique enregistrement ; écriture responsable/admin."""
    queryset = MonitoringSettings.objects.all()
    serializer_class = MonitoringSettingsSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def list(self, request, *args, **kwargs):
        """Renvoie le réglage unique de la société (créé à défaut)."""
        company = request.user.company
        if company is None:
            return Response({})
        obj = MonitoringSettings.get(company)
        return Response(self.get_serializer(obj).data)

    def create(self, request, *args, **kwargs):
        """Upsert du singleton société (PATCH-like via POST)."""
        company = request.user.company
        obj = MonitoringSettings.get(company)
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(company=company)
        return Response(serializer.data, status=status.HTTP_200_OK)
