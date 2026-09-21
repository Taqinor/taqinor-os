"""CALX35 — ``POST /calepinages/<pk>/dupliquer/`` : EXPOSER l'existant.

LA CAPACITÉ ÉTAIT DÉJÀ LÀ
-------------------------
``services/variantes.py::dupliquer`` (CAL14) recopie DÉJÀ le layout et les
variantes vers un NOUVEAU calepinage sans reprendre ``devis`` ni
``appel_offre_id`` — sa docstring le dit, ses tests le prouvent. Aucune vue,
aucun bouton ne l'appelait : ``grep dupliquer`` sur ``views/`` et ``urls.py``
ne rendait rien. Cette vue n'écrit donc AUCUNE logique de copie ; elle ouvre
la porte HTTP du service qui existe. **Aucun second chemin de copie** (ni
``services/creation.py::dupliquer_calepinage``, ni une recopie inline).

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
------------------------------------------------------------
Même discipline que ``views/archivage.py`` (CAL208) et ``views/
bibliotheque.py`` (CAL246) : l'action est posée ICI et RATTACHÉE au
``CalepinageViewSet`` par une ligne ajoutée EN FIN de
``views/rattachements.py`` (décision D-CALX 13) — ``urls.py`` n'est pas
rouvert. Le nom de l'attribut de classe est EXACTEMENT celui de la fonction :
DRF mappe par ``__name__`` (piège CALX7).

``avec_variantes`` — LE DÉFAUT EST LE COMPORTEMENT D'AUJOURD'HUI (D12)
------------------------------------------------------------------------
``dupliquer`` recopie les variantes depuis CAL14 : le drapeau vaut donc
``True`` par défaut, et une requête qui ne le porte pas se comporte
exactement comme le service se comportait avant cette tâche. ``False`` est un
choix EXPLICITE de l'appelant.

LA RÉFÉRENCE DE LA COPIE — CE QUE LE TEXTE DE LA TÂCHE SUPPOSE, ET LE RÉEL
----------------------------------------------------------------------------
Le texte de CALX35 annonce « la référence neuve vient de
``core.numbering.next_reference`` ». ``Calepinage`` ne porte AUCUN champ
``reference`` : l'étiquette est DÉRIVÉE de la date de création et de
l'identifiant (``views/calepinages.py::_reference``, CAL17), et
``next_reference`` exige un champ porteur sur le modèle — l'ajouter serait
une migration, que la décision D-CALX 8 interdit dans ce lot. La copie porte
donc une référence NEUVE parce qu'elle porte un identifiant neuf, et cette
vue publie EXACTEMENT l'étiquette que la fiche affichera : un seul dérivateur,
jamais deux formes de référence pour un même objet.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage
from ..services.variantes import VarianteRefusee
from ..services.variantes import dupliquer as service_dupliquer

__all__ = ['dupliquer']


def _drapeau(brut, defaut=True):
    """Un booléen EXPLICITE, ou le défaut — jamais une valeur devinée.

    Absent du corps ⇒ le comportement d'aujourd'hui (D12). Les formes
    textuelles (``"false"``, ``"0"``) arrivent des clients qui postent en
    formulaire : les lire est la seule façon de ne pas transformer un refus
    explicite en acceptation silencieuse.
    """
    if brut is None:
        return defaut
    if isinstance(brut, bool):
        return brut
    if isinstance(brut, str):
        return brut.strip().lower() not in ('false', '0', 'non', '')
    return bool(brut)


@action(detail=True, methods=['post'], url_path='dupliquer',
        permission_classes=[PeutGererCalepinage])
def dupliquer(self, request, pk=None):
    """CALX35 — duplique ce calepinage et rend la COPIE.

    Forme de la réponse : ``contract_samples/calepinage_dupliquer.json``.
    """
    # Import LOCAL : ``views/calepinages.py`` importe déjà tout le viewset,
    # le résoudre au chargement du module ferait un aller-retour inutile.
    from .calepinages import _reference

    calepinage = self.get_object()  # borné société par get_queryset
    corps = request.data if isinstance(request.data, dict) else {}
    avec_variantes = _drapeau(corps.get('avec_variantes'))
    try:
        copie = service_dupliquer(
            calepinage, user=request.user,
            titre=str(corps.get('titre') or ''),
            avec_variantes=avec_variantes)
    except VarianteRefusee as refus:
        return Response({refus.champ or 'detail': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'calepinage': copie.pk,
        'reference': _reference(copie),
        'nom': (copie.titre or '').strip() or str(copie),
        'source': calepinage.pk,
        'avec_variantes': avec_variantes,
        'variantes_copiees': copie.variantes.count(),
        # La copie ne réquisitionne JAMAIS le devis de l'original (CAL14).
        'devis': copie.devis_id,
        'layout_hash': copie.layout_hash or '',
    }, status=status.HTTP_201_CREATED)


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF découvre
# l'action par ``get_extra_actions()`` et reconstruit le mapping depuis
# ``__name__`` (piège CALX7).
CalepinageViewSet.dupliquer = dupliquer
