"""ACAL403 — ``GET``/``POST``/``DELETE calepinages/profil-depart/``.

Action de LISTE (un réglage société, sans identifiant de calepinage) :
``GET`` rend le profil tel que le fichier le porte (contrat ACAL387), chaque
valeur avec son ``etat`` lu sur les réglages de la société ;
``POST`` remplit les seules clés vides ; ``DELETE`` retire ce que le profil a
posé et qui n'a pas été retouché. Garde PAR MÉTHODE : lire = ``calepinage_voir``,
écrire = ``calepinage_approuver`` (``PERMISSIONS_ECRITURE_PAR_ACTION``).
Société TOUJOURS celle de l'appelant. Code métier : ``services/profil_depart.py``.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuApprouverCalepinage
from ..serializers import forme_du_contrat
from ..services.parametres import ReglageInterdit, ReglageInvalide
from ..services.profil_depart import (
    appliquer_profil, charger_profil, reference_ecrite, retirer_profil,
)
from .calepinages import CalepinageViewSet

__all__ = ['profil_depart']

_LIGNES = serializers.ListField(child=serializers.DictField())


def _avec_etats(profil, company):
    """Chaque valeur proposée + son ``etat`` LU sur les réglages stockés de
    ``company`` : ``a_appliquer`` (clé vide), ``posee_par_profil`` (la saisie
    exacte qu'« Appliquer » écrit, même règle que ``retirer_profil`` —
    « Retirer » la retirera) ou ``deja_saisie`` (une saisie, jamais touchée)."""
    from ..selectors import parametres_de_societe
    from ..services.parametres import _normaliser_cles_a_registre

    stockes = parametres_de_societe(company)
    valeurs = []
    for ligne in profil.get('valeurs', []):
        section, cle = ligne['section'], ligne['cle']
        actuelle = (stockes.get(section) or {}).get(cle)
        if actuelle is None:
            etat = 'a_appliquer'
        elif actuelle == _normaliser_cles_a_registre(section, {cle: {
                'valeur': ligne['valeur'], 'source': ligne['source'],
                'reference': reference_ecrite(ligne)}})[cle]:
            etat = 'posee_par_profil'
        else:
            etat = 'deja_saisie'
        valeurs.append(dict(ligne, etat=etat))
    return dict(profil, valeurs=valeurs)


@extend_schema(methods=['GET'], responses=forme_du_contrat(
    'CalepinageProfilDepart', 'calepinage_profil_depart.json'))
@extend_schema(methods=['POST'], request=None, responses=forme_du_contrat(
    'CalepinageProfilDepartApplication', 'calepinage_profil_depart.json',
    cle='exemple_application'))
@extend_schema(methods=['DELETE'], request=None, responses=inline_serializer(
    'CalepinageProfilDepartRetrait', {'retirees': _LIGNES, 'gardees': _LIGNES}))
@action(detail=False, methods=['get', 'post', 'delete'],
        url_path='profil-depart', url_name='profil-depart',
        permission_classes=[PeutLireOuApprouverCalepinage])
def profil_depart(self, request):
    """ACAL403 — lire, appliquer ou retirer le profil de départ sourcé."""
    methode = request.method.lower()
    company = getattr(request.user, 'company', None)
    if methode == 'get':
        return Response(_avec_etats(charger_profil(), company))
    geste = appliquer_profil if methode == 'post' else retirer_profil
    try:
        return Response(geste(company, user=request.user))
    except ReglageInterdit as refus:
        return Response({refus.champ: str(refus)},
                        status=status.HTTP_403_FORBIDDEN)
    except ReglageInvalide as refus:
        return Response({refus.champ or 'detail': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)


# Le nom d'attribut est EXACTEMENT celui de la fonction (piège CALX7).
CalepinageViewSet.profil_depart = profil_depart
