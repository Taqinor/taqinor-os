"""Clés posées par les M0 ACAL (PACT10) AVANT que leur producteur ne les serve.

Les contrats ACAL1-21 sont arrivés SEULS sur main (le contrat d'abord) : leurs
échantillons portent déjà des clés que le serveur d'aujourd'hui n'émet pas.
Les tests qui comparent ce que le serveur SERT à l'échantillon retirent ces
clés-là — et SEULEMENT elles — via :func:`sans`, chacune nommant la tâche qui
la livre. La tâche nommée retire son entrée dans le même commit que son
producteur : la comparaison d'égalité rougit d'elle-même dès qu'une clé « en
attente » est réellement servie (la valeur servie ne correspond plus à
l'échantillon amputé), ou via :func:`affirmer_non_servies`.

Syntaxe des chemins : ``'a.b.c'`` (clés de dictionnaires), ``'a[].b'``
(chaque élément d'une liste). Un chemin absent est ignoré.
"""
from __future__ import annotations

import copy


def _retirer(noeud, segments):
    if not segments or noeud is None:
        return
    tete, reste = segments[0], segments[1:]
    if tete.endswith('[]'):
        liste = noeud.get(tete[:-2]) if isinstance(noeud, dict) else None
        if isinstance(liste, list) and reste:
            for element in liste:
                _retirer(element, reste)
        return
    if not isinstance(noeud, dict):
        return
    if not reste:
        noeud.pop(tete, None)
        return
    _retirer(noeud.get(tete), reste)


def sans(valeur, chemins):
    """Copie profonde de ``valeur`` privée des clés désignées par ``chemins``.

    ``chemins`` : itérable de chemins, ou dictionnaire ``chemin -> tâche``.
    """
    copie = copy.deepcopy(valeur)
    for chemin in chemins:
        _retirer(copie, chemin.split('.'))
    return copie


def _present(noeud, segments):
    if not segments or noeud is None:
        return False
    tete, reste = segments[0], segments[1:]
    if tete.endswith('[]'):
        liste = noeud.get(tete[:-2]) if isinstance(noeud, dict) else None
        return isinstance(liste, list) and any(
            _present(element, reste) for element in liste)
    if not isinstance(noeud, dict) or tete not in noeud:
        return False
    return True if not reste else _present(noeud[tete], reste)


def affirmer_non_servies(test, servi, en_attente):
    """Rougit dès qu'une clé « en attente » est servie : retirer son entrée."""
    servies = sorted(chemin for chemin in en_attente
                     if _present(servi, chemin.split('.')))
    test.assertEqual(
        servies, [],
        f'Le serveur sert désormais {servies} : retirer ces clés de la table '
        'des clés en attente (tâche livrée : '
        f'{sorted({en_attente[c] for c in servies})}).')


#: ``calepinage_detail.json`` (ACAL6, forme_serveur ``partielle``) : la
#: première moitié back de chaque clé la sert, retire son entrée et remet
#: ``complete`` quand la table est vide.
EN_ATTENTE_DETAIL = {
    'custom_data': 'ACAL6 moitié back (D09-T33)',
    'permissions.peut_deroger': 'ACAL6 moitié back (D-ACAL-9)',
    'lead.supprime': 'ACAL178',
}

#: Clés du bloc de simulation posées par ACAL8 (M0) — chemins relatifs à
#: un état de ``calepinage_simulation.json`` OU de ``calepinage_resultat.json``
#: (les deux échantillons publient les mêmes blocs).
EN_ATTENTE_SIMULATION = {
    'simulation.meteo_fichier': 'ACAL146',
    'meteo.fichier': 'ACAL146',
}

#: Clés propres à ``calepinage_resultat.json`` posées par ACAL8 (M0), en plus
#: des blocs de simulation ci-dessus.
EN_ATTENTE_RESULTAT = {
    **EN_ATTENTE_SIMULATION,
    'ecart_devis': 'ACAL104',
    'pose.pans[].cle': 'ACAL265',
    'pose.pans[].module_id': 'ACAL264',
    'electrique.affectation_obsolete': 'ACAL265',
}
