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

from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, extend_schema,
    extend_schema_view, inline_serializer,
)
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import (
    HasPermissionOrLegacy, IsAnyRole, IsResponsableOrAdmin)
from apps.records.champs_stricts import RegexStricte
from core.champs_stricts import MOTIF_NON_BLANC_SANS_NUL
from core.conflit_etat import ConflitEtat
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE
from core.parseurs import corps_valide
from core.viewsets import CompanyScopedModelViewSet
from apps.parametres.views_common import SettingsAuditedMixin  # ASOC82

from .models import (
    AbonnementMonitoring, CertificatCarbone, CleaningEvent, MonitoringConfig,
    MonitoringSettings, ProductionReading, ProductionWarranty,
    SlaDisponibilite, UnderperformanceFlag,
)
from .providers import available_providers
from .serializers import (
    AbonnementMonitoringSerializer, CleaningEventSerializer,
    CertificatCarboneSerializer, MonitoringConfigSerializer,
    SlaDisponibiliteSerializer,
    MonitoringSettingsSerializer, ProductionReadingSerializer,
    ProductionWarrantySerializer, UnderperformanceFlagSerializer,
)
from .analytics import om_metrics, soiling_assessment
from .query_params import (
    date_iso, decimal_param, entier_borne, identifiant,
)
from .services import (
    evaluate_underperformance, production_warranty_status,
    sync_system, warranty_curve_overlay,
)
from rest_framework import serializers as drf_serializers

READ_ACTIONS = ['list', 'retrieve']

_PDF = {(200, 'application/pdf'): OpenApiTypes.BINARY}
# ENF11 — bornes RÉELLES des paramètres entiers (voir query_params.py) : sans
# `minimum`, le schéma autorisait 0/négatif que le serveur refuse en 400.
_ENTIER_MIN_1 = {'type': 'integer', 'minimum': 1}
_ANNEE = {'type': 'integer', 'minimum': 1900}
_WINDOW = OpenApiParameter(
    'window_days', _ENTIER_MIN_1, required=False, default=365)
# ENF11 (api-fuzz) — ``query_params.date_iso`` lit « vide » comme « borne non
# posée » : le schéma le dit (date ISO ou chaîne vide) au lieu d'annoncer une
# date seule qu'un ``?until=`` contredit.
_DATE_OU_VIDE = {'oneOf': [
    {'type': 'string', 'format': 'date'}, {'type': 'string', 'enum': ['']}]}
_SINCE = OpenApiParameter('since', _DATE_OU_VIDE, required=False)
_UNTIL = OpenApiParameter('until', _DATE_OU_VIDE, required=False)
# ENF11 (api-fuzz) — ``query_params.identifiant`` refuse 0 et les négatifs :
# le schéma le dit (``minimum: 1``) au lieu d'annoncer tout entier.
_IDENTIFIANT = {'type': 'integer', 'minimum': 1}
_CLIENT_REQ = OpenApiParameter('client', _IDENTIFIANT, required=True)
_FILTRE_INSTALLATION = [OpenApiParameter(
    'installation', _IDENTIFIANT, required=False)]

# ── CIQ645 — import CSV des relevés ─────────────────────────────────────────
_COLONNES_RELEVES = {
    'date': ('date',),
    'periode': ('periode_jours', 'periode', 'period_days'),
    'energie': ('energie_kwh', 'energie', 'energy_kwh'),
    'index': ('index_compteur', 'index'),
}


def _lire_csv_releves(texte):
    """``([(numero, (date, periode, energie, index|None))], erreurs)``.

    ``numero`` = numéro de ligne du fichier (en-tête = 1). Une ligne invalide
    part dans ``erreurs`` [{ligne, motif}] et n'est jamais créée.
    """
    import datetime as _dt
    from decimal import Decimal, InvalidOperation

    premiere = texte.splitlines()[0] if texte.splitlines() else ''
    separateur = ';' if ';' in premiere else ','
    # api-fuzz-full 27/10 : ``newline=''`` (le module csv l'exige — un retour
    # chariot isolé levait ``csv.Error``, 500) ; un CSV encore illisible est
    # RAPPORTÉ dans ``erreurs`` comme toute ligne fautive, jamais un 500.
    lecteur = csv.reader(io.StringIO(texte, newline=''), delimiter=separateur)
    try:
        rangs = list(lecteur)
    except csv.Error as exc:
        return [], [{'ligne': lecteur.line_num, 'motif': f'CSV illisible ({exc}).'}]
    if not rangs:
        return [], [{'ligne': 1, 'motif': 'En-tête absent.'}]
    entete = [c.strip().lower() for c in rangs[0]]
    position = {}
    for cle, noms in _COLONNES_RELEVES.items():
        position[cle] = next(
            (entete.index(n) for n in noms if n in entete), None)
    manquantes = [noms[0] for cle, noms in _COLONNES_RELEVES.items()
                  if cle != 'index' and position[cle] is None]
    if manquantes:
        return [], [{'ligne': 1, 'motif': 'Colonne(s) manquante(s) : '
                     + ', '.join(manquantes) + '.'}]

    def cellule(ligne, cle):
        i = position[cle]
        if i is None or i >= len(ligne):
            return ''
        return ligne[i].strip()

    lignes, erreurs = [], []
    for numero, ligne in enumerate(rangs[1:], start=2):
        if not any(c.strip() for c in ligne):
            continue
        brut_date = cellule(ligne, 'date')
        jour = None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
            try:
                jour = _dt.datetime.strptime(brut_date, fmt).date()
                break
            except ValueError:
                continue
        if jour is None:
            erreurs.append({'ligne': numero,
                            'motif': f'Date illisible : « {brut_date} ».'})
            continue
        try:
            periode = int(cellule(ligne, 'periode'))
        except ValueError:
            periode = 0
        if periode < 1:
            erreurs.append({'ligne': numero, 'motif': (
                'Période en jours invalide (entier ≥ 1 attendu).')})
            continue
        try:
            energie = Decimal(cellule(ligne, 'energie').replace(',', '.'))
        except InvalidOperation:
            energie = None
        if energie is None or not energie.is_finite():
            erreurs.append({'ligne': numero,
                            'motif': 'Énergie (kWh) illisible.'})
            continue
        if energie < 0:
            erreurs.append({'ligne': numero,
                            'motif': 'Énergie négative refusée.'})
            continue
        brut_index = cellule(ligne, 'index')
        index = None
        if brut_index:
            try:
                index = Decimal(brut_index.replace(',', '.'))
            except InvalidOperation:
                erreurs.append({'ligne': numero, 'motif': (
                    "Index du compteur illisible.")})
                continue
        lignes.append((numero, (jour, periode, energie.quantize(
            Decimal('0.01')), index)))
    return lignes, erreurs


_VIEWS_MONITORING_CONFIG_VIEW_SET_FLEET_REPONSE = inline_serializer('ViewsMonitoringConfigViewSetFleetReponse', {
    'systems': drf_serializers.JSONField(allow_null=True),
    'systems_active': drf_serializers.JSONField(allow_null=True),
})


