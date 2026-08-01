"""AOF159 — propagation d'un changement de prix aux SIX CIBLES DÉCLARÉES.

Un registre, pas une découverte
===============================
La cascade FRDISI a été PARTIELLE exactement là où personne n'avait la liste
en tête : le montant est descendu dans le bordereau et dans la lettre, mais la
justification d'une annexe est restée à l'ancien prix. Tant que « qui dépend
du prix ? » est une question à laquelle on répond de mémoire, la réponse est
incomplète un jour sur deux.

Ici la liste est un **registre explicite** de six cibles :

    01 bordereau (et son arrêté en lettres) · 02 lettre de soumission
    (chiffres ET lettres) · 03 acte d'engagement · 04 simulation de
    rentabilité · 05 checklist partenaire · 06 mémoire technique

et ``verifier_registre`` **fait échouer** l'ajout au gabarit d'une pièce qui
porte un montant sans être déclarée cible. C'est la seule mécanique qui
survit à l'ajout d'une dixième pièce dans six mois.

Péremption
----------
Tout artefact dont l'empreinte de cascade diverge de la cascade COURANTE est
marqué périmé, et l'état « prêt à déposer » est refusé tant qu'il en reste un.
Un artefact périmé n'est pas « un peu vieux » : c'est un fichier frère qui
attend d'être déposé à la place du bon.

Module PUR : dicts et ``Decimal``, aucun ORM. L'exposition HTTP de
l'historique appartient aux endpoints de la fabrique (AOF154).
"""
from __future__ import annotations

from decimal import Decimal

__all__ = [
    'CIBLES_CASCADE',
    'CibleNonDeclaree',
    'DepotRefuse',
    'codes_cibles',
    'verifier_registre',
    'marquer_perimes',
    'verifier_pret_a_deposer',
    'historique_deltas',
]

#: LE registre. Toute pièce portant un montant doit y figurer.
CIBLES_CASCADE = (
    {'code': '04', 'cle': 'bordereau',
     'libelle': 'Bordereau des prix et son arrêté en lettres'},
    {'code': '01', 'cle': 'lettre_soumission',
     'libelle': 'Lettre de soumission (chiffres et lettres)'},
    {'code': '03', 'cle': 'acte_engagement',
     'libelle': "Acte d'engagement"},
    {'code': '05', 'cle': 'simulation',
     'libelle': 'Simulation de rentabilité 25 ans'},
    {'code': '00', 'cle': 'checklist',
     'libelle': 'Checklist partenaire'},
    {'code': '02', 'cle': 'memoire',
     'libelle': 'Mémoire technique'},
)


class CibleNonDeclaree(Exception):
    """Levée quand une pièce porte un montant sans être déclarée cible."""


class DepotRefuse(Exception):
    """Levée quand un artefact périmé interdit le passage à « prêt »."""


def codes_cibles():
    return {cible['code'] for cible in CIBLES_CASCADE}


def verifier_registre(pieces):
    """Refuse toute pièce ``porte_montant`` absente du registre.

    ``pieces`` : ``[{'code', 'libelle', 'porte_montant'}]`` — les pièces du
    gabarit de pack (AOF116). Ajouter une pièce chiffrée au gabarit sans la
    déclarer ici fait ÉCHOUER cette vérification, donc le test qui l'appelle :
    c'est le mécanisme qui empêche la liste de vieillir en silence.
    """
    declarees = codes_cibles()
    manquantes = [
        {'code': piece.get('code'), 'libelle': piece.get('libelle')}
        for piece in (pieces or ())
        if piece.get('porte_montant') and piece.get('code') not in declarees
    ]
    if manquantes:
        raise CibleNonDeclaree(
            "Pièces portant un montant sans être déclarées cibles de la "
            "cascade : {}. Les ajouter à CIBLES_CASCADE — sinon un changement "
            "de prix les laissera en arrière, exactement comme la cascade "
            "partielle du dossier réel.".format(
                ', '.join('{} ({})'.format(m['code'], m['libelle'])
                          for m in manquantes)))
    return True


def marquer_perimes(artefacts, empreinte_cascade):
    """Marque périmé tout artefact d'empreinte divergente. Liste NEUVE.

    ``artefacts`` : ``[{'code', 'empreinte_cascade', 'perime'}]``.
    """
    resultat = []
    for artefact in artefacts or ():
        entree = dict(artefact)
        entree['perime'] = (
            str(entree.get('empreinte_cascade') or '')
            != str(empreinte_cascade or ''))
        resultat.append(entree)
    return resultat


def verifier_pret_a_deposer(artefacts, empreinte_cascade):
    """Porte : refuse « prêt à déposer » tant qu'une cible est périmée.

    Vérifie AUSSI que les six cibles sont présentes : une cible absente est
    pire qu'une cible périmée, puisqu'elle ne déclenche aucun signal.
    """
    marques = marquer_perimes(artefacts, empreinte_cascade)
    presents = {str(a.get('code')) for a in marques}
    absentes = [c for c in CIBLES_CASCADE if c['code'] not in presents]
    perimes = [a for a in marques if a['perime']]
    if absentes or perimes:
        details = []
        if perimes:
            details.append('périmées : ' + ', '.join(
                sorted(str(a.get('code')) for a in perimes)))
        if absentes:
            details.append('absentes : ' + ', '.join(
                c['code'] for c in absentes))
        raise DepotRefuse(
            "Dépôt refusé — cibles de la cascade non à jour ({}). Un artefact "
            "périmé est un fichier frère qui attend d'être déposé à la place "
            "du bon.".format(' ; '.join(details)))
    return marques


def historique_deltas(versions):
    """Deltas entre versions successives de la cascade — total ET par ligne.

    ``versions`` : ``[{'version', 'date', 'motif', 'total_ttc',
    'lignes': {numero: total_ht}}]``, dans l'ordre chronologique. Renvoie une
    liste de transitions ``v(n) → v(n+1)``. Objectif : justifier un mouvement
    de prix sans reconstituer de mémoire.
    """
    versions = list(versions or ())
    transitions = []
    for precedente, suivante in zip(versions, versions[1:]):
        avant = Decimal(str(precedente.get('total_ttc') or 0))
        apres = Decimal(str(suivante.get('total_ttc') or 0))
        lignes_avant = precedente.get('lignes') or {}
        lignes_apres = suivante.get('lignes') or {}
        deltas = []
        for numero in sorted(set(lignes_avant) | set(lignes_apres),
                             key=lambda n: str(n)):
            ancien = Decimal(str(lignes_avant.get(numero, 0)))
            nouveau = Decimal(str(lignes_apres.get(numero, 0)))
            if ancien != nouveau:
                deltas.append({'numero': numero, 'avant': ancien,
                               'apres': nouveau, 'delta': nouveau - ancien})
        deltas.sort(key=lambda d: abs(d['delta']), reverse=True)
        transitions.append({
            'de': precedente.get('version'),
            'vers': suivante.get('version'),
            'date': suivante.get('date'),
            'motif': suivante.get('motif', ''),
            'total_avant': avant,
            'total_apres': apres,
            'delta_total': apres - avant,
            'lignes': deltas,
        })
    return transitions
