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
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

#: Identifiants de contexte retirés du corps avant le calcul.
CLES_CONTEXTE = ('devis', 'lead')

#: Forme de réponse = clés de ``exemple`` du contrat
#: ``contract_samples/etude_ci_preview.json`` (PACT7 : jamais un objet vide).
EtudeCiPreviewResponse = inline_serializer('EtudeCiPreviewResponse', {
    'entrees_resolues': serializers.JSONField(),
    'niveau_donnees': serializers.CharField(),
    'sous_reserve_visite': serializers.JSONField(),
    'profil_charge': serializers.JSONField(),
    'production': serializers.JSONField(),
    'taille': serializers.JSONField(),
    'bilan': serializers.JSONField(),
    'economie_ci': serializers.JSONField(),
    'composition': serializers.JSONField(),
    'regime_8221_suggere': serializers.JSONField(),
    'alertes': serializers.ListField(child=serializers.JSONField()),
    'hypotheses': serializers.ListField(child=serializers.JSONField()),
    'methode': serializers.CharField(),
    'version_moteur': serializers.CharField(),
})


def _devis_de_la_societe(company, devis_id, user=None):
    """Le devis ``devis_id`` de la société, borné à la portée équipe de
    ``user`` (ADEV21 — mêmes ``owner_fields`` que ``DevisViewSet``)."""
    if not devis_id or company is None:
        return None
    from .models import Devis
    qs = Devis.objects.filter(company=company)
    if user is not None:
        from core.scoping import scope_queryset
        qs = scope_queryset(qs, user, ['created_by'])
    try:
        return qs.filter(pk=int(devis_id)).first()
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
    request=OpenApiTypes.OBJECT, responses={200: EtudeCiPreviewResponse},
)
@api_view(['POST'])
@permission_classes([IsAnyRole])
def etude_ci_preview(request):
    """POST /ventes/etude-ci/preview/ — calcule, n'écrit rien."""
    from .domain.etude_ci import etudier_ci

    corps = request.data if isinstance(request.data, dict) else {}
    company = getattr(request.user, 'company', None)
    devis = _devis_de_la_societe(company, corps.get('devis'), request.user)
    if corps.get('devis') not in (None, '') and devis is None:
        # ADEV21 — un devis désigné mais hors société ou hors portée : 404,
        # jamais un calcul silencieux sur ses données.
        return Response({'detail': 'Devis introuvable.'}, status=404)
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