_VIEWS_MONITORING_CONFIG_VIEW_SET_CO2_FLEET_REPONSE = inline_serializer('ViewsMonitoringConfigViewSetCo2FleetReponse', {
    'systems': drf_serializers.JSONField(allow_null=True),
    'total_co2_kg': drf_serializers.JSONField(allow_null=True),
})


_VIEWS_MONITORING_CONFIG_VIEW_SET_BENCHMARK_REPONSE = inline_serializer(
    'ViewsMonitoringConfigViewSetBenchmarkReponse', {
        'systems_ranked': drf_serializers.JSONField(allow_null=True),
        'systems': drf_serializers.JSONField(allow_null=True),
    })


_VIEWS_MONITORING_CONFIG_VIEW_SET_SOILING_REPONSE = inline_serializer('ViewsMonitoringConfigViewSetSoilingReponse', {
    'installation': drf_serializers.JSONField(allow_null=True),
    'current_pr_pct': drf_serializers.JSONField(allow_null=True),
    'baseline_pr_pct': drf_serializers.JSONField(allow_null=True),
    'estimated_soiling_loss_pct': drf_serializers.JSONField(allow_null=True),
    'last_cleaning_date': drf_serializers.JSONField(allow_null=True),
    'days_since_cleaning': drf_serializers.JSONField(allow_null=True),
    'recommend_cleaning': drf_serializers.JSONField(allow_null=True),
    'reasons': drf_serializers.JSONField(allow_null=True),
})


_VIEWS_MONITORING_CONFIG_VIEW_SET_OM_REPORT_REPONSE = inline_serializer('ViewsMonitoringConfigViewSetOmReportReponse', {
    'installation': drf_serializers.JSONField(allow_null=True),
    'reference': drf_serializers.JSONField(allow_null=True),
    'period': drf_serializers.JSONField(allow_null=True),
    'period_days': drf_serializers.JSONField(allow_null=True),
    'period_kwh': drf_serializers.JSONField(allow_null=True),
    'pr_pct': drf_serializers.JSONField(allow_null=True),
    'availability_pct': drf_serializers.JSONField(allow_null=True),
    'libelle_indicateur': drf_serializers.CharField(),
    'degradation_pct_per_year': drf_serializers.JSONField(allow_null=True),
    'soiling_suspected': drf_serializers.JSONField(allow_null=True),
    'open_alarms': drf_serializers.JSONField(allow_null=True),
    'recommendations': drf_serializers.JSONField(allow_null=True),
    'date_edition': drf_serializers.JSONField(allow_null=True),
})


_VIEWS_MONITORING_CONFIG_VIEW_SET_CO2_REPONSE = inline_serializer('ViewsMonitoringConfigViewSetCo2Reponse', {
    'installation': drf_serializers.JSONField(allow_null=True),
    'production_kwh': drf_serializers.JSONField(allow_null=True),
    'co2_kg': drf_serializers.JSONField(allow_null=True),
    'co2_tonnes': drf_serializers.JSONField(allow_null=True),
    'co2_kg_par_kwh': drf_serializers.JSONField(allow_null=True),
})


_VIEWS_MONITORING_CONFIG_VIEW_SET_CLIENT_PORTAL_REPONSE = inline_serializer(
    'ViewsMonitoringConfigViewSetClientPortalReponse', {
        'client': drf_serializers.JSONField(allow_null=True),
        'systems_count': drf_serializers.JSONField(allow_null=True),
        'total_production_kwh': drf_serializers.JSONField(allow_null=True),
        'economies_mad': drf_serializers.JSONField(allow_null=True),
        'co2_kg': drf_serializers.JSONField(allow_null=True),
        'co2_tonnes': drf_serializers.JSONField(allow_null=True),
        'tarif_mad_par_kwh': drf_serializers.JSONField(allow_null=True),
        'co2_kg_par_kwh': drf_serializers.JSONField(allow_null=True),
    })


_VIEWS_MONITORING_CONFIG_VIEW_SET_OM_METRICS_REPONSE = inline_serializer(
    'ViewsMonitoringConfigViewSetOmMetricsReponse', {
        'installation': drf_serializers.JSONField(allow_null=True),
        'window_days': drf_serializers.JSONField(allow_null=True),
        'production_kwh': drf_serializers.JSONField(required=False, allow_null=True),
        'expected_kwh': drf_serializers.JSONField(required=False, allow_null=True),
        'pr_pct': drf_serializers.JSONField(required=False, allow_null=True),
        'availability_pct': drf_serializers.JSONField(required=False, allow_null=True),
        'degradation_pct_per_year': drf_serializers.JSONField(required=False, allow_null=True),
        'soiling_suspected': drf_serializers.JSONField(required=False, allow_null=True),
        'monthly_pr': drf_serializers.JSONField(required=False, allow_null=True),
    })


class MonitoringEmailOmReportSerializer(serializers.Serializer):
    """CI #993 api-fuzz-pr (cas JNK86P) — corps STRICT de `email-om-report`
    (même composant OpenAPI `MonitoringEmailOmReport`). Avant : lu sans
    validation, `period: null` atteignait `html.escape(None)` (500) et un
    `recipient` non e-mail partait au serveur de messagerie → 400 nommé."""
    period = serializers.ChoiceField(
        choices=['monthly', 'quarterly'], required=False, default='monthly')
    recipient = serializers.EmailField(required=False)


class MonitoringImportRelevesCsv(serializers.Serializer):
    """Corps JSON de ``import-releves`` (alternative au fichier multipart)."""
    csv = RegexStricte(MOTIF_NON_BLANC_SANS_NUL)


class _RapportPdfRenderer(JSONRenderer):
    """Rend ``?format=pdf`` négociable sur le rapport O&M.

    DRF réserve ``?format=`` (``URL_FORMAT_OVERRIDE``) au choix du renderer :
    sans renderer « pdf » déclaré, la négociation lève un 404 AVANT la vue
    (bug AMON108). La vue renvoie une ``HttpResponse`` déjà construite ; ce
    renderer ne sert qu'aux ERREURS, rendues en JSON (jamais en faux PDF).
    """

    media_type = 'application/pdf'
    format = 'pdf'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        reponse = (renderer_context or {}).get('response')
        if reponse is not None:
            reponse['Content-Type'] = 'application/json'
        return super().render(data, 'application/json', renderer_context)


@extend_schema_view(list=extend_schema(
    parameters=_FILTRE_INSTALLATION))
