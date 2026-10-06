"""CIQ210 — Aperçu de l'économie C&I : POST /ventes/economie-ci/preview/.

Porte HTTP sur :func:`apps.ventes.economie_ci.assembler_economie_ci` — la
MÊME fonction que la lecture d'un devis (``GET devis/<pk>/economie-ci/``), le
PDF et /proposition (ces deux-là par ``economie_ci_publique``). Corps (contrat
``contract_samples/economie_ci.json``, ``corps_preview``) : ``sortie_etude_ci``
(réponse de l'aperçu C&I, contrat ``etude_ci_preview.json``), ``saisies``
(forme ``saisies_economie_ci``) et ``lignes`` [{produit, quantite, taux_tva,
totaux {ht, ttc}, optionnelle}].

AUCUNE ÉCRITURE (patron ``etude_ci_view.py`` : ``@api_view``, jamais une
action de ViewSet). Société = celle de l'appelant : un ``produit`` est lu DANS
la société (un identifiant étranger n'apporte rien). L'investissement est le
TOTAL CLIENT transmis (HT/TTC), jamais ``Produit.prix_achat``. Rend le bloc
INTERNE (avec ``vue_interne``) : écran interne seulement.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

#: Forme documentée (PACT7 — jamais un « object » vide) : les clés de
#: ``exemple`` du contrat ``contract_samples/economie_ci.json``.
EconomieCiResponse = inline_serializer('EconomieCiResponse', {
    cle: serializers.JSONField(allow_null=True) for cle in (
        'statut', 'motifs_omission', 'base', 'motif_base', 'tarif',
        'economie_annee1', 'facture_avant', 'facture_apres', 'revente',
        'flux_ht', 'flux_ttc', 'jalons', 'jalons_ttc', 'indicateurs',
        'remplacements', 'om', 'sensibilites', 'financement', 'hypotheses',
        'omissions', 'alertes_internes', 'vue_interne')
})


def refus_saisie(refus):
    """400 qui NOMME le champ refusé (``SaisieEconomieCiInvalide``)."""
    return Response({'detail': str(refus), 'champ': refus.champ},
                    status=status.HTTP_400_BAD_REQUEST)


def _nombre(valeur):
    try:
        if valeur is None or isinstance(valeur, bool):
            return None
        return float(valeur)
    except (TypeError, ValueError):
        return None


def lignes_ecran(company, lignes):
    """``(investissement {ht, ttc}, lignes)`` depuis les lignes de l'écran.

    Montants = totaux CLIENT transmis ; rôle onduleur / O&M lus sur le
    produit DE la société (jamais son prix d'achat)."""
    from apps.stock.selectors import get_produit_scoped

    from .economie_ci import _est_onduleur

    sorties = []
    ht_total = ttc_total = 0.0
    for ligne in lignes if isinstance(lignes, list) else []:
        if not isinstance(ligne, dict):
            continue
        totaux = ligne.get('totaux') if isinstance(ligne.get('totaux'),
                                                   dict) else {}
        ht, ttc = _nombre(totaux.get('ht')), _nombre(totaux.get('ttc'))
        produit = None
        try:
            if ligne.get('produit') not in (None, ''):
                produit = get_produit_scoped(company, int(ligne['produit']))
        except (TypeError, ValueError):
            produit = None
        optionnelle = bool(ligne.get('optionnelle'))
        if not optionnelle:
            ht_total += ht or 0.0
            ttc_total += ttc or 0.0
        sorties.append({
            'designation': ligne.get('designation')
            or (getattr(produit, 'nom', '') if produit else ''),
            'ht': ht, 'ttc': ttc, 'optionnelle': optionnelle,
            'onduleur': _est_onduleur(produit),
            'role_ci': (getattr(produit, 'role_ci', '') or None)
            if produit is not None else None,
        })
    investissement = {'ht': round(ht_total, 2), 'ttc': round(ttc_total, 2)} \
        if sorties else None
    return investissement, sorties


@extend_schema(
    summary="Aperçu de l'économie commercial / industriel (CIQ210, aucune "
            "écriture)",
    description=("Valorisation horaire au tarif du poste, base HT/TTC, flux "
                 "25 ans, revente, financement, vue interne — forme du "
                 "contrat economie_ci.json. Société = celle de l'appelant."),
    request=OpenApiTypes.OBJECT, responses={200: EconomieCiResponse},
)
@api_view(['POST'])
@permission_classes([IsAnyRole])
def economie_ci_preview(request):
    """POST /ventes/economie-ci/preview/ — calcule, n'écrit rien."""
    from .economie_ci import (
        SaisieEconomieCiInvalide, assembler_economie_ci, reglages_economie_ci)

    corps = request.data if isinstance(request.data, dict) else {}
    company = getattr(request.user, 'company', None)
    sortie = corps.get('sortie_etude_ci')
    saisies = corps.get('saisies')
    investissement, lignes = lignes_ecran(company, corps.get('lignes'))
    sortie = sortie if isinstance(sortie, dict) else {}
    mode = _mode(sortie)
    try:
        bloc = assembler_economie_ci(
            sortie, saisies=saisies if isinstance(saisies, dict) else {},
            investissement=investissement, lignes=lignes,
            mode_installation=mode, reglages=reglages_economie_ci(company))
    except SaisieEconomieCiInvalide as refus:
        return refus_saisie(refus)
    return Response(bloc)


def _mode(sortie):
    entree = (sortie.get('entrees_resolues') or {}).get('mode')
    return entree.get('valeur') if isinstance(entree, dict) else entree
