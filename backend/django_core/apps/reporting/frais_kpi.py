"""NTP2P47 — Dashboard KPI notes de frais & per-diem dans ``apps.reporting``.

Combine en UNE vue les quatre sélecteurs d'agrégation ajoutés à
``apps.frais.selectors`` — même patron que ``p2p_kpi.py`` (agrège, n'importe
aucun modèle métier directement, appelle exclusivement des sélecteurs déjà
en place) :

  * ``total_rembourse_par_categorie`` — total remboursé par catégorie de
    dépense sur la période.
  * ``top_employes_par_montant_notes_frais`` — top 5 employés par montant de
    notes de frais.
  * ``delai_moyen_depense_remboursement_jours`` — délai moyen (jours) entre
    la dépense et son remboursement.
  * ``total_per_diem_par_destination`` — total per-diem missions (NTP2P12)
    par destination.

Lecture seule, réservé Responsable/Admin (pilotage RH/dépenses), multi-tenant.
"""
from datetime import date

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin

# NTP2P47 — la forme RÉELLE de `dashboard_frais_kpi()`, jamais
# `OpenApiTypes.OBJECT` (incident du 03/08/2026, PACT7). Même patron que
# `apps/ao/calepinage_views.py` : chaque liste imbriquée est un
# `inline_serializer(..., many=True)` à nom unique.
KPI_FRAIS_RESPONSE = inline_serializer('ReportingKpiFrais', {
    'debut': serializers.DateField(allow_null=True),
    'fin': serializers.DateField(allow_null=True),
    'total_rembourse_par_categorie': inline_serializer(
        'ReportingFraisCategorie', {
            'categorie': serializers.CharField(),
            'categorie_display': serializers.CharField(),
            'montant_total': serializers.DecimalField(
                max_digits=14, decimal_places=2),
        }, many=True),
    'top_employes': inline_serializer('ReportingFraisTopEmploye', {
        'employe_id': serializers.IntegerField(),
        'employe_nom': serializers.CharField(),
        'montant_total': serializers.DecimalField(
            max_digits=14, decimal_places=2),
    }, many=True),
    'delai_moyen_depense_remboursement_jours': serializers.FloatField(
        allow_null=True),
    'total_per_diem_par_destination': inline_serializer(
        'ReportingFraisPerDiemDestination', {
            'destination': serializers.CharField(allow_blank=True),
            'montant_total': serializers.DecimalField(
                max_digits=14, decimal_places=2),
        }, many=True),
})


def _qdate(value):
    """Parse une date ``?debut=``/``?fin=`` au format ISO, ou ``None``."""
    try:
        return date.fromisoformat((value or '').strip())
    except (ValueError, TypeError):
        return None


def dashboard_frais_kpi(company, *, debut=None, fin=None):
    """NTP2P47 — KPI notes de frais & per-diem agrégés d'une société sur la
    période."""
    from apps.frais.selectors import (
        delai_moyen_depense_remboursement_jours,
        top_employes_par_montant_notes_frais,
        total_per_diem_par_destination,
        total_rembourse_par_categorie,
    )

    return {
        'debut': debut,
        'fin': fin,
        'total_rembourse_par_categorie': total_rembourse_par_categorie(
            company, debut=debut, fin=fin),
        'top_employes': top_employes_par_montant_notes_frais(
            company, debut=debut, fin=fin, limit=5),
        'delai_moyen_depense_remboursement_jours':
            delai_moyen_depense_remboursement_jours(
                company, debut=debut, fin=fin),
        'total_per_diem_par_destination': total_per_diem_par_destination(
            company, debut=debut, fin=fin),
    }


@extend_schema(responses=KPI_FRAIS_RESPONSE)
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def kpi_frais(request):
    """``GET reporting/frais/kpi/?debut=&fin=`` — widget dashboard RH/frais."""
    if not request.user.company_id:
        return Response({'detail': 'Société requise.'}, status=400)
    debut = _qdate(request.query_params.get('debut'))
    fin = _qdate(request.query_params.get('fin'))
    return Response(
        dashboard_frais_kpi(request.user.company, debut=debut, fin=fin))
