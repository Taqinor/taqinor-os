"""FG253 / CIQ114 — endpoint INTERNE de vérification de charge de toiture.

  POST /ventes/toiture/charge/ → masse ajoutée vs charge admissible DÉCLARÉE
       (avec sa source) ; sans capacité déclarée, verdict « non déclarée ».
       Une capacité ou un coefficient sans source → 400 FR nommant le champ.

Calcul PUR (aucune écriture base, aucun statut changé) ; jamais de prix ;
résultat interne, jamais imprimé au client. Les anciennes capacités par type
de toit (GET) ont disparu avec CIQ114.
"""
import math

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import (
    api_view, parser_classes, permission_classes,
)
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from . import openapi_shapes as SH
from .roof_load import ChargeNonSourcee, verifier_charge_toiture


#: ENF11 (api-fuzz « accepted schema-violating ») — champs du corps publié
#: (``openapi_shapes.RoofLoadRequest``) : nombres JSON (ou null) / textes (ou
#: null). Le calcul ignorait en silence ``"None"`` ou ``"abc"`` saisis pour un
#: nombre (corps multipart lu comme texte) au lieu de refuser la saisie.
_NOMBRES = ('charge_admissible_kg_m2', 'struct_masse_kg_m2',
            'poids_module_kg', 'aire_module_m2', 'masse_layout_kg_m2',
            'coefficient_securite')
_TEXTES = ('charge_admissible_source', 'couverture', 'coefficient_source')


def _corps_invalide(data):
    """``{champ: [message]}`` du premier champ mal typé, sinon ``None``."""
    if not isinstance(data, dict):
        return {'detail': 'Corps JSON objet attendu.'}
    for champ in _NOMBRES:
        valeur = data.get(champ)
        if valeur is not None and (isinstance(valeur, bool) or not isinstance(
                valeur, (int, float))):
            return {champ: ['Nombre attendu.']}
        if valeur is not None and not abs(valeur) <= SH.BORNE_CHARGE:
            return {champ: ['Valeur hors plage.']}
    for champ in _TEXTES:
        valeur = data.get(champ)
        if valeur is not None and not isinstance(valeur, str):
            return {champ: ['Texte attendu.']}
    return None


def _fini(valeur):
    """Faux si le résultat porte un flottant infini ou NaN (non sérialisable)."""
    if isinstance(valeur, float):
        return math.isfinite(valeur)
    if isinstance(valeur, dict):
        return all(_fini(v) for v in valeur.values())
    if isinstance(valeur, (list, tuple)):
        return all(_fini(v) for v in valeur)
    return True


@extend_schema(request=SH.RoofLoadRequest, responses=SH.RoofLoadResponse,
               extensions=SH.ROOF_LOAD_SOURCES)
@api_view(['POST'])
@parser_classes([JSONParser])  # ENF11/D2 : JSON seul, aucun envoi de fichier
@permission_classes([IsAnyRole])
def roof_load_check(request):
    """POST → vérification de charge (interne)."""
    data = request.data
    invalide = _corps_invalide(data)
    if invalide:
        return Response(invalide, status=400)
    try:
        result = verifier_charge_toiture(
            charge_admissible_kg_m2=data.get('charge_admissible_kg_m2'),
            charge_admissible_source=data.get('charge_admissible_source'),
            struct_masse_kg_m2=data.get('struct_masse_kg_m2'),
            poids_module_kg=data.get('poids_module_kg'),
            aire_module_m2=data.get('aire_module_m2'),
            masse_layout_kg_m2=data.get('masse_layout_kg_m2'),
            couverture=data.get('couverture'),
            coefficient_securite=data.get('coefficient_securite'),
            coefficient_source=data.get('coefficient_source'),
        )
    except ChargeNonSourcee as refus:
        return Response({refus.champ: [refus.message]}, status=400)
    if not _fini(result):
        # CI #997 fuzz (24/10) : des entrées dans les bornes dont le calcul ne
        # tient pas (``poids / aire`` d'une aire infime) : refus d'ÉTAT, 409.
        from core.conflit_etat import ConflitEtat
        raise ConflitEtat('Ces valeurs ne permettent pas de calcul fini : '
                          'vérifiez la surface et le poids du module.')
    return Response(result)
