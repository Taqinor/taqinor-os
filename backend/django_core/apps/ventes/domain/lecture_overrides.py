"""Lecture PURE du registre d'overrides d'un devis (feuille, aucun import d'app).

ENF20 — extrait de ``overrides`` : ``utils.options.scenario_declare`` lit le
registre sans tirer ``overrides`` (qui lit le catalogue, le moteur et le CRM).
``overrides`` ré-exporte ces noms : l'objet est le MÊME.
"""
#: Les ORIGINES admises d'un override — jamais une quatrième inventée sans que
#: le contrat PACT10 ne soit d'abord mis à jour.
ORIGINE_MANUEL = 'manuel'
ORIGINE_IMPORT = 'import'
ORIGINE_API = 'api'
ORIGINES = (ORIGINE_MANUEL, ORIGINE_IMPORT, ORIGINE_API)

def registre_du_devis(devis):
    """Le registre RANGÉ sur ce devis, toujours un dict (jamais ``None``).

    Lu par ``getattr`` : la colonne ``Devis.overrides`` n'existe qu'à partir de
    QJR58, ce module fonctionne donc AVANT elle comme APRÈS. Rendu par COPIE :
    un appelant qui le modifie ne touche jamais l'instance.
    """
    brut = getattr(devis, 'overrides', None)
    return dict(brut) if isinstance(brut, dict) else {}


#: Alias interne historique — ce module l'utilise sous ce nom court.
_registre = registre_du_devis


def effectif(devis, chemin, auto):
    """``(valeur, source)`` — LA valeur qui vaut aujourd'hui pour ce chemin.

    ``auto`` est ce que le moteur dériverait MAINTENANT (l'appelant le lui
    fournit : ce module ne calcule rien). Un override posé prime, et ``source``
    NOMME sa provenance (``manuel`` / ``import`` / ``api``) ; sinon la valeur
    automatique, ``source='auto'``.

    RIEN N'EST STOCKÉ ICI : un devis dont le catalogue a changé depuis la pose
    de l'override voit son ``auto`` bouger sans que ``manuel`` ne change, et un
    chemin RESTÉ automatique reflète toujours l'état actuel — jamais une valeur
    figée au moment d'une lecture passée.
    """
    entree = _registre(devis).get(chemin)
    if not isinstance(entree, dict) or 'valeur' not in entree:
        return auto, 'auto'
    origine = entree.get('origine')
    return entree['valeur'], (origine if origine in ORIGINES
                              else ORIGINE_MANUEL)
