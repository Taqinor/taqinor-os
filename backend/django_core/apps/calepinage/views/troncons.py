"""CALX228 — ``GET calepinages/<pk>/troncons/`` : le métré et la chute servis.

LE CONSTAT
----------
``views/electrique.py`` n'expose que trois actions (``resultat``,
``entree-electrique``, ``evaluer-electrique``) et ``resultat['cables']`` ne
porte que les DEUX lignes historiques (``W1`` DC, ``W2`` AC) : aucune chute
par tronçon, aucun métré par section, aucun cumul le long du chemin. Un
installateur ne pouvait donc ni commander son câble ni savoir OÙ la chute se
paie. Parité : HelioScope sert son SLD et ses conducteurs comme une vue
vivante du design (https://help-center.helioscope.com/hc/en-us/articles/
8198335127059-Single-Line-Diagram).

CE QUE CETTE PORTE GARANTIT
---------------------------
* la SOCIÉTÉ vient du serveur : ``get_object()`` est borné par le queryset du
  viewset (``CompanyScopedModelViewSet``), donc un calepinage d'une autre
  société est INTROUVABLE (404) et jamais « interdit » ;
* elle est en LECTURE PURE — ``troncons_du_calepinage`` ne fait que lire le
  document, la norme et la conception : aucun statut, aucun champ, aucune
  ligne de journal n'est écrit ;
* la charge utile est EXACTEMENT celle du contrat committé
  ``contract_samples/calepinage_troncons.json`` (CALX203) — ``troncons``,
  ``totaux``, ``omissions``, ``verdicts`` — et c'est la MÊME que la clé
  ``troncons`` du ``resultat`` (``services/electrique.py``) : deux formes du
  même métré, ce serait deux métrés.

LA GREFFE (piège de classe #105)
---------------------------------
L'action est posée sur le viewset pivot par AFFECTATION D'ATTRIBUT, et le nom
de l'attribut est EXACTEMENT ``fonction.__name__`` : DRF mappe par
``__name__``, un nom qui diverge fait disparaître la route. L'import qui
exécute ce module vit en FIN de ``views/rattachements.py``, donc AVANT
``router.register`` (``urls.py`` n'importe que ce module-là).
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage

__all__ = ['troncons']


@action(detail=True, methods=['get'], url_path='troncons',
        permission_classes=[PeutVoirCalepinage])
def troncons(self, request, pk=None):
    """CALX224-228 — le métré et la chute, tronçon par tronçon.

    Les quatre clés du contrat sont TOUJOURS présentes. Un plan sans
    cheminement rend ``troncons: []`` et une omission qui NOMME le champ
    absent (``electrical.cheminements``) : un calepinage sans tracé n'a pas
    « 0 % de chute », il n'a PAS de chute calculable.
    """
    from ..services.electrique import TemperaturesInvalides
    from ..services.troncons import troncons_du_calepinage

    calepinage = self.get_object()
    try:
        return Response(troncons_du_calepinage(calepinage))
    except TemperaturesInvalides as refus:
        # Une saisie de températures illisible est un refus MÉTIER qui nomme
        # son champ, jamais une erreur 500.
        return Response({refus.champ or 'temperatures': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7 / bug de classe #105).
CalepinageViewSet.troncons = troncons
