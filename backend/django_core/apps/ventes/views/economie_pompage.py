"""AGR206 — l'économie DÉCLARÉE d'un devis de pompage, exposée.

* ``GET /api/django/ventes/devis/<pk>/economie-pompage/`` — action GREFFÉE au
  ``DevisViewSet`` (patron ``views/economie.py``) : ``IsAnyRole``, 404 hors
  société (``get_object`` passe par le queryset scopé), lecture seule, rend le
  bloc AVEC ``vue_interne`` (écran interne seulement) ;
* ``POST /api/django/ventes/economie-pompage/preview/`` — aperçu : saisies +
  sortie de l'aperçu pompage + lignes de l'écran ; l'investissement est
  RECALCULÉ côté serveur depuis ``produit`` (lu DANS la société) et les prix
  transmis ; AUCUNE écriture.

Un seul calcul (``economie_pompage.economie_pompage_depuis``) sert l'écran,
le PDF, /proposition et le devis automatique (D-AGR-1). Jamais de
``prix_achat`` : l'investissement est le total TTC CLIENT. Règle #4 : aucun
statut changé.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

from ..economie import EconomieInvalide
from ..economie_pompage import (
    economie_pompage_depuis, economie_pompage_pour_devis)
from .devis import DevisViewSet

__all__ = ['economie_pompage', 'economie_pompage_preview']

#: Forme documentée du bloc (PACT7 — jamais un « object » vide) : les clés du
#: contrat contract_samples/economie_pompage.json (``exemple``).
EconomiePompageResponse = inline_serializer('EconomiePompageResponse', {
    'statut': serializers.JSONField(allow_null=True),
    'publiable_client': serializers.JSONField(allow_null=True),
    'motifs_non_publiable': serializers.JSONField(allow_null=True),
    'cas': serializers.JSONField(allow_null=True),
    'entrees_declarees': serializers.JSONField(allow_null=True),
    'depense_actuelle': serializers.JSONField(allow_null=True),
    'charges_solaires': serializers.JSONField(allow_null=True),
    'remplacements': serializers.JSONField(allow_null=True),
    'economie': serializers.JSONField(allow_null=True),
    'couverture': serializers.JSONField(allow_null=True),
    'mad_par_m3': serializers.JSONField(allow_null=True),
    'sensibilite_carburant': serializers.JSONField(allow_null=True),
    'seuil_rentabilite_carburant': serializers.JSONField(allow_null=True),
    'financement': serializers.JSONField(allow_null=True),
    'coherence': serializers.JSONField(allow_null=True),
    'reperes_affiches': serializers.JSONField(allow_null=True),
    'omissions': serializers.JSONField(allow_null=True),
    'vue_interne': serializers.JSONField(allow_null=True),
})


def _refus(refus):
    return Response({'detail': str(refus), 'champ': refus.champ},
                    status=status.HTTP_400_BAD_REQUEST)


@action(detail=True, methods=['get'], url_path='economie-pompage',
        permission_classes=[IsAnyRole])
def economie_pompage(self, request, pk=None):
    """AGR206 — le bloc économie de pompage du devis (contrat AGR3)."""
    devis = self.get_object()
    try:
        bloc = economie_pompage_pour_devis(devis.pk, devis.company)
    except EconomieInvalide as refus:
        return _refus(refus)
    return Response(bloc)


def _lignes_ecran(company, lignes):
    """Lignes de l'écran enrichies du produit lu DANS la société (rôle,
    catégorie, garantie) ; un produit étranger ou inconnu n'apporte rien."""
    from apps.stock.selectors import get_produit_scoped

    sorties = []
    for ligne in lignes if isinstance(lignes, list) else []:
        if not isinstance(ligne, dict):
            continue
        sortie = {k: ligne.get(k) for k in (
            'designation', 'quantite', 'prix_unitaire', 'remise', 'taux_tva',
            'optionnelle', 'type_ligne')}
        produit = None
        try:
            if ligne.get('produit') not in (None, ''):
                produit = get_produit_scoped(company, int(ligne['produit']))
        except (TypeError, ValueError):
            produit = None
        if produit is not None:
            categorie = getattr(produit, 'categorie', None)
            sortie['type_equipement'] = getattr(
                categorie, 'type_equipement', None)
            sortie['role_pompage'] = getattr(produit, 'role_pompage', None) \
                or None
            sortie['garantie_mois'] = getattr(produit, 'garantie_mois', None)
            if not sortie.get('designation'):
                sortie['designation'] = getattr(produit, 'nom', '')
        sorties.append(sortie)
    return sorties


@extend_schema(
    summary="Aperçu de l'économie de pompage (AGR206, aucune écriture)",
    request=OpenApiTypes.OBJECT,
    responses={200: EconomiePompageResponse},
)
@api_view(['POST'])
@permission_classes([IsAnyRole])
def economie_pompage_preview(request):
    """POST /ventes/economie-pompage/preview/ — calcule, n'écrit rien."""
    corps = request.data if isinstance(request.data, dict) else {}
    company = getattr(request.user, 'company', None)
    saisies = corps.get('saisies')
    sortie = corps.get('sortie_etude_pompage')
    try:
        bloc = economie_pompage_depuis(
            company, saisies if isinstance(saisies, dict) else {},
            sortie_etude=sortie if isinstance(sortie, dict) else None,
            lignes=_lignes_ecran(company, corps.get('lignes')))
    except EconomieInvalide as refus:
        return _refus(refus)
    return Response(bloc)


# Rattachement au viewset PIVOT — voir la docstring de ``views/economie.py``.
DevisViewSet.economie_pompage = economie_pompage
