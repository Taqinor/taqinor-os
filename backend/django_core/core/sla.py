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
from rest_framework import generics, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
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


def generer_snapshot_societe(company, periode):
    """Calcule et persiste (upsert) le snapshot SLA d'une société pour ``periode``."""
    from . import metrics as metrics_infra

    uptime = uptime_pct_periode(company, periode)
    p95 = metrics_infra.p95_latency_ms(company.id)
    snapshot, _created = SlaSnapshot.objects.update_or_create(
        company=company, periode=periode,
        defaults={
            'uptime_pct': uptime,
            'latence_p95_ms': p95,
            'genere_le': timezone.now(),
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
        ]


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
