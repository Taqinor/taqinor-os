"""AGR121 — Aperçu serveur du pompage : POST /ventes/etude-pompage/preview/.

D-AGR-1 : UN seul calcul serveur sert l'écran (aperçu en direct), le PDF,
/proposition et le devis automatique. Cette vue n'est qu'une porte HTTP sur
:func:`apps.ventes.domain.pompage.etudier_pompage` ; elle rend EXACTEMENT la
forme du contrat ``contract_samples/etude_pompage_preview.json``.

AUCUNE ÉCRITURE : ni devis, ni statut, ni ligne, ni colonne de lead. POST
parce que tout dépend d'une saisie (patron ``etude_horaire_view.py`` :
fonction ``@api_view``, jamais une action de ViewSet).

Company-scopé : la société vient TOUJOURS de ``request.user``, jamais du
corps. ``devis`` / ``lead`` (identifiants facultatifs du corps) sont résolus
DANS la société de l'appelant uniquement ; un identifiant étranger est ignoré.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

#: Forme documentée de l'aperçu (PACT7 — jamais un « object » vide) : les
#: clés EXACTES rendues par la vue, cf. contract_samples/etude_pompage_preview.json.
EtudePompagePreviewResponse = inline_serializer('EtudePompagePreviewResponse', {
    'entrees_resolues': serializers.JSONField(allow_null=True),
    'hmt': serializers.JSONField(allow_null=True),
    'besoin': serializers.JSONField(allow_null=True),
    'conception': serializers.JSONField(allow_null=True),
    'pompe': serializers.JSONField(allow_null=True),
    'variateur': serializers.JSONField(allow_null=True),
    'prix_a_renseigner': serializers.JSONField(allow_null=True),
    'puissance_retenue': serializers.JSONField(allow_null=True),
    'champ': serializers.JSONField(allow_null=True),
    'production': serializers.JSONField(allow_null=True),
    'couverture_pct_mois': serializers.JSONField(allow_null=True),
    'controle_conception': serializers.JSONField(allow_null=True),
    'ha_irrigables': serializers.JSONField(allow_null=True),
    'autonomie_reservoir_jours': serializers.JSONField(allow_null=True),
    'tailles': serializers.JSONField(allow_null=True),
    'tailles_omises': serializers.JSONField(allow_null=True),
    'kit': serializers.JSONField(allow_null=True),
    'alertes': serializers.JSONField(allow_null=True),
    'hypotheses': serializers.JSONField(allow_null=True),
    'methode': serializers.JSONField(allow_null=True),
})

#: Identifiants de contexte retirés du corps avant le calcul (ce ne sont pas
#: des entrées du dimensionnement).
CLES_CONTEXTE = ('devis', 'lead')


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
    summary="Aperçu serveur du pompage solaire (AGR121, aucune écriture)",
    description=("Dimensionnement agricole complet (HMT, besoin, pompe, "
                 "variateur, champ, production, tailles, kit) — forme du "
                 "contrat etude_pompage_preview.json. Société = celle de "
                 "l'appelant."),
    request=OpenApiTypes.OBJECT,
    responses={200: EtudePompagePreviewResponse},
)
@api_view(['POST'])
@permission_classes([IsAnyRole])
def etude_pompage_preview(request):
    """POST /ventes/etude-pompage/preview/ — calcule, n'écrit rien."""
    from .domain.pompage import etudier_pompage

    corps = request.data if isinstance(request.data, dict) else {}
    company = getattr(request.user, 'company', None)
    devis = _devis_de_la_societe(company, corps.get('devis'), request.user)
    if corps.get('devis') not in (None, '') and devis is None:
        # ADEV21 — un devis désigné mais hors société ou hors portée : 404,
        # jamais un calcul silencieux sur ses données.
        # (exception, pas un dict : la forme 200 du contrat reste seule.)
        from rest_framework.exceptions import NotFound
        raise NotFound('Devis introuvable.')
    lead = _lead_de_la_societe(company, corps.get('lead'))
    entrees = {k: v for k, v in corps.items() if k not in CLES_CONTEXTE}
    etude = etudier_pompage(company, entrees, devis=devis, lead=lead)
    return Response({
        'entrees_resolues': etude['entrees_resolues'],
        'hmt': etude['hmt'],
        'besoin': etude['besoin'],
        'conception': etude['conception'],
        'pompe': etude['pompe'],
        'variateur': etude['variateur'],
        'prix_a_renseigner': etude['prix_a_renseigner'],
        'puissance_retenue': etude['puissance_retenue'],
        'champ': etude['champ'],
        'production': etude['production'],
        'couverture_pct_mois': etude['couverture_pct_mois'],
        'controle_conception': etude['controle_conception'],
        'ha_irrigables': etude['ha_irrigables'],
        'autonomie_reservoir_jours': etude['autonomie_reservoir_jours'],
        'tailles': etude['tailles'],
        'tailles_omises': etude['tailles_omises'],
        'kit': etude['kit'],
        'alertes': etude['alertes'],
        'hypotheses': etude['hypotheses'],
        'methode': etude['methode'],
    })
