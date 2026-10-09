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
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, extend_schema_view, inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
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
from .query_params import (
    date_iso, decimal_param, entier_borne, identifiant,
)
from .services import (
    evaluate_underperformance, production_warranty_status,
    sync_system, warranty_curve_overlay,
)

READ_ACTIONS = ['list', 'retrieve']

_PDF = {(200, 'application/pdf'): OpenApiTypes.BINARY}
_WINDOW = OpenApiParameter(
    'window_days', OpenApiTypes.INT, required=False, default=365)
_SINCE = OpenApiParameter('since', OpenApiTypes.DATE, required=False)
_UNTIL = OpenApiParameter('until', OpenApiTypes.DATE, required=False)
_CLIENT_REQ = OpenApiParameter('client', OpenApiTypes.INT, required=True)
_FILTRE_INSTALLATION = [OpenApiParameter(
    'installation', OpenApiTypes.INT, required=False)]

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
    lecteur = csv.reader(io.StringIO(texte), delimiter=separateur)
    try:
        entete = [c.strip().lower() for c in next(lecteur)]
    except StopIteration:
        return [], [{'ligne': 1, 'motif': 'En-tête absent.'}]
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
    for numero, ligne in enumerate(lecteur, start=2):
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


@extend_schema_view(list=extend_schema(
    parameters=_FILTRE_INSTALLATION))
