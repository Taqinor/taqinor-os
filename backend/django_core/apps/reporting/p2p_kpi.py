"""NTP2P46 — Dashboard KPI Procure-to-Pay dans ``apps.reporting``.

Combine en UNE vue les briques déjà existantes de ``apps.stock`` (dashboard
spend management NTP2P17), JAMAIS regroupées ensemble côté reporting — même
patron que ``technicien_scorecard.py`` (agrège, n'importe aucun modèle
métier, appelle exclusivement des sélecteurs déjà en place) :

  * ``delai_demande_bcf_jours`` — délai moyen demande→BCF (cycle time),
    ``apps.stock.selectors.tableau_bord_achats``.
  * ``budgets_departement`` — montant engagé vs budgété par département
    (NTP2P4), même sélecteur (``taux_consommation_pct`` par ligne).
  * ``conformite_fournisseur_moyenne`` — moyenne des ``score_risque``
    (NTP2P8) des fournisseurs qui EN portent un,
    ``apps.stock.selectors.conformite_fournisseurs``.

``taux_conversion_pct`` (NTP2P47) — % de demandes ``commandee`` (converties)
parmi les demandes DÉCIDÉES (``commandee`` + ``refusee``, en excluant les
demandes encore en cours — ``brouillon``/``soumise``/``approuvee`` non
commandée — qui n'ont pas encore d'issue) : ``apps.installations.selectors.
comptes_demandes_achat_par_statut`` (NOUVEAU sélecteur cross-app en LECTURE
SEULE). ``None`` (jamais 0/``KeyError``) si aucune demande n'a encore été
décidée sur la période.

Lecture seule, réservé Responsable/Admin (pilotage achats), multi-tenant.
"""
from datetime import date

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin

# NTP2P46 — la forme RÉELLE de `dashboard_p2p()`, jamais `OpenApiTypes.OBJECT`
# (incident du 03/08/2026, PACT7). Même patron que
# `apps/ao/calepinage_views.py` : chaque liste imbriquée est un
# `inline_serializer(..., many=True)` à nom unique.
KPI_P2P_RESPONSE = inline_serializer('ReportingKpiP2p', {
    'debut': serializers.CharField(allow_null=True),
    'fin': serializers.CharField(allow_null=True),
    'delai_demande_bcf_jours': serializers.FloatField(allow_null=True),
    'budgets_departement': inline_serializer(
        'ReportingP2pBudgetDepartement', {
            'budget_id': serializers.IntegerField(),
            'departement_id': serializers.IntegerField(),
            'periodicite': serializers.CharField(),
            'annee': serializers.IntegerField(),
            'mois': serializers.IntegerField(),
            'montant_alloue': serializers.DecimalField(
                max_digits=14, decimal_places=2),
            'engage': serializers.DecimalField(
                max_digits=14, decimal_places=2),
            'realise': serializers.DecimalField(
                max_digits=14, decimal_places=2),
            'consomme_total': serializers.DecimalField(
                max_digits=14, decimal_places=2),
            'restant': serializers.DecimalField(
                max_digits=14, decimal_places=2),
            'taux_consommation_pct': serializers.FloatField(),
        }, many=True),
    'conformite_fournisseur_moyenne': serializers.FloatField(
        allow_null=True),
    'taux_conversion_pct': serializers.FloatField(allow_null=True),
})


def _qdate(value):
    """Parse une date ``?debut=``/``?fin=`` au format ISO, ou ``None``."""
    try:
        return date.fromisoformat((value or '').strip())
    except (ValueError, TypeError):
        return None


def _conformite_fournisseur_moyenne(company, *, debut=None, fin=None):
    """Moyenne des ``score_risque`` (NTP2P8) des fournisseurs actifs qui EN
    portent un. ``None`` (jamais 0) si aucun fournisseur n'a de score."""
    from apps.stock.selectors import conformite_fournisseurs

    lignes = conformite_fournisseurs(company, debut=debut, fin=fin)
    scores = [ligne['score_risque'] for ligne in lignes
              if ligne.get('score_risque') is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def _taux_conversion_pct(company, *, debut=None, fin=None):
    """NTP2P47 — % de demandes d'achat ``commandee`` parmi les demandes
    DÉCIDÉES (``commandee`` + ``refusee``). ``None`` (jamais 0) si aucune
    demande n'a encore été décidée sur la période."""
    from apps.installations.selectors import comptes_demandes_achat_par_statut

    comptes = comptes_demandes_achat_par_statut(company, debut=debut, fin=fin)
    commandees = comptes.get('commandee', 0)
    refusees = comptes.get('refusee', 0)
    decidees = commandees + refusees
    if not decidees:
        return None
    return round(commandees / decidees * 100, 1)


def dashboard_p2p(company, *, debut=None, fin=None):
    """NTP2P46 — KPI Procure-to-Pay agrégés d'une société sur la période."""
    from apps.stock.selectors import tableau_bord_achats

    achats = tableau_bord_achats(company, debut, fin)
    return {
        'debut': achats.get('debut'),
        'fin': achats.get('fin'),
        'delai_demande_bcf_jours': achats.get('delai_demande_bcf_jours'),
        'budgets_departement': achats.get('budgets_departement'),
        'conformite_fournisseur_moyenne': _conformite_fournisseur_moyenne(
            company, debut=debut, fin=fin),
        'taux_conversion_pct': _taux_conversion_pct(
            company, debut=debut, fin=fin),
    }


@extend_schema(responses=KPI_P2P_RESPONSE)
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def kpi_p2p(request):
    """``GET reporting/p2p/kpi/?debut=&fin=`` — widget dashboard achats."""
    if not request.user.company_id:
        return Response({'detail': 'Société requise.'}, status=400)
    debut = _qdate(request.query_params.get('debut'))
    fin = _qdate(request.query_params.get('fin'))
    return Response(
        dashboard_p2p(request.user.company, debut=debut, fin=fin))
