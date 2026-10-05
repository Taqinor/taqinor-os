"""CIQ118 — Aperçu serveur C&I : POST /ventes/etude-ci/preview/.

D-CIQ-0 : UN moteur serveur C&I sert l'écran, le devis automatique, le PDF et
/proposition. Cette vue n'est qu'une porte HTTP sur
:func:`apps.ventes.domain.etude_ci.etudier_ci` ; elle rend EXACTEMENT la forme
``exemple`` du contrat ``contract_samples/etude_ci_preview.json``.

AUCUNE ÉCRITURE (patron ``etude_horaire_view.py`` / ``etude_pompage_view.py``
: fonction ``@api_view``, jamais une action de ViewSet). Company-scopé : la
société vient TOUJOURS de ``request.user`` ; ``devis`` / ``lead`` du corps sont
résolus DANS la société de l'appelant, un identifiant étranger est ignoré.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

#: Identifiants de contexte retirés du corps avant le calcul.
CLES_CONTEXTE = ('devis', 'lead')


def _devis_de_la_societe(company, devis_id):
    if not devis_id or company is None:
        return None
    from .models import Devis
    try:
        return Devis.objects.filter(company=company, pk=int(devis_id)).first()
    except (TypeError, ValueError):
        return None


def _lead_de_la_societe(company, lead_id):
    if not lead_id or company is None:
        return None
    from apps.crm.selectors import get_company_lead
    try:
        return get_company_lead(company, int(lead_id))
    except (TypeError, ValueError):
        return None


@extend_schema(
    summary="Aperçu serveur de l'étude commercial / industriel (CIQ118, aucune écriture)",
    description=("Profil déclaré heure par heure, production PVGIS, taille par la "
                 "règle des 10 ans, bilan, économie, composition — forme du contrat "
                 "etude_ci_preview.json. Société = celle de l'appelant."),
    request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT},
)
@api_view(['POST'])
@permission_classes([IsAnyRole])
def etude_ci_preview(request):
    """POST /ventes/etude-ci/preview/ — calcule, n'écrit rien."""
    from .domain.etude_ci import etudier_ci

    corps = request.data if isinstance(request.data, dict) else {}
    company = getattr(request.user, 'company', None)
    devis = _devis_de_la_societe(company, corps.get('devis'))
    lead = _lead_de_la_societe(company, corps.get('lead'))
    entrees = {k: v for k, v in corps.items() if k not in CLES_CONTEXTE}
    etude = etudier_ci(company, entrees, devis=devis, lead=lead)
    return Response({
        'entrees_resolues': etude['entrees_resolues'],
        'niveau_donnees': etude['niveau_donnees'],
        'sous_reserve_visite': etude['sous_reserve_visite'],
        'profil_charge': etude['profil_charge'],
        'production': etude['production'],
        'taille': etude['taille'],
        'bilan': etude['bilan'],
        'economie_ci': etude['economie_ci'],
        'composition': etude['composition'],
        'regime_8221_suggere': etude['regime_8221_suggere'],
        'alertes': etude['alertes'],
        'hypotheses': etude['hypotheses'],
        'methode': etude['methode'],
        'version_moteur': etude['version_moteur'],
    })
