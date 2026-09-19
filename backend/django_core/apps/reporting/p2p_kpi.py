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

``taux_conversion_pct`` (% de demandes converties vs rejetées) est
VOLONTAIREMENT ``None`` : aucun sélecteur cross-app en LECTURE
n'expose aujourd'hui un compte par statut (soumise/approuvée/refusée) de
``apps.installations.DemandeAchat`` — seul le compte des demandes
CONVERTIES existe (``demandes_achat_converties``). Ajouter un tel sélecteur
vit dans ``apps/installations`` (hors périmètre de cette lane) ; jamais un
taux inventé ou une ``KeyError`` à la place.

Lecture seule, réservé Responsable/Admin (pilotage achats), multi-tenant.
"""
from datetime import date

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin


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
        'taux_conversion_pct': None,
    }


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
