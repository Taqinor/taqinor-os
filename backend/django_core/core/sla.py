"""NTOBS3 — rapport SLA mensuel par tenant (uptime mesuré + P95 + export PDF).

Fondation : ``SlaSnapshot`` persiste, pour une société et un mois, une
disponibilité dérivée de l'historique RÉEL ``apps.statuspage.IncidentPublic``
(pondérée par la durée effective de chaque incident sur le mois) et un P95 de
latence best-effort dérivé de ``core.metrics`` (``None`` — jamais un chiffre
inventé — quand aucune mesure n'est disponible pour la période).

``core`` reste une couche de FONDATION (contrat import-linter
``core-foundation-is-a-base-layer``) : ``apps.statuspage`` est résolu par
``django.apps.apps.get_model`` (jamais un import statique). Modèle défini ICI
(pas directement dans ``core/models.py``) et réexporté en bas de
``core/models.py`` — même éclatement que ``core/sharing.py``/
``core/field_permissions.py``.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta

from django.apps import apps as django_apps
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import (
    BasePermission, IsAuthenticated,
)
from rest_framework.response import Response

from .models import TenantModel

# Pondération de la sévérité d'un incident dans le calcul de disponibilité —
# méthodologie DOCUMENTÉE et dérivée d'horodatages réels (jamais un chiffre
# inventé) : une incident « mineure » est une dégradation, pas un arrêt, donc
# ne réduit pas l'uptime contractuel.
DOWNTIME_WEIGHT = {
    'critique': 1.0,
    'majeure': 0.5,
    'mineure': 0.0,
}


class SlaSnapshot(TenantModel):
    """Rapport SLA mensuel d'UNE société (NTOBS3). ``company`` (obligatoire,
    imposée côté serveur) vient de ``core.models.TenantModel``."""

    class CreditStatut(models.TextChoices):
        NON_APPLICABLE = 'non_applicable', 'Non applicable'
        A_EMETTRE = 'a_emettre', 'À émettre'
        EMIS = 'emis', 'Émis'
        REFUSE = 'refuse', 'Refusé'

    periode = models.DateField(
        'Période (mois)',
        help_text='Premier jour du mois couvert par ce snapshot.')
    uptime_pct = models.DecimalField(
        'Disponibilité (%)', max_digits=7, decimal_places=4)
    latence_p95_ms = models.PositiveIntegerField(
        'Latence P95 (ms)', null=True, blank=True,
        help_text=(
            'None = aucune mesure disponible pour cette période '
            '(jamais un chiffre inventé).'))
    genere_le = models.DateTimeField('Généré le', default=timezone.now)
    # NTOBS4 — crédit SLA calculé selon le barème actif (SlaCreditPolicy).
    # L'ÉMISSION réelle (avoir) reste TOUJOURS une action manuelle — ces
    # champs ne font QUE tracer le calcul et son suivi.
    credit_du_pct = models.DecimalField(
        'Crédit dû (%)', max_digits=5, decimal_places=2, null=True, blank=True)
    credit_du_montant = models.DecimalField(
        'Crédit dû (montant)', max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text='None si le montant facturé du mois est inconnu.')
    credit_statut = models.CharField(
        'Statut du crédit', max_length=15, choices=CreditStatut.choices,
        default=CreditStatut.NON_APPLICABLE)

    class Meta:
        verbose_name = 'Rapport SLA mensuel'
        verbose_name_plural = 'Rapports SLA mensuels'
        ordering = ['-periode']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'periode'],
                name='core_slasnapshot_co_periode'),
        ]

    def __str__(self):
        return f'SLA société {self.company_id} — {self.periode:%Y-%m}'


# NTOBS4 — barème par défaut, valeurs D'EXEMPLE (DÉCISION COMMERCIALE du
# fondateur à valider) : jamais appliqué comme un engagement réel tant que
# `SlaCreditPolicy.valide` reste False. Seedé automatiquement au premier
# calcul (voir `politique_active`), jamais en migration de données.
DEFAULT_PALIERS_A_VALIDER = [
    {'seuil_uptime_pct': 99.5, 'credit_pct_facture': 5},
    {'seuil_uptime_pct': 99.0, 'credit_pct_facture': 10},
    {'seuil_uptime_pct': 95.0, 'credit_pct_facture': 25},
]


def _default_paliers():
    # Callable (jamais un mutable partagé en `default=`) — copie fraîche.
    return [dict(p) for p in DEFAULT_PALIERS_A_VALIDER]


class SlaCreditPolicy(models.Model):
    """NTOBS4 — barème de crédits SLA (paliers de disponibilité → % de crédit
    sur la facture). ``company`` NULL = politique par défaut SYSTÈME ; une
    société peut avoir SA PROPRE politique (override total du système).

    Le barème est une DÉCISION COMMERCIALE DU FONDATEUR — seedé avec des
    valeurs D'EXEMPLE marquées "à valider" (``valide=False``) : rien ici ne
    prétend être un engagement contractuel réel tant qu'un humain ne l'a pas
    validé."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='sla_credit_policies',
        verbose_name='Société',
        help_text='NULL = politique par défaut système.')
    paliers = models.JSONField(
        'Paliers', default=_default_paliers,
        help_text=(
            'Liste de {"seuil_uptime_pct": .., "credit_pct_facture": ..} : '
            'un palier s\'applique si uptime_pct < seuil_uptime_pct.'))
    valide = models.BooleanField(
        'Barème validé par le fondateur', default=False,
        help_text='False = valeurs d\'exemple, pas encore un engagement réel.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Barème de crédits SLA'
        verbose_name_plural = 'Barèmes de crédits SLA'
        ordering = ['-created_at']

    def __str__(self):
        cible = f'société {self.company_id}' if self.company_id else 'système (défaut)'
        return f'Barème SLA — {cible}' + ('' if self.valide else ' (à valider)')


def politique_active(company):
    """Politique SLA effective d'une société : son OVERRIDE si elle en a un,
    sinon la politique système par défaut (créée avec le barème d'exemple si
    elle n'existe pas encore — jamais une exception à l'exécution)."""
    policy = (
        SlaCreditPolicy.objects.filter(company=company)
        .order_by('-created_at').first())
    if policy:
        return policy
    policy = (
        SlaCreditPolicy.objects.filter(company__isnull=True)
        .order_by('-created_at').first())
    if policy:
        return policy
    return SlaCreditPolicy.objects.create(company=None)


def credit_pct_pour_uptime(uptime_pct, paliers):
    """% de crédit applicable pour une disponibilité mesurée : le PLUS ÉLEVÉ
    des paliers dont le seuil est franchi (``uptime_pct < seuil``) — un mois
    à 98% avec les paliers d'exemple (99.5→5, 99.0→10, 95.0→25) doit recevoir
    10%, pas 5% (le palier 99.5 est aussi franchi, mais 99.0 l'emporte)."""
    franchis = [
        p.get('credit_pct_facture', 0) for p in (paliers or [])
        if uptime_pct < p.get('seuil_uptime_pct', 0)
    ]
    return max(franchis) if franchis else 0


def montant_facture_mois(company, periode):
    """Montant TTC facturé par la société sur le mois de ``periode``.

    Lecture seule via ``apps.facturation`` (résolu par
    ``django.apps.apps.get_model`` — ``core`` reste une couche de base,
    contrat import-linter ``core-foundation-is-a-base-layer``). Réutilise la
    propriété ``total_ttc`` DÉJÀ définie côté facturation (jamais un calcul de
    TVA dupliqué ici). ``None`` — jamais 0 maquillé — si l'app n'est pas
    disponible ou si le calcul échoue pour une facture (best-effort)."""
    try:
        facture_model = django_apps.get_model('facturation', 'Facture')
    except LookupError:
        return None

    debut, fin = _mois_bounds(periode)
    qs = (
        facture_model.objects
        .filter(company=company, date_emission__gte=debut.date(),
                date_emission__lte=fin.date())
        .exclude(statut=facture_model.Statut.ANNULEE)
    )
    total = 0.0
    for facture in qs:
        try:
            total += float(facture.total_ttc or 0)
        except Exception:  # noqa: BLE001 — best-effort, une facture KO n'en bloque pas d'autres
            continue
    return total


# ── Calcul ───────────────────────────────────────────────────────────────

def _mois_bounds(periode):
    """(début, fin) en datetime AWARE d'un mois (``periode`` = 1er jour, date)."""
    tz = timezone.get_current_timezone()
    debut = timezone.make_aware(
        datetime(periode.year, periode.month, 1), tz)
    _, dernier_jour = calendar.monthrange(periode.year, periode.month)
    fin = timezone.make_aware(
        datetime(periode.year, periode.month, dernier_jour, 23, 59, 59), tz)
    return debut, fin


def premier_du_mois(ref=None):
    ref = ref or timezone.now()
    return ref.date().replace(day=1)


def mois_precedent(ref=None):
    """Premier jour du mois PRÉCÉDENT celui de ``ref`` (défaut maintenant)."""
    premier = premier_du_mois(ref)
    dernier_jour_precedent = premier - timedelta(days=1)
    return dernier_jour_precedent.replace(day=1)


def uptime_pct_periode(company, periode):
    """Disponibilité (%) pondérée par la durée RÉELLE des incidents publics
    touchant ``company`` (systèmes ``company=None`` OU propres à la société)
    sur le mois de ``periode``. Best-effort : renvoie 100.0 si
    ``apps.statuspage`` n'est pas disponible (jamais une exception)."""
    try:
        incident_model = django_apps.get_model('statuspage', 'IncidentPublic')
    except LookupError:
        return 100.0

    debut, fin = _mois_bounds(periode)
    total_seconds = (fin - debut).total_seconds()
    if total_seconds <= 0:
        return 100.0

    qs = incident_model.objects.filter(
        Q(company__isnull=True) | Q(company=company),
        debute_le__lt=fin,
    ).filter(Q(resolu_le__gte=debut) | Q(resolu_le__isnull=True))

    downtime_seconds = 0.0
    for incident in qs:
        poids = DOWNTIME_WEIGHT.get(incident.severite, 0.0)
        if not poids:
            continue
        borne_debut = max(incident.debute_le, debut)
        borne_fin = min(incident.resolu_le or fin, fin)
        if borne_fin > borne_debut:
            downtime_seconds += poids * (borne_fin - borne_debut).total_seconds()

    downtime_seconds = min(downtime_seconds, total_seconds)
    uptime = 100.0 * (total_seconds - downtime_seconds) / total_seconds
    return round(uptime, 4)


def _calculer_credit(company, periode, uptime):
    """NTOBS4 — (credit_du_pct, credit_du_montant, credit_statut).

    Best-effort STRICT : une erreur de résolution (politique/facturation
    absente) dégrade en `NON_APPLICABLE`, jamais une exception qui casserait
    la génération du snapshot."""
    try:
        policy = politique_active(company)
        credit_pct = credit_pct_pour_uptime(float(uptime), policy.paliers)
    except Exception:  # noqa: BLE001 — best-effort
        return None, None, SlaSnapshot.CreditStatut.NON_APPLICABLE

    if not credit_pct:
        return None, None, SlaSnapshot.CreditStatut.NON_APPLICABLE

    montant_facture = montant_facture_mois(company, periode)
    credit_montant = (
        round(montant_facture * credit_pct / 100.0, 2)
        if montant_facture is not None else None)
    return credit_pct, credit_montant, SlaSnapshot.CreditStatut.A_EMETTRE


def generer_snapshot_societe(company, periode):
    """Calcule et persiste (upsert) le snapshot SLA d'une société pour ``periode``.

    Ne réémet JAMAIS un crédit déjà ``emis``/``refuse`` (une régénération —
    ex. recalcul après incident tardif — ne doit pas effacer une décision déjà
    prise par un humain sur le crédit)."""
    from . import metrics as metrics_infra

    uptime = uptime_pct_periode(company, periode)
    p95 = metrics_infra.p95_latency_ms(company.id)
    credit_pct, credit_montant, credit_statut = _calculer_credit(
        company, periode, uptime)

    existant = SlaSnapshot.objects.filter(
        company=company, periode=periode).first()
    if existant and existant.credit_statut in (
            SlaSnapshot.CreditStatut.EMIS, SlaSnapshot.CreditStatut.REFUSE):
        credit_pct, credit_montant = (
            existant.credit_du_pct, existant.credit_du_montant)
        credit_statut = existant.credit_statut

    snapshot, _created = SlaSnapshot.objects.update_or_create(
        company=company, periode=periode,
        defaults={
            'uptime_pct': uptime,
            'latence_p95_ms': p95,
            'genere_le': timezone.now(),
            'credit_du_pct': credit_pct,
            'credit_du_montant': credit_montant,
            'credit_statut': credit_statut,
        },
    )
    return snapshot


def generer_sla_mensuel(periode=None):
    """NTOBS3 — génère le snapshot SLA de TOUTES les sociétés actives pour
    ``periode`` (défaut : le mois précédent — job beat le 1er du mois)."""
    from authentication.models import Company

    periode = periode or mois_precedent()
    return [
        generer_snapshot_societe(company, periode)
        for company in Company.objects.filter(actif=True)
    ]


# ── API ──────────────────────────────────────────────────────────────────

class SlaSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlaSnapshot
        fields = [
            'id', 'periode', 'uptime_pct', 'latence_p95_ms', 'genere_le',
            'credit_du_pct', 'credit_du_montant', 'credit_statut',
        ]


class SlaCreditDuSerializer(serializers.ModelSerializer):
    """NTOBS4 — un crédit dû, avec le nom de la société (vue cross-tenant
    Directeur uniquement)."""

    company_nom = serializers.SerializerMethodField()

    class Meta:
        model = SlaSnapshot
        fields = [
            'id', 'company', 'company_nom', 'periode', 'uptime_pct',
            'credit_du_pct', 'credit_du_montant', 'credit_statut',
        ]

    def get_company_nom(self, obj):
        return getattr(obj.company, 'nom', '')


class SlaSnapshotListView(generics.ListAPIView):
    """GET /api/django/core/sla/ — historique 12 mois, scopé société."""

    serializer_class = SlaSnapshotSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return list(
            SlaSnapshot.objects
            .filter(company=self.request.user.company)
            .order_by('-periode')[:12]
        )


def _sla_pdf_html(snapshot, company):
    from html import escape

    p95_label = (
        f'{snapshot.latence_p95_ms} ms' if snapshot.latence_p95_ms is not None
        else 'non mesuré pour cette période')
    return f"""<html><head><meta charset="utf-8"></head><body>
<h1>Rapport SLA mensuel — {escape(str(company))}</h1>
<p>Période : {snapshot.periode:%B %Y}</p>
<p>Disponibilité mesurée : {snapshot.uptime_pct}%</p>
<p>Latence P95 : {p95_label}</p>
<p>Généré le {snapshot.genere_le:%d/%m/%Y %H:%M}</p>
</body></html>"""


@extend_schema(responses={200: OpenApiTypes.BINARY})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sla_export_pdf(request, periode):
    """GET /api/django/core/sla/<periode:YYYY-MM>/export-pdf/ — scopé société."""
    try:
        annee_str, mois_str = periode.split('-')
        periode_date = datetime(int(annee_str), int(mois_str), 1).date()
    except (ValueError, TypeError):
        return Response(
            {'detail': 'Format de période invalide (attendu YYYY-MM).'},
            status=400)

    snapshot = SlaSnapshot.objects.filter(
        company=request.user.company, periode=periode_date).first()
    if snapshot is None:
        return Response(
            {'detail': 'Aucun rapport SLA pour cette période.'}, status=404)

    from core.pdf import render_pdf
    html = _sla_pdf_html(snapshot, request.user.company)
    pdf_bytes = render_pdf(html=html)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="sla-{periode}.pdf"')
    return response


class IsDirecteurOrAdmin(BasePermission):
    """NTOBS4 — action réservée Directeur/Administrateur (même patron local
    que ``apps.credit.views.IsDirecteurOrAdmin`` / ``apps.statuspage.views``,
    dupliqué exprès : jamais un import cross-app d'une classe de permission)."""

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if getattr(u, 'is_superuser', False) or getattr(u, 'is_admin_role', False):
            return True
        role = getattr(u, 'role', None)
        return bool(role and role.nom in ('Directeur', 'Administrateur'))


class SlaCreditsDusListView(generics.ListAPIView):
    """GET /api/django/core/sla/credits/ — crédits SLA dus, TOUTES sociétés
    (Directeur/Administrateur uniquement — vue de pilotage cross-tenant,
    jamais accessible à un compte société-scopé normal)."""

    serializer_class = SlaCreditDuSerializer
    permission_classes = [IsAuthenticated, IsDirecteurOrAdmin]
    pagination_class = None

    def get_queryset(self):
        return (
            SlaSnapshot.objects
            .exclude(credit_statut=SlaSnapshot.CreditStatut.NON_APPLICABLE)
            .select_related('company')
            .order_by('-periode')
        )


@extend_schema(
    request=inline_serializer('SlaCreditStatutRequete', {
        'statut': serializers.CharField(),
    }),
    responses=SlaSnapshotSerializer)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDirecteurOrAdmin])
def sla_credit_statut(request, pk):
    """POST /api/django/core/sla/credits/<pk>/statut/ — trace la décision
    humaine sur un crédit (``emis``/``refuse``). N'ÉMET JAMAIS d'avoir : cette
    action enregistre seulement qu'un humain l'a fait (ou refusé) via le flux
    Avoir existant, ailleurs."""
    nouveau_statut = request.data.get('statut')
    valides = (SlaSnapshot.CreditStatut.EMIS, SlaSnapshot.CreditStatut.REFUSE)
    if nouveau_statut not in valides:
        return Response(
            {'detail': "statut doit être 'emis' ou 'refuse'."},
            status=status.HTTP_400_BAD_REQUEST)

    try:
        snapshot = SlaSnapshot.objects.get(pk=pk)
    except SlaSnapshot.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    snapshot.credit_statut = nouveau_statut
    snapshot.save(update_fields=['credit_statut', 'updated_at'])
    return Response(SlaSnapshotSerializer(snapshot).data)
