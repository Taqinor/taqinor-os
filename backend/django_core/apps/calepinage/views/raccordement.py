"""CALX244 — le POINT DE RACCORDEMENT, servi en HTTP.

LE CONSTAT
----------
``views/electrique.py`` n'offrait que trois actions (``resultat``,
``entree-electrique``, ``evaluer-electrique``) et ``CHAMPS_ENTREE``
(``services/electrique.py``) n'admet AUCUNE clé de raccordement : un
installateur n'avait nulle part où déclarer sa puissance souscrite, son
régime de branchement, sa limite d'élévation ni le cos φ que son contrat de
raccordement lui impose. Les trois calculs existaient (CALX241-243) —
personne ne pouvait les atteindre.

UNE SEULE FORME D'URL (CAL233) : ``@action`` du viewset pivot, servie sous
``/api/django/calepinage/calepinages/<pk>/raccordement/``, jamais un second
viewset. Le ``GET`` lit, le ``POST`` enregistre la saisie ET REND le
raccordement recalculé — l'appelant n'a aucun second appel à enchaîner.
C'est pourquoi la garde est ``PeutLireOuEcrireCalepinage`` (CAL18) : elle
choisit le code par la MÉTHODE, donc un simple lecteur ne peut pas écrire et
un rédacteur n'est pas fermé en lecture.

OÙ VIT LA SAISIE
-----------------
Dans ``Calepinage.resultat['raccordement_saisie']`` — le ``JSONField`` qui
porte déjà ``sld_edition`` (CALX234) et le reste de ce que le moteur dépose.
Aucune migration, et ``update_fields=['resultat', 'updated_at']`` pour qu'une
saisie de raccordement ne réécrive jamais une conception.

CE QUI EST ENREGISTRÉ EST CE QUI EST REPUBLIÉ : la saisie persistée est le
bloc ``saisie`` NORMALISÉ que ``services/raccordement.py::bloc_raccordement``
vient de valider. Une valeur illisible n'entre donc jamais en base, et le
refus NOMME son champ (``source_limite``, ``phases``…, noms NUS du
contrat CALX205) pour que l'écran pose le message SOUS lui (règle fondateur
du 08/09/2026).

CE QUE CETTE VUE NE FAIT PAS
-----------------------------
Elle ne calcule rien : la conception, les tronçons et les réglages société
sont LUS (lecture seule), puis passés à la fonction pure qui assemble le
contrat CALX205. Aucun seuil n'est posé ici, aucun barème marocain n'est
supposé, aucun montant n'est publié (D-CALX 5).

La société vient TOUJOURS du serveur : ``get_object()`` est borné par le
queryset du viewset, donc un calepinage d'une autre société est INTROUVABLE
(404), jamais « interdit ».
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuEcrireCalepinage
from ..services.raccordement import (
    PREFIXE_CHAMP, RaccordementInvalide, bloc_raccordement,
)

__all__ = ['raccordement', 'CLE_SAISIE', 'champ_du_refus']

#: La clé de la saisie dans ``Calepinage.resultat`` (JSONField existant).
CLE_SAISIE = 'raccordement_saisie'


def champ_du_refus(champ):
    """Le nom de champ PUBLIÉ par un refus 400.

    Le service qualifie son champ (``raccordement.source_limite``) pour qu'un
    appelant interne sache de quel formulaire il parle ; le contrat CALX205,
    lui, fige les deux refus sur le nom NU du champ de provenance
    (``refus_limite_sans_source`` porte ``source_limite``, et sa garde exige
    « ce champ, et lui seul »). La porte HTTP publie donc le nom nu : c'est
    lui que l'écran cherche pour poser le message SOUS le bon champ.
    """
    nom = (champ or '').strip()
    if nom.startswith(PREFIXE_CHAMP):
        nom = nom[len(PREFIXE_CHAMP):]
    return nom or 'raccordement'


def _saisie_enregistree(calepinage):
    """La saisie déjà posée sur ce calepinage, ou ``{}`` — jamais un repli.

    Un ``resultat`` illisible (None, liste, texte) rend ``{}`` : l'état vide
    du contrat CALX205, où les cinq verdicts sont omis en nommant ce qui
    manque — pas une saisie devinée.
    """
    resultat = getattr(calepinage, 'resultat', None)
    if not isinstance(resultat, dict):
        return {}
    saisie = resultat.get(CLE_SAISIE)
    return saisie if isinstance(saisie, dict) else {}


def _persister(calepinage, saisie):
    """Écrit la saisie NORMALISÉE, sans toucher au reste de ``resultat``."""
    resultat = getattr(calepinage, 'resultat', None)
    resultat = dict(resultat) if isinstance(resultat, dict) else {}
    resultat[CLE_SAISIE] = saisie
    calepinage.resultat = resultat
    if getattr(calepinage, 'pk', None):
        calepinage.save(update_fields=['resultat', 'updated_at'])
    return saisie


def _bloc_du_calepinage(calepinage, saisie):
    """Les trois lectures du serveur, puis la fonction PURE qui assemble.

    Les tronçons viennent de ``services/troncons.py`` (leur ``ib_a`` est le
    seul courant lu) et les réglages de la section société
    « electrique_societe » du registre : aucun seuil n'est écrit ici.
    """
    from ..services.electrique import (
        conception_du_calepinage, parametres_societe,
    )
    from ..services.parametres_cles import SECTION_ELECTRIQUE_SOCIETE
    from ..services.troncons import troncons_du_calepinage

    conception, _materiel, _donnees, _document = conception_du_calepinage(
        calepinage)
    troncons = troncons_du_calepinage(calepinage).get('troncons') or []
    reglages = (parametres_societe(calepinage)
                .get(SECTION_ELECTRIQUE_SOCIETE) or {})
    return bloc_raccordement(conception, saisie, troncons, reglages)


@action(detail=True, methods=['get', 'post'], url_path='raccordement',
        permission_classes=[PeutLireOuEcrireCalepinage])
def raccordement(self, request, pk=None):
    """CALX244 — ``{saisie, calcul, verdicts}`` du point de raccordement.

    ``GET`` republie la saisie enregistrée ; ``POST`` valide, enregistre et
    rend le MÊME document recalculé. Un refus est 400 et NOMME son champ.
    """
    from ..services.electrique import TemperaturesInvalides

    calepinage = self.get_object()  # borné société par get_queryset
    ecriture = request.method.lower() == 'post'
    corps = request.data if isinstance(request.data, dict) else {}
    saisie = corps if ecriture else _saisie_enregistree(calepinage)
    try:
        bloc = _bloc_du_calepinage(calepinage, saisie)
    except RaccordementInvalide as refus:
        return Response({champ_du_refus(refus.champ): str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    except TemperaturesInvalides as refus:
        return Response(
            {getattr(refus, 'champ', '') or 'temperatures': str(refus)},
            status=status.HTTP_400_BAD_REQUEST)
    if ecriture:
        _persister(calepinage, bloc['saisie'])
    return Response(bloc)


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.raccordement = raccordement