class MonitoringConfigViewSet(TenantMixin, viewsets.ModelViewSet):
    """Config de supervision par système installé (N50). Lecture tout rôle ;
    écriture responsable/admin. ?installation= pour filtrer."""
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

    @extend_schema(responses=inline_serializer('MonitoringProvider', {
        'key': serializers.CharField(),
        'label': serializers.CharField(),
    }, many=True))
    @action(detail=False, methods=['get'], url_path='providers')
    def providers(self, request):
        """Liste des fournisseurs disponibles (registre swappable)."""
        return Response([
            {'key': k, 'label': lbl} for k, lbl in available_providers()
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
            'application/json': inline_serializer(
                'MonitoringImportRelevesCsv', {
                    'csv': serializers.CharField()}),
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
            texte = str(request.data.get('csv') or '')
        if not texte.strip():
            return Response(
                {'detail': 'Fichier CSV vide ou absent (champ « fichier » ou '
                           '« csv »).'},
                status=status.HTTP_400_BAD_REQUEST)
        lignes, erreurs = _lire_csv_releves(texte)
        installation = config.installation
        existants = set(ProductionReading.objects.filter(
            installation=installation).values_list('date', 'period_days'))
        a_creer, doublons = [], 0
        for numero, (jour, periode, energie, index) in lignes:
            if (jour, periode) in existants:
                doublons += 1
                continue
            existants.add((jour, periode))
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
            OpenApiParameter('months', OpenApiTypes.INT, required=False,
                             default=12),
            OpenApiParameter('export', OpenApiTypes.STR, required=False,
                             enum=['csv']),
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
        months = entier_borne(request, 'months', 12, mini=1, maxi=60)
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

        # ASAV63 — production attendue de chaque mois sur ses jours
        # réellement couverts (annuel × jours / 365) : le premier et le
        # dernier mois partiels sont normalisés (même règle que les PR
        # mensuels de l'analytique O&M).
        from .analytics import jours_couverts_mois
        from .services import debut_couverture

        today = timezone.localdate()
        expected_annual = config.expected_annual_kwh
        debut_eff = debut_couverture(config.installation, since)

        rows = []
        for row in qs:
            actual = float(row['actual_kwh'])
            ratio_pct = None
            expected_month = None
            couverts = jours_couverts_mois(row['month'], debut_eff, today)
            if expected_annual and couverts > 0:
                expected_month = float(expected_annual) * couverts / 365
            if expected_month and expected_month > 0:
                ratio_pct = round(actual / expected_month * 100, 1)
            rows.append({
                'month': row['month'].strftime('%Y-%m'),
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

    @extend_schema(parameters=[_WINDOW], responses=OpenApiTypes.OBJECT)
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
        window = entier_borne(
            request, 'window_days', 365, mini=1, maxi=1825)
        return Response(fleet_overview(company, window_days=window))

    @extend_schema(parameters=[_WINDOW], responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=['get'], url_path='benchmark',
            permission_classes=[IsAnyRole])
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

    @extend_schema(parameters=[_WINDOW], responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=['get'], url_path='om-metrics',
            permission_classes=[IsAnyRole])
    def om_metrics(self, request, pk=None):
        """FG279 — Analytique O&M par système (PR, disponibilité, soiling,
        dégradation) depuis `ProductionReading`. Fenêtre : ?window_days=365
        (défaut, jusqu'à 1825 jours). 100 % lecture."""
        config = self.get_object()
        window = entier_borne(
            request, 'window_days', 365, mini=1, maxi=1825)
        return Response(om_metrics(config.installation, window_days=window))

    @extend_schema(parameters=[_CLIENT_REQ], responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=['get'], url_path='client-portal',
            permission_classes=[IsAnyRole])
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

    @extend_schema(parameters=[_SINCE, _UNTIL], responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=['get'], url_path='co2',
            permission_classes=[IsAnyRole])
    def co2(self, request, pk=None):
        """FG286 — CO₂ évité (kg + tonnes) par ce système (toute la production
        ou bornée par ?since=YYYY-MM-DD&until=YYYY-MM-DD)."""
        from .selectors import co2_for_installation
        config = self.get_object()
        since = date_iso(request, 'since')
        until = date_iso(request, 'until')
        return Response(co2_for_installation(
            config.installation, since=since, until=until))

    @extend_schema(parameters=[_SINCE, _UNTIL], responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=['get'], url_path='co2-fleet',
            permission_classes=[IsAnyRole])
    def co2_fleet(self, request):
        """FG286 — CO₂ évité par système ET cumulé sur le parc de la société."""
        from .selectors import co2_fleet
        company = request.user.company
        if company is None:
            return Response({'systems': [], 'total_co2_kg': 0})
        since = date_iso(request, 'since')
        until = date_iso(request, 'until')
        return Response(co2_fleet(company, since=since, until=until))

    @extend_schema(parameters=[_WINDOW], responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=['get'], url_path='soiling',
            permission_classes=[IsAnyRole])
    def soiling(self, request, pk=None):
        """FG283 — perte estimée par salissure (chute de PR entre nettoyages)
        + recommandation de nettoyage. ?window_days=365 (défaut)."""
        config = self.get_object()
        window = entier_borne(
            request, 'window_days', 365, mini=1, maxi=1825)
        return Response(
            soiling_assessment(config.installation, window_days=window))

    @extend_schema(
        parameters=[
            OpenApiParameter('period', OpenApiTypes.STR, required=False,
                             enum=['monthly', 'quarterly']),
            OpenApiParameter('format', OpenApiTypes.STR, required=False,
                             enum=['pdf']),
        ],
        responses={(200, 'application/json'): OpenApiTypes.OBJECT,
                   (200, 'application/pdf'): OpenApiTypes.BINARY})
    @action(detail=True, methods=['get'], url_path='om-report',
            permission_classes=[IsAnyRole])
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
        request=inline_serializer('MonitoringEmailOmReport', {
            'period': serializers.CharField(required=False),
            'recipient': serializers.CharField(required=False)}),
        responses=inline_serializer('MonitoringEmailOmReportReponse', {
            'sent': serializers.BooleanField()}))
    @action(detail=True, methods=['post'], url_path='email-om-report',
            permission_classes=[IsResponsableOrAdmin])
    def email_om_report(self, request, pk=None):
        """FG289 — envoie le rapport O&M périodique par e-mail (PDF joint).
        Destinataire : body `recipient` sinon l'e-mail du client du système."""
        from .report import EnvoiRapportImpossible, email_om_report
        config = self.get_object()
        period = request.data.get('period', 'monthly')
        recipient = request.data.get('recipient') or None
        try:
            sent = email_om_report(
                config.installation, period=period, recipient=recipient)
        except EnvoiRapportImpossible as exc:
            # ASAV68 — l'e-mail n'est pas parti : jamais {sent: true}.
            return Response(
                {'detail': f'Envoi impossible : {exc}'},
                status=status.HTTP_502_BAD_GATEWAY)
        return Response({'sent': sent})

    @extend_schema(
        parameters=[OpenApiParameter('annee', OpenApiTypes.INT, required=False)],
        responses=_PDF)
    @action(detail=True, methods=['get'], url_path='rapport-garantie-pdf',
            permission_classes=[IsAnyRole])
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
            permission_classes=[IsAnyRole])
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
            permission_classes=[IsAnyRole])
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


@extend_schema_view(list=extend_schema(
    parameters=_FILTRE_INSTALLATION))
class ProductionWarrantyViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG282 — garantie de production par système. Lecture tout rôle
    (filtrable par ?installation=) ; écriture responsable/admin. Action
    `status` : production réelle vs garanti dégradé → manque/compensation."""
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

    @extend_schema(
        parameters=[OpenApiParameter('year', OpenApiTypes.INT, required=False)],
        responses=OpenApiTypes.OBJECT)
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
            OpenApiParameter('years', OpenApiTypes.INT, required=False),
            OpenApiParameter('drift_threshold_pct', OpenApiTypes.NUMBER,
                             required=False),
        ],
        responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=['get'], url_path='curve',
            permission_classes=[IsAnyRole])
    def curve(self, request, pk=None):
        """FG284 — superpose production mesurée et courbe garantie de
        dégradation par année → dérive anormale → recours fabricant.
        ?years=N pour borner ; ?drift_threshold_pct=X pour le seuil."""
        warranty = self.get_object()
        years = entier_borne(request, 'years', None, mini=1, maxi=100)
        threshold = decimal_param(request, 'drift_threshold_pct')
        result = warranty_curve_overlay(
            warranty.installation, years=years,
            drift_threshold_pct=threshold)
        return Response(result)


class MonitoringSettingsViewSet(TenantMixin, viewsets.ModelViewSet):
    """Réglage société de sous-performance (N52). Singleton par société :
    `list` renvoie l'unique enregistrement ; écriture responsable/admin."""
    queryset = MonitoringSettings.objects.all()
    serializer_class = MonitoringSettingsSerializer
    parser_classes = [JSONParser]
    pagination_class = None

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

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
        """Upsert du singleton société (PATCH-like via POST)."""
        company = request.user.company
        obj = MonitoringSettings.get(company)
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(company=company)
        return Response(serializer.data, status=status.HTTP_200_OK)