class MonitoringConfigViewSet(TenantMixin, viewsets.ModelViewSet):
    """Config de supervision par système installé (N50). Lecture tout rôle ;
    écriture responsable/admin. ?installation= pour filtrer."""
    permission_module = 'sav'  # AMON45 — écritures bornées au module sav (ASEC11)
    queryset = MonitoringConfig.objects.select_related('installation').all()
    serializer_class = MonitoringConfigSerializer
    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'providers':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        inst = identifiant(self.request, 'installation')
        if inst:
            qs = qs.filter(installation_id=inst)
        return qs

    def perform_destroy(self, instance):
        # AMON46 — supprimer la config la recréerait vide (get_or_create) :
        # on la désactive, jamais on ne l'efface.
        raise ConflitEtat('La configuration de supervision ne se supprime '
                          'pas : désactivez-la.')

    @extend_schema(responses=inline_serializer('MonitoringProvider', {
        'key': serializers.CharField(),
        'label': serializers.CharField(),
        'disponible': serializers.BooleanField(),
    }, many=True))
    # ENF11 — liste PLATE (registre de fournisseurs), non paginée : sans
    # `pagination_class=None` drf-spectacular publiait un schéma paginé
    # ({count, results}) alors que la réponse est un tableau.
    @action(detail=False, methods=['get'], url_path='providers',
            pagination_class=None, filter_backends=[])
    def providers(self, request):
        """Liste des fournisseurs disponibles (registre swappable)."""
        return Response([
            {'key': k, 'label': lbl, 'disponible': dispo}
            for k, lbl, dispo in available_providers()
        ])

    @extend_schema(request=None, responses=inline_serializer(
        'MonitoringSyncNow', {
            'ok': serializers.BooleanField(),
            'imported': serializers.IntegerField(),
            'provider': serializers.CharField(allow_null=True),
            'underperforming': serializers.BooleanField(),
            'ratio_pct': serializers.FloatField(allow_null=True),
            'ticket': serializers.IntegerField(allow_null=True),
        }))
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

    @extend_schema(
        request={
            'multipart/form-data': inline_serializer(
                'MonitoringImportRelevesFichier', {
                    'fichier': serializers.FileField()}),
            'application/json': MonitoringImportRelevesCsv,
        },
        responses=inline_serializer('MonitoringImportReleves', {
            'crees': serializers.IntegerField(),
            'doublons': serializers.IntegerField(),
            'erreurs': serializers.ListField(
                child=serializers.DictField()),
        }))
    @action(detail=True, methods=['post'], url_path='import-releves',
            permission_classes=[IsResponsableOrAdmin],
            parser_classes=[MultiPartParser, JSONParser])
    def import_releves(self, request, pk=None):
        """CIQ645 (D-CIQ-18) — import CSV des relevés de production d'un site.

        Colonnes : ``date`` (AAAA-MM-JJ ou JJ/MM/AAAA), ``periode_jours``,
        ``energie_kwh``, ``index_compteur`` (facultatif) ; séparateur ``;``
        ou ``,``. Fichier ``fichier`` (multipart) ou texte ``csv``.
        Idempotent par (chantier, date, période) : un relevé déjà présent
        n'est jamais doublé. Les lignes invalides sont rapportées avec leur
        numéro, jamais créées. ``company`` posée côté serveur. Aucun
        connecteur : le suivi n'est jamais « en temps réel ».
        """
        config = self.get_object()  # 404 hors société (TenantMixin)
        fichier = request.FILES.get('fichier')
        if fichier is not None:
            texte = fichier.read().decode('utf-8-sig', errors='replace')
        else:
            # ENF11 : corps validé par le serializer PUBLIÉ (``csv`` chaîne
            # non blanche) — un tableau/nombre ne plante plus, ne passe plus.
            texte = corps_valide(request, MonitoringImportRelevesCsv)['csv']
        # Un fichier vide est un fichier conforme : 0 relevé créé, l'en-tête
        # absent est rapporté dans ``erreurs`` (jamais un 400).
        lignes, erreurs = _lire_csv_releves(texte)
        installation = config.installation
        existants = list(ProductionReading.objects.filter(
            installation=installation).values_list('date', 'period_days'))
        a_creer, doublons = [], 0
        from .selectors import (
            depassement_aujourdhui, message_recouvrement, recouvre,
        )
        for numero, (jour, periode, energie, index) in lignes:
            if (jour, periode) in existants:
                doublons += 1
                continue
            refus = depassement_aujourdhui(jour, periode)  # AMON3
            if refus:
                erreurs.append({'ligne': numero, 'motif': refus})
                continue
            # AMON1 — un relevé qui en recouvre un autre (base ou ligne déjà
            # retenue) n'est jamais créé : il est rapporté.
            autre = next((e for e in existants
                          if recouvre(jour, periode, *e)), None)
            if autre is not None:
                erreurs.append({'ligne': numero,
                                'motif': message_recouvrement(*autre)})
                continue
            existants.append((jour, periode))
            a_creer.append(ProductionReading(
                company=request.user.company, installation=installation,
                date=jour, period_days=periode, energy_kwh=energie,
                source=ProductionReading.Source.IMPORT,
                note=(f'Index du compteur de production : {index}'
                      if index is not None else ''),
                created_by=request.user))
        ProductionReading.objects.bulk_create(a_creer)
        if a_creer:
            # ASAV66 — l'import ré-évalue la sous-performance (comme la
            # saisie manuelle), au lieu de laisser le drapeau périmé.
            evaluate_underperformance(installation, user=request.user)
        return Response({
            'crees': len(a_creer),
            'doublons': doublons,
            'erreurs': erreurs,
        }, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[
            OpenApiParameter('months', _ENTIER_MIN_1, required=False,
                             default=12),
            OpenApiParameter('export', OpenApiTypes.STR, required=False),
        ],
        responses={
            (200, 'application/json'): inline_serializer(
                'MonitoringHistory', {
                    'installation': serializers.IntegerField(),
                    'months': serializers.IntegerField(),
                    'expected_annual_kwh': serializers.FloatField(
                        allow_null=True),
                    'data': serializers.ListField(
                        child=serializers.DictField()),
                }),
            (200, 'text/csv'): OpenApiTypes.STR,
        })
    @action(detail=True, methods=['get'], url_path='history',
            permission_classes=[IsResponsableOrAdmin])
    def history(self, request, pk=None):
        """FG84 — Historique de production mensuelle agrégée avec expected vs actual.

        Renvoie les relevés agrégés par mois + production attendue (basée sur
        expected_annual_kwh). Format : JSON (défaut) ou CSV (?format=csv).
        Fenêtre : ?months=12 (défaut) jusqu'à 60.

        Chaque point : { month, actual_kwh, expected_kwh, ratio_pct }.
        Le ratio_pct < (100 - seuil) indique une sous-performance.
        """
        config = self.get_object()
        months = entier_borne(request, 'months', 12, mini=1, maxi=60)
        today = timezone.localdate()
        since = today - timedelta(days=months * 31)

        # AMON100 — MÊMES PR mensuels que l'analytique O&M
        # (``serie_mensuelle`` : relevés au prorata de leurs jours dans le
        # mois, attendu au profil mensuel sur les seuls jours couverts).
        from .analytics import serie_mensuelle
        from .services import debut_couverture, releves_recouvrant

        expected_annual = config.expected_annual_kwh
        releves = releves_recouvrant(
            config.installation, since, today,
            base=ProductionReading.objects.filter(
                company=request.user.company))
        rows = []
        for mois, actual, expected_month in serie_mensuelle(
                config, releves,
                debut_couverture(config.installation, since), today):
            actual, ratio_pct = float(actual), None
            expected_month = float(expected_month or 0) or None
            if expected_month:
                ratio_pct = round(actual / expected_month * 100, 1)
            rows.append({
                'month': mois.strftime('%Y-%m'),
                'actual_kwh': round(actual, 2),
                'expected_kwh': (
                    round(expected_month, 2) if expected_month else None),
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

    @extend_schema(parameters=[_WINDOW], responses=_VIEWS_MONITORING_CONFIG_VIEW_SET_FLEET_REPONSE)
    @action(detail=False, methods=['get'], url_path='fleet',
            permission_classes=[IsResponsableOrAdmin])
    def fleet(self, request):
        """FG281 — Tableau de bord parc/flotte multi-systèmes : production
        totale, kWc installés, PR moyen et alertes ouvertes sur tous les
        systèmes actifs de la société. ?window_days=365 (défaut)."""
        from .selectors import fleet_overview
        company = request.user.company
        if company is None:
            return Response({'systems': [], 'systems_active': 0})
        window = entier_borne(
            request, 'window_days', 365, mini=1, maxi=1825)
        return Response(fleet_overview(company, window_days=window))

    @extend_schema(parameters=[_WINDOW], responses=_VIEWS_MONITORING_CONFIG_VIEW_SET_BENCHMARK_REPONSE)
    @action(detail=False, methods=['get'], url_path='benchmark',
            permission_classes=[IsResponsableOrAdmin])
    def benchmark(self, request):
        """NTNRG33 — classement RELATIF du parc par PR (percentile), jamais
        un seuil absolu. ?window_days=365 (défaut)."""
        from .selectors import benchmark_parc
        company = request.user.company
        if company is None:
            return Response({'systems_ranked': 0, 'systems': []})
        window = entier_borne(
            request, 'window_days', 365, mini=1, maxi=1825)
        return Response(benchmark_parc(company, window_days=window))

    @extend_schema(parameters=[_WINDOW], responses=_VIEWS_MONITORING_CONFIG_VIEW_SET_OM_METRICS_REPONSE)
    @action(detail=True, methods=['get'], url_path='om-metrics',
            permission_classes=[IsResponsableOrAdmin])
    def om_metrics(self, request, pk=None):
        """FG279 — Analytique O&M par système (PR, disponibilité, soiling,
        dégradation) depuis `ProductionReading`. Fenêtre : ?window_days=365
        (défaut, jusqu'à 1825 jours). 100 % lecture."""
        config = self.get_object()
        window = entier_borne(
            request, 'window_days', 365, mini=1, maxi=1825)
        return Response(om_metrics(config.installation, window_days=window))

    @extend_schema(parameters=[_CLIENT_REQ], responses=_VIEWS_MONITORING_CONFIG_VIEW_SET_CLIENT_PORTAL_REPONSE)
    @action(detail=False, methods=['get'], url_path='client-portal',
            permission_classes=[IsResponsableOrAdmin])
    def client_portal(self, request):
        """FG288 — synthèse environnementale cumulée des systèmes d'un client
        (production / économies / CO₂). ?client=ID requis."""
        from .selectors import client_environmental_dashboard
        company = request.user.company
        client_id = identifiant(request, 'client')
        if company is None or not client_id:
            return Response(
                {'detail': 'client requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(client_environmental_dashboard(company, client_id))

    @extend_schema(parameters=[_SINCE, _UNTIL], responses=_VIEWS_MONITORING_CONFIG_VIEW_SET_CO2_REPONSE)
    @action(detail=True, methods=['get'], url_path='co2',
            permission_classes=[IsResponsableOrAdmin])
    def co2(self, request, pk=None):
        """FG286 — CO₂ évité (kg + tonnes) par ce système (toute la production
        ou bornée par ?since=YYYY-MM-DD&until=YYYY-MM-DD)."""
        from .selectors import co2_for_installation
        config = self.get_object()
        since = date_iso(request, 'since')
        until = date_iso(request, 'until')
        return Response(co2_for_installation(
            config.installation, since=since, until=until))

    @extend_schema(parameters=[_SINCE, _UNTIL], responses=_VIEWS_MONITORING_CONFIG_VIEW_SET_CO2_FLEET_REPONSE)
    @action(detail=False, methods=['get'], url_path='co2-fleet',
            permission_classes=[IsResponsableOrAdmin])
    def co2_fleet(self, request):
        """FG286 — CO₂ évité par système ET cumulé sur le parc de la société."""
        from .selectors import co2_fleet
        company = request.user.company
        if company is None:
            return Response({'systems': [], 'total_co2_kg': 0})
        since = date_iso(request, 'since')
        until = date_iso(request, 'until')
        return Response(co2_fleet(company, since=since, until=until))

    @extend_schema(parameters=[_WINDOW], responses=_VIEWS_MONITORING_CONFIG_VIEW_SET_SOILING_REPONSE)
    @action(detail=True, methods=['get'], url_path='soiling',
            permission_classes=[IsResponsableOrAdmin])
    def soiling(self, request, pk=None):
        """FG283 — perte estimée par salissure (chute de PR entre nettoyages)
        + recommandation de nettoyage. ?window_days=365 (défaut)."""
        config = self.get_object()
        window = entier_borne(
            request, 'window_days', 365, mini=1, maxi=1825)
        return Response(
            soiling_assessment(config.installation, window_days=window))

    @extend_schema(parameters=[_WINDOW], responses=inline_serializer(
        'MonitoringPertesCategorisees', {
            'installation': serializers.IntegerField(),
            'window_days': serializers.IntegerField(),
            'soiling_pct': serializers.FloatField(allow_null=True),
            'ombrage_pct': serializers.FloatField(allow_null=True),
            'panne_pct': serializers.FloatField(allow_null=True),
            'curtailment_pct': serializers.FloatField(allow_null=True),
        }))
    @action(detail=True, methods=['get'], url_path='pertes',
            permission_classes=[IsResponsableOrAdmin])
    def pertes(self, request, pk=None):
        """ASAV103 (D-ASAV-4 option (b)) — pertes de production PAR
        CATÉGORIE (salissure, ombrage, panne, écrêtement — NTNRG32) de ce
        système. Responsable/admin ; 404 hors société. Une catégorie sans
        donnée vaut ``null`` (jamais un faux 0). ?window_days=365 (défaut).
        Contrat : ``contract_samples/pertes_categorisees.json``."""
        from .analytics import pertes_categorisees
        config = self.get_object()
        window = entier_borne(
            request, 'window_days', 365, mini=1, maxi=1825)
        return Response(
            pertes_categorisees(config.installation, window_days=window))

    @extend_schema(
        parameters=[
            OpenApiParameter('period', OpenApiTypes.STR, required=False),
            OpenApiParameter('format', OpenApiTypes.STR, required=False),
        ],
        responses={(200, 'application/json'): _VIEWS_MONITORING_CONFIG_VIEW_SET_OM_REPORT_REPONSE,
                   (200, 'application/pdf'): OpenApiTypes.BINARY})
    @action(detail=True, methods=['get'], url_path='om-report',
            permission_classes=[IsResponsableOrAdmin],
            renderer_classes=[JSONRenderer, _RapportPdfRenderer])
    def om_report(self, request, pk=None):
        """FG289 — rapport O&M périodique du système. ?period=monthly|quarterly.
        ?format=pdf renvoie le PDF ; sinon les données JSON."""
        from .report import build_om_report_data, render_om_report_pdf
        config = self.get_object()
        period = request.query_params.get('period', 'monthly')
        if request.query_params.get('format') == 'pdf':
            pdf = render_om_report_pdf(config.installation, period=period)
            resp = HttpResponse(pdf, content_type='application/pdf')
            ref = config.installation.reference or config.installation_id
            resp['Content-Disposition'] = (
                f'attachment; filename="rapport-om-{ref}.pdf"')
            return resp
        return Response(
            build_om_report_data(config.installation, period=period))

    @extend_schema(
        request=MonitoringEmailOmReportSerializer,
        responses={
            200: inline_serializer('MonitoringEmailOmReportReponse', {
                'sent': serializers.BooleanField()}),
            # ASAV68 — l'e-mail n'est pas parti : 502 servi, désormais publié
            # (api-fuzz #1377, « Undocumented HTTP status code »).
            502: inline_serializer('MonitoringEmailOmReportEchec', {
                'detail': serializers.CharField()}),
        })
    @action(detail=True, methods=['post'], url_path='email-om-report',
            permission_classes=[IsResponsableOrAdmin])
    def email_om_report(self, request, pk=None):
        """FG289 — envoie le rapport O&M périodique par e-mail (PDF joint).
        Destinataire : body `recipient` sinon l'e-mail du client du système."""
        from .report import (
            DestinataireHorsClient, EnvoiRapportImpossible, email_om_report,
        )
        config = self.get_object()
        corps = MonitoringEmailOmReportSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        period = corps.validated_data['period']
        recipient = corps.validated_data.get('recipient')
        try:
            sent = email_om_report(
                config.installation, period=period, recipient=recipient)
        except DestinataireHorsClient as exc:
            # AMON47 — un tiers n'est jamais destinataire. Adresse bien formée
            # mais hors des adresses du client EN BASE : refus d'état, 409
            # (règle ENF40 — le schéma ne peut pas connaître ces adresses).
            raise ConflitEtat({'recipient': [str(exc)]})
        except EnvoiRapportImpossible as exc:
            # ASAV68 — l'e-mail n'est pas parti : jamais {sent: true}.
            return Response(
                {'detail': f'Envoi impossible : {exc}'},
                status=status.HTTP_502_BAD_GATEWAY)
        return Response({'sent': sent})

    @extend_schema(
        parameters=[OpenApiParameter('annee', _ANNEE, required=False)],
        # ENF11 : le 409 d'une LECTURE n'est pas déclaré par le crochet global.
        responses={**_PDF, 409: OpenApiResponse(
            description='Garantie de production non validée (Paramètres).')})
    @action(detail=True, methods=['get'], url_path='rapport-garantie-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def rapport_garantie_pdf(self, request, pk=None):
        """NTNRG11 — rapport CONTRACTUEL mensuel de garantie de performance
        (PDF), distinct du rapport O&M générique ci-dessus : mention légale
        de la clause de garantie + tableau mensuel écart/pénalité cumulée sur
        l'année contractuelle. ?annee=YYYY (défaut année courante). 404
        propre si aucune garantie de production n'est configurée."""
        from .report_warranty import (
            build_warranty_report_data, render_warranty_report_pdf,
        )
        config = self.get_object()
        # CIQ646 (D-CIQ-12) — aucun rapport client de garantie de production
        # tant que la société n'a pas validé l'engagement (assureur/juriste).
        from .selectors import _garantie_production_autorisee
        if not _garantie_production_autorisee(config.installation):
            return Response(
                {'detail': 'Garantie de production non validée (Paramètres).'},
                status=status.HTTP_409_CONFLICT)
        annee = entier_borne(request, 'annee', None, mini=1900, maxi=2200)
        data = build_warranty_report_data(config.installation, year=annee)
        if not data.get('has_warranty'):
            return Response(
                {'detail': 'Aucune garantie de production configurée pour '
                           'ce système.'},
                status=status.HTTP_404_NOT_FOUND)
        pdf = render_warranty_report_pdf(config.installation, year=annee)
        resp = HttpResponse(pdf, content_type='application/pdf')
        ref = config.installation.reference or config.installation_id
        resp['Content-Disposition'] = (
            f'attachment; filename="rapport-garantie-{ref}.pdf"')
        return resp

    @extend_schema(parameters=[_SINCE, _UNTIL], responses=_PDF)
    @action(detail=True, methods=['get'], url_path='attestation-carbone-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def attestation_carbone_pdf(self, request, pk=None):
        """NTNRG26 — attestation carbone PDF certifiable de CE système
        (au-delà du portail JSON FG286/288) : méthodologie affichée, distincte
        du certificat RE générique FG287 (``apps.ventes``). ?since=&until=
        (YYYY-MM-DD, optionnels). Sans relevé sur la période : message propre
        dans le PDF, jamais une erreur."""
        from .report_carbon import render_carbon_report_pdf_site
        config = self.get_object()
        since = date_iso(request, 'since')
        until = date_iso(request, 'until')
        pdf = render_carbon_report_pdf_site(
            config.installation, since=since, until=until)
        resp = HttpResponse(pdf, content_type='application/pdf')
        ref = config.installation.reference or config.installation_id
        resp['Content-Disposition'] = (
            f'attachment; filename="attestation-carbone-{ref}.pdf"')
        return resp

    @extend_schema(parameters=[_CLIENT_REQ, _SINCE, _UNTIL], responses=_PDF)
    @action(detail=False, methods=['get'], url_path='attestation-carbone-client-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def attestation_carbone_client_pdf(self, request):
        """NTNRG26 — attestation carbone CONSOLIDÉE (multi-sites) pour un
        client (FG288). ?client=ID requis. Sans relevé sur la période :
        message propre dans le PDF, jamais une erreur."""
        from .report_carbon import render_carbon_report_pdf_client
        company = request.user.company
        client_id = identifiant(request, 'client')
        if company is None or not client_id:
            return Response(
                {'detail': 'client requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        # ASAV67 — la période demandée est appliquée (plus ignorée).
        pdf = render_carbon_report_pdf_client(
            company, client_id, since=date_iso(request, 'since'),
            until=date_iso(request, 'until'))
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="attestation-carbone-client-{client_id}.pdf"')
        return resp


@extend_schema_view(list=extend_schema(
    parameters=_FILTRE_INSTALLATION))
class CleaningEventViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG283 — nettoyages de panneaux (bornes pour l'estimation de salissure).
    Lecture tout rôle (filtrable par ?installation=) ; écriture
    responsable/admin. `company` et `created_by` posés côté serveur."""
    permission_module = 'sav'  # AMON45 — écritures bornées au module sav (ASEC11)
    queryset = CleaningEvent.objects.select_related('installation').all()
    serializer_class = CleaningEventSerializer
    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        inst = identifiant(self.request, 'installation')
        if inst:
            qs = qs.filter(installation_id=inst)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)


@extend_schema_view(list=extend_schema(
    parameters=_FILTRE_INSTALLATION))
class ProductionReadingViewSet(TenantMixin, viewsets.ModelViewSet):
    """Relevés de production (N51). Lecture tout rôle (filtrable par
    ?installation=) ; saisie manuelle (POST) responsable/admin."""
    permission_module = 'sav'  # AMON45 — écritures bornées au module sav (ASEC11)
    queryset = ProductionReading.objects.select_related('installation').all()
    serializer_class = ProductionReadingSerializer
    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        inst = identifiant(self.request, 'installation')
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

    def perform_destroy(self, instance):
        # AMON46 — un relevé qui fonde un certificat ÉMIS (du site ou de son
        # client consolidé) ne se supprime pas ; sinon, suppression puis
        # ré-évaluation de la sous-performance.
        from datetime import timedelta

        from django.db.models import Q

        installation = instance.installation
        fin = instance.date + timedelta(
            days=max(int(instance.period_days or 1), 1) - 1)
        cible = Q(installation_id=installation.pk)
        if installation.client_id:
            cible |= Q(client_id=installation.client_id)
        certificat = CertificatCarbone.objects.filter(
            cible, company_id=installation.company_id,
            statut=CertificatCarbone.Statut.EMIS,
            periode_debut__lte=fin, periode_fin__gte=instance.date,
        ).order_by('periode_debut').first()
        if certificat is not None:
            raise ConflitEtat(
                f'Ce relevé fonde le certificat {certificat.reference} : '
                'annulez le certificat avant de le supprimer.')
        instance.delete()
        evaluate_underperformance(installation, user=self.request.user)


_VIEWS_PRODUCTION_WARRANTY_VIEW_SET_STATUS_REPONSE = inline_serializer('ViewsProductionWarrantyViewSetStatusReponse', {
    'has_warranty': drf_serializers.JSONField(allow_null=True),
    'year': drf_serializers.JSONField(required=False, allow_null=True),
    'year_in_progress': drf_serializers.JSONField(required=False, allow_null=True),
    'guaranteed_kwh': drf_serializers.JSONField(required=False, allow_null=True),
    'actual_kwh': drf_serializers.JSONField(required=False, allow_null=True),
    'shortfall_kwh': drf_serializers.JSONField(required=False, allow_null=True),
    'within_tolerance': drf_serializers.JSONField(required=False, allow_null=True),
    'compensation_mad': drf_serializers.JSONField(required=False, allow_null=True),
})


_VIEWS_PRODUCTION_WARRANTY_VIEW_SET_CURVE_REPONSE = inline_serializer('ViewsProductionWarrantyViewSetCurveReponse', {
    'has_warranty': drf_serializers.JSONField(allow_null=True),
    'installation': drf_serializers.JSONField(required=False, allow_null=True),
    'threshold_pct': drf_serializers.JSONField(required=False, allow_null=True),
    'manufacturer_recourse': drf_serializers.JSONField(required=False, allow_null=True),
    'points': drf_serializers.JSONField(required=False, allow_null=True),
})


@extend_schema_view(list=extend_schema(
    parameters=_FILTRE_INSTALLATION))
class ProductionWarrantyViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG282 — garantie de production par système. Lecture tout rôle
    (filtrable par ?installation=) ; écriture responsable/admin. Action
    `status` : production réelle vs garanti dégradé → manque/compensation."""
    permission_module = 'sav'  # AMON45 — écritures bornées au module sav (ASEC11)
    queryset = ProductionWarranty.objects.select_related('installation').all()
    serializer_class = ProductionWarrantySerializer
    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action in ('status', 'curve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        inst = identifiant(self.request, 'installation')
        if inst:
            qs = qs.filter(installation_id=inst)
        return qs

    def perform_destroy(self, instance):
        # ASUP7 — une garantie commencée (ou dont l'installation a des
        # relevés) fonde la compensation due : elle ne se supprime pas.
        if (instance.start_year <= timezone.localdate().year
                or ProductionReading.objects.filter(
                    installation_id=instance.installation_id).exists()):
            raise ConflitEtat('Garantie en cours : modifiez-la ou clôturez-la, '
                              'elle fonde la compensation due.')
        super().perform_destroy(instance)

    @extend_schema(
        parameters=[OpenApiParameter('year', _ANNEE, required=False)],
        responses=_VIEWS_PRODUCTION_WARRANTY_VIEW_SET_STATUS_REPONSE)
    @action(detail=True, methods=['get'], url_path='status',
            permission_classes=[IsAnyRole])
    def status(self, request, pk=None):
        """Écart production réelle vs productible garanti dégradé d'une année
        (?year=YYYY, défaut année courante) + compensation due."""
        warranty = self.get_object()
        year = entier_borne(request, 'year', None, mini=1900, maxi=2200)
        result = production_warranty_status(
            warranty.installation, year=year)
        return Response(result)

    @extend_schema(
        parameters=[
            OpenApiParameter('years', _ENTIER_MIN_1, required=False),
            # Forme littérale EXACTE lue par ``decimal_param`` (pas d'exposant :
            # « 4e+59 » est un ``number`` valide mais refusé), 6 chiffres
            # entiers au plus (un seuil est un pourcentage) -> publiée.
            OpenApiParameter('drift_threshold_pct',
                             {'type': 'string',
                              'pattern': r'^-?[0-9]{1,6}(\.[0-9]+)?$'},
                             required=False),
        ],
        responses=_VIEWS_PRODUCTION_WARRANTY_VIEW_SET_CURVE_REPONSE)
    @action(detail=True, methods=['get'], url_path='curve',
            permission_classes=[IsAnyRole])
    def curve(self, request, pk=None):
        """FG284 — superpose production mesurée et courbe garantie de
        dégradation par année → dérive anormale → recours fabricant.
        ?years=N pour borner ; ?drift_threshold_pct=X pour le seuil."""
        warranty = self.get_object()
        years = entier_borne(request, 'years', None, mini=1, maxi=100)
        if request.query_params.get('drift_threshold_pct') == '':
            # Publié par motif (au moins un chiffre) : le vide n'est pas « absent ».
            raise serializers.ValidationError(
                {'drift_threshold_pct': 'Nombre attendu.'})
        threshold = decimal_param(request, 'drift_threshold_pct')
        if threshold is not None and abs(threshold) >= 1000000:
            raise serializers.ValidationError(
                {'drift_threshold_pct': 'Nombre attendu.'})
        result = warranty_curve_overlay(
            warranty.installation, years=years,
            drift_threshold_pct=threshold)
        return Response(result)


class MonitoringSettingsViewSet(SettingsAuditedMixin, TenantMixin,
                                viewsets.ModelViewSet):
    """Réglage société de sous-performance (N52). Singleton par société :
    `list` renvoie l'unique enregistrement ; écriture responsable/admin."""
    permission_module = 'sav'  # AMON45 — écritures bornées au module sav (ASEC11)
    audit_section, audit_libelle = 'monitoring', 'Réglage de supervision'
    queryset = MonitoringSettings.objects.all()
    serializer_class = MonitoringSettingsSerializer
    parser_classes = [JSONParser]
    pagination_class = None

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        # ADRG46 (D-ADRG-5) — réglage de toute la société : + `parametres_modifier`.
        return [IsResponsableOrAdmin(), HasPermissionOrLegacy('parametres_modifier')()]

    @extend_schema(responses=MonitoringSettingsSerializer)
    def list(self, request, *args, **kwargs):
        """Renvoie le réglage unique de la société (créé à défaut)."""
        company = request.user.company
        if company is None:
            return Response({})
        obj = MonitoringSettings.get(company)
        return Response(self.get_serializer(obj).data)

    @extend_schema(request=MonitoringSettingsSerializer,
                   responses={200: MonitoringSettingsSerializer})
    def create(self, request, *args, **kwargs):
        """Upsert du singleton société (PATCH-like via POST), journalisé."""
        obj = MonitoringSettings.get(request.user.company)
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)  # ASOC82 — SettingsAuditLog
        return Response(serializer.data, status=status.HTTP_200_OK)


def _erreur_service(exc):
    """ASAV100/102 — erreur de service → corps DRF : champ nommé sous le champ,
    sinon ``detail`` (texte, lu tel quel par ``getApiError`` côté écran)."""
    if exc.champ:
        return {exc.champ: [exc.message]}
    return {'detail': exc.message}


class AbonnementMonitoringViewSet(CompanyScopedModelViewSet):
    """ASAV100 (D-ASAV-4 option (b), ASAV93) — abonnements de supervision.

    Responsable/admin seulement (lecture comme écriture) ; société forcée côté
    serveur, client résolu depuis le système (jamais lu du corps). Ni
    modification libre ni suppression : un abonnement se crée, puis se résilie
    par l'action ``resilier`` (motif obligatoire) qui coupe la supervision du
    système lié. Contrat : ``contract_samples/abonnements_monitoring.json``."""
    permission_module = 'sav'  # AMON45 — écritures bornées au module sav (ASEC11)
    queryset = AbonnementMonitoring.objects.all()
    serializer_class = AbonnementMonitoringSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['periodicite', 'statut', 'motif_resiliation']
    ordering_fields = ['date_debut', 'date_creation', 'montant', 'statut', 'id']
    ordering = ['-date_debut', 'id']
    parser_classes = [JSONParser]
    permission_classes = [IsResponsableOrAdmin]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        from .services import (
            AbonnementMonitoringError, creer_abonnement_monitoring,
        )
        data = serializer.validated_data
        try:
            serializer.instance = creer_abonnement_monitoring(
                self.request.user.company,
                installation_id=data['installation_id'],
                periodicite=data.get('periodicite') or (
                    AbonnementMonitoring.Periodicite.MENSUEL),
                montant=data.get('montant'),
                date_debut=data.get('date_debut'),
                user=self.request.user)
        except AbonnementMonitoringError as exc:
            if exc.etat:
                raise ConflitEtat(exc.message)
            if exc.introuvable:
                raise NotFound(_erreur_service(exc))
            raise serializers.ValidationError(_erreur_service(exc))

    @extend_schema(
        request=inline_serializer('MonitoringAbonnementResilier', {
            'motif': serializers.CharField()}),
        responses=AbonnementMonitoringSerializer)
    @action(detail=True, methods=['post'], url_path='resilier',
            permission_classes=[IsResponsableOrAdmin])
    def resilier(self, request, pk=None):
        """Résilie l'abonnement (404 hors société) et coupe la supervision
        automatique du système lié (abonné ``abonnement_monitoring_resilie``)."""
        from .services import (
            AbonnementMonitoringError, resilier_abonnement_monitoring,
        )
        abonnement = self.get_object()
        if not hasattr(request.data, 'get'):  # ENF11 : `null` en corps -> 400
            raise serializers.ValidationError(
                {'detail': 'Un objet JSON est attendu en corps.'})
        try:
            resilier_abonnement_monitoring(
                abonnement, motif=request.data.get('motif'),
                user=request.user)
        except AbonnementMonitoringError as exc:
            if exc.etat:
                raise ConflitEtat(exc.message)
            raise serializers.ValidationError(_erreur_service(exc))
        return Response(self.get_serializer(abonnement).data)


@extend_schema_view(list=extend_schema(
    parameters=_FILTRE_INSTALLATION))
class SlaDisponibiliteViewSet(CompanyScopedModelViewSet):
    """ASAV101 (D-ASAV-4 option (b), ASAV93) — SLA de disponibilité par
    système : saisie du taux garanti (aucun défaut) et action ``ecart`` qui
    compare l'indice de suivi mesuré au taux garanti
    (``selectors.disponibilite_vs_garantie``). Responsable/admin seulement ;
    société forcée côté serveur (TenantMixin.perform_create). Contrat :
    ``contract_samples/sla_disponibilite.json``."""
    permission_module = 'sav'  # AMON45 — écritures bornées au module sav (ASEC11)
    queryset = SlaDisponibilite.objects.select_related('installation').all()
    serializer_class = SlaDisponibiliteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['note']
    ordering_fields = [
        'updated_at', 'created_at', 'disponibilite_garantie_pct', 'id']
    ordering = ['-updated_at']
    parser_classes = [JSONParser]

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        inst = identifiant(self.request, 'installation')
        if inst:
            qs = qs.filter(installation_id=inst)
        return qs

    @extend_schema(parameters=[_WINDOW], responses=inline_serializer(
        'MonitoringSlaDisponibiliteEcart', {
            'has_sla': serializers.BooleanField(),
            'installation': serializers.IntegerField(required=False),
            'window_days': serializers.IntegerField(required=False),
            'libelle_indicateur': serializers.CharField(required=False),
            'disponibilite_garantie_pct': serializers.FloatField(
                required=False, allow_null=True),
            'disponibilite_mesuree_pct': serializers.FloatField(
                required=False, allow_null=True),
            'ecart_pct': serializers.FloatField(
                required=False, allow_null=True),
            'sous_garantie': serializers.BooleanField(required=False),
            'jours_indisponibilite_excedentaire': serializers.FloatField(
                required=False, allow_null=True),
            'penalite_mad': serializers.FloatField(
                required=False, allow_null=True),
        }))
    @action(detail=True, methods=['get'], url_path='ecart',
            permission_classes=[IsResponsableOrAdmin])
    def ecart(self, request, pk=None):
        """Indice de suivi mesuré vs taux garanti + pénalité (tarif saisi ;
        ``null`` tant que l'engagement de production n'est pas validé).
        ?window_days=365 (défaut, 1..1825). 404 hors société."""
        from .selectors import disponibilite_vs_garantie
        sla = self.get_object()
        window = entier_borne(
            request, 'window_days', 365, mini=1, maxi=1825)
        return Response(disponibilite_vs_garantie(
            sla.installation, window_days=window))


class _ClasserDrapeauCorps(serializers.Serializer):
    motif = RegexStricte(MOTIF_NON_BLANC_SANS_NUL, max_length=500)


@extend_schema_view(list=extend_schema(parameters=_FILTRE_INSTALLATION + [
    OpenApiParameter('is_open', OpenApiTypes.BOOL, required=False)]))
class UnderperformanceFlagViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """AMON24 — drapeaux de sous-performance : liste (tout rôle, filtrable
    ?installation= / ?is_open=) et classement par le personnel (action
    ``classer``, responsable/admin, motif obligatoire, auteur tracé) — un
    faux drapeau sort du compteur du parc et du portail client ; une rechute
    réelle rouvre un drapeau NEUF. Contrat :
    ``contract_samples/drapeaux_sous_performance.json``."""
    permission_module = 'sav'  # AMON45 — écritures bornées au module sav (ASEC11)
    queryset = (UnderperformanceFlag.objects
                .select_related('installation', 'cloture_par').all())
    serializer_class = UnderperformanceFlagSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'ratio_pct', 'id']
    ordering = ['-date_creation', '-id']
    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        inst = identifiant(self.request, 'installation')
        if inst:
            qs = qs.filter(installation_id=inst)
        ouvert = (self.request.query_params.get('is_open') or '').lower()
        if ouvert in ('true', '1', 'false', '0'):
            qs = qs.filter(is_open=ouvert in ('true', '1'))
        return qs

    @extend_schema(request=_ClasserDrapeauCorps,
                   responses={200: UnderperformanceFlagSerializer})
    @action(detail=True, methods=['post'], url_path='classer',
            permission_classes=[IsResponsableOrAdmin])
    def classer(self, request, pk=None):
        """Ferme le drapeau (motif ``classe_manuellement``, note = motif,
        auteur = l'utilisateur). Motif vide : 400 ; déjà fermé : 409 ;
        autre société : 404."""
        from .services import MOTIF_CLASSE_MANUELLEMENT, _fermer_episode
        drapeau = self.get_object()
        corps = _ClasserDrapeauCorps(data=request.data if hasattr(
            request.data, 'get') else {})
        corps.is_valid(raise_exception=True)
        if not drapeau.is_open:
            raise ConflitEtat('Ce drapeau est déjà fermé.')
        ferme = _fermer_episode(
            drapeau.installation, MOTIF_CLASSE_MANUELLEMENT,
            corps.validated_data['motif'].strip(), user=request.user,
            drapeau_id=drapeau.pk)
        if ferme is None:
            raise ConflitEtat('Ce drapeau est déjà fermé.')
        return Response(self.get_serializer(ferme).data)


#: CI #997 fuzz (2) — un certificat vise UN système OU UN client, jamais les
#: deux ni aucun (400 ``Choisissez soit un système, soit un client``). La
#: période est OBLIGATOIRE dans tous les cas : ``required`` à la RACINE (une
#: branche ``oneOf`` ne suffit pas à Schemathesis), et le ``oneOf`` ne porte que
#: la règle « exactement un des deux ».
_CORPS_CERTIFICAT_CARBONE = {'application/json': {
    'type': 'object',
    'required': ['periode_debut', 'periode_fin'],
    'properties': {
        'installation_id': {'type': 'integer', 'minimum': 1},
        'client_id': {'type': 'integer', 'minimum': 1},
        'periode_debut': {'type': 'string', 'format': 'date'},
        'periode_fin': {'type': 'string', 'format': 'date'},
    },
    'oneOf': [{'required': ['installation_id']}, {'required': ['client_id']}],
}}


@extend_schema_view(create=extend_schema(
    request=_CORPS_CERTIFICAT_CARBONE,
    # Corps OBLIGATOIRE (api-fuzz-full : sans corps, la période manque -> 400
    # « conforme » ; un ``request`` en dict ne pose pas ``required: true``).
    extensions={EXTENSION_CORPS_RESSERRE: {
        'required': ['periode_debut', 'periode_fin']}},
    responses={201: CertificatCarboneSerializer}))
class CertificatCarboneViewSet(CompanyScopedModelViewSet):
    """ASAV102 (D-ASAV-4 option (b), ASAV93) — registre des certificats
    carbone (NTNRG27) : liste + émission. Responsable/admin seulement ;
    société forcée côté serveur. Les tCO₂ sont CALCULÉES par le serveur
    (production mesurée de la période), jamais lues du corps ; un certificat
    émis ne se modifie ni ne se supprime (traçabilité). Contrat :
    ``contract_samples/certificats_carbone.json``."""
    permission_module = 'sav'  # AMON45 — écritures bornées au module sav (ASEC11)
    queryset = CertificatCarbone.objects.all()
    serializer_class = CertificatCarboneSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference']
    ordering_fields = [
        'created_at', 'periode_debut', 'periode_fin', 'tco2_evitees',
        'reference', 'id']
    ordering = ['-created_at']
    parser_classes = [JSONParser]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        from .services import (
            CertificatCarboneError, emettre_certificat_carbone_mesure,
        )
        data = serializer.validated_data
        try:
            serializer.instance = emettre_certificat_carbone_mesure(
                self.request.user.company,
                installation_id=data.get('installation_id'),
                client_id=data.get('client_id'),
                periode_debut=data['periode_debut'],
                periode_fin=data['periode_fin'])
        except CertificatCarboneError as exc:
            if exc.etat:
                # AMON42 — un refus d'état nommé (fin future) garde son champ.
                raise ConflitEtat(_erreur_service(exc))
            if exc.introuvable:
                raise NotFound(_erreur_service(exc))
            raise serializers.ValidationError(_erreur_service(exc))

    @extend_schema(responses=_PDF)
    @action(detail=True, methods=['get'], url_path='pdf',
            permission_classes=[IsResponsableOrAdmin])
    def pdf(self, request, pk=None):
        """AMON94 — PDF du certificat (référence, période, tonnes figées,
        facteur) : la version GED déposée à l'émission, re-déposée si absente."""
        from .report_carbon import pdf_certificat
        certificat = self.get_object()
        resp = HttpResponse(pdf_certificat(certificat),
                            content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="{certificat.reference}.pdf"')
        return resp

    @extend_schema(request=_ClasserDrapeauCorps,
                   responses={200: CertificatCarboneSerializer})
    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[IsResponsableOrAdmin])
    def annuler(self, request, pk=None):
        """AMON93 — annule le certificat (motif obligatoire, auteur et date
        tracés) ; la même cible et période redeviennent émissibles. Motif
        vide : 400 ; déjà annulé : 409 ; autre société : 404."""
        from .services import CertificatCarboneError, annuler_certificat_carbone
        certificat = self.get_object()
        corps = _ClasserDrapeauCorps(data=request.data if hasattr(
            request.data, 'get') else {})
        corps.is_valid(raise_exception=True)
        try:
            annule = annuler_certificat_carbone(
                certificat, motif=corps.validated_data['motif'],
                user=request.user)
        except CertificatCarboneError as exc:
            if exc.etat:
                raise ConflitEtat(_erreur_service(exc))
            raise serializers.ValidationError(_erreur_service(exc))
        return Response(self.get_serializer(annule).data)
