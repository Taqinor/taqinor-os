"""AOF122 — alimenter le bordereau depuis les variantes RETENUES.

Trois propriétés, et elles sont toutes les trois des garde-fous :

1. **Le report ne touche QUE les lignes de calepinage.** Une ligne manuelle
   (un poste que l'acheteur n'a pas cadré, une prestation forfaitaire) et une
   ligne du cadre acheteur (verrouillée, AOF121) sont laissées INTACTES. Un
   report qui écraserait une quantité imposée par la consultation ferait
   écarter l'offre.
2. **Rejouer le report est idempotent.** Il peut donc être déclenché à chaque
   ouverture du bordereau sans risque : c'est ce qui permet de le rendre
   automatique plutôt que de compter sur un clic humain.
3. **L'invariant « quantités du bordereau = engagements des planches » est
   VÉRIFIABLE EN MACHINE.** Sur le dossier réel : 152 + 120 + 288 = 560
   modules. C'est exactement ce que personne ne peut recontrôler à la main sur
   30 lignes et 4 sections un soir de dépôt.

Le module est PUR : il reçoit des lignes sous forme de mappings (la couche
Django les construit depuis `LigneBordereau`) et retourne de nouvelles lignes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Tuple

SOURCE_CALEPINAGE = 'calepinage'
SOURCE_MANUELLE = 'manuelle'
SOURCE_CATALOGUE = 'catalogue'
SOURCE_ACHETEUR = 'acheteur'

#: Grandeurs qu'une ligne de calepinage peut porter.
GRANDEUR_MODULES = 'modules'
GRANDEUR_KWC = 'kwc'
GRANDEURS = (GRANDEUR_MODULES, GRANDEUR_KWC)


class LigneNonReportable(ValueError):
    """La ligne déclare un calepinage impossible à servir."""


@dataclass(frozen=True)
class Ecart:
    """Un écart entre ce que le bordereau engage et ce que la planche montre."""

    batiment: str
    grandeur: str
    bordereau: Decimal
    planche: Decimal
    motif: str

    @property
    def delta(self):
        return self.bordereau - self.planche

    def vers_dict(self):
        return {'batiment': self.batiment, 'grandeur': self.grandeur,
                'bordereau': str(self.bordereau), 'planche': str(self.planche),
                'delta': str(self.delta), 'motif': self.motif}


@dataclass(frozen=True)
class Report:
    """Le résultat d'un report : les lignes, et ce qui a bougé."""

    lignes: Tuple[dict, ...] = field(default_factory=tuple)
    reportees: Tuple[str, ...] = field(default_factory=tuple)
    inchangees: Tuple[str, ...] = field(default_factory=tuple)
    ignorees: Tuple[str, ...] = field(default_factory=tuple)
    non_servies: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def a_change(self):
        return bool(self.reportees)


def _cle(ligne):
    return str(ligne.get('numero') or ligne.get('cle') or
               ligne.get('designation') or '')


def _quantite(valeur):
    if valeur is None:
        return None
    return valeur if isinstance(valeur, Decimal) else Decimal(str(valeur))


def _valeur_de_variante(resultat, grandeur):
    if grandeur == GRANDEUR_MODULES:
        return Decimal(str(resultat['compte_retenu']))
    if grandeur == GRANDEUR_KWC:
        return Decimal(str(resultat['kwc']))
    raise LigneNonReportable(
        'grandeur inconnue : %r (attendues : %s)'
        % (grandeur, ', '.join(GRANDEURS)))


def reporter(lignes, resultats):
    """Reporte les quantités des variantes retenues dans le bordereau.

    :param lignes: mappings de lignes de bordereau. Une ligne de calepinage
        porte `quantite_source='calepinage'`, `batiment` et, optionnellement,
        `grandeur` (défaut : `modules`).
    :param resultats: résultats de calepinage VALIDÉS (contrat AOF112),
        sous forme de mappings, indexés ou non par bâtiment.
    :returns: `Report`.
    """
    par_batiment = _indexer(resultats)
    sorties, reportees, inchangees, ignorees, servis = [], [], [], [], set()

    for ligne in lignes or ():
        cle = _cle(ligne)
        source = ligne.get('quantite_source', SOURCE_MANUELLE)
        if source != SOURCE_CALEPINAGE or ligne.get('verrouillee'):
            sorties.append(dict(ligne))
            ignorees.append(cle)
            continue

        batiment = str(ligne.get('batiment') or '')
        resultat = par_batiment.get(batiment)
        if resultat is None:
            sorties.append(dict(ligne))
            ignorees.append(cle)
            continue

        grandeur = ligne.get('grandeur') or GRANDEUR_MODULES
        attendue = _valeur_de_variante(resultat, grandeur)
        servis.add(batiment)
        nouvelle = dict(ligne)
        nouvelle['quantite'] = attendue
        nouvelle['variante_hash'] = resultat.get('hash_entree', '')
        nouvelle['version_moteur'] = resultat.get('version_moteur', '')
        if _quantite(ligne.get('quantite')) == attendue and \
                ligne.get('variante_hash') == nouvelle['variante_hash']:
            inchangees.append(cle)
        else:
            reportees.append(cle)
        sorties.append(nouvelle)

    return Report(lignes=tuple(sorties), reportees=tuple(reportees),
                  inchangees=tuple(inchangees), ignorees=tuple(ignorees),
                  non_servies=tuple(sorted(set(par_batiment) - servis)))


def _indexer(resultats):
    if hasattr(resultats, 'items'):
        return {str(cle): val for cle, val in resultats.items()}
    return {str(r['batiment']): r for r in resultats or ()}


def a_rafraichir(lignes, resultats):
    """Les lignes dont la variante a bougé — le bordereau est à rafraîchir.

    C'est le pendant « bordereau » de la péremption d'artefact d'AOF111 : un
    calepinage rejoué ne réécrit pas le bordereau dans le dos de l'utilisateur,
    il le SIGNALE.
    """
    par_batiment = _indexer(resultats)
    a_revoir = []
    for ligne in lignes or ():
        if ligne.get('quantite_source') != SOURCE_CALEPINAGE:
            continue
        resultat = par_batiment.get(str(ligne.get('batiment') or ''))
        if resultat is None:
            continue
        grandeur = ligne.get('grandeur') or GRANDEUR_MODULES
        if _quantite(ligne.get('quantite')) != \
                _valeur_de_variante(resultat, grandeur) or \
                ligne.get('variante_hash') != resultat.get('hash_entree', ''):
            a_revoir.append(_cle(ligne))
    return tuple(a_revoir)


def quantites_par_batiment(lignes, *, grandeur=GRANDEUR_MODULES):
    """Ce que le BORDEREAU engage, par bâtiment — la somme qui fait foi."""
    totaux = {}
    for ligne in lignes or ():
        if (ligne.get('grandeur') or GRANDEUR_MODULES) != grandeur:
            continue
        if ligne.get('quantite_source') not in (SOURCE_CALEPINAGE,
                                                SOURCE_ACHETEUR):
            continue
        quantite = _quantite(ligne.get('quantite'))
        if quantite is None:
            continue
        batiment = str(ligne.get('batiment') or '')
        totaux[batiment] = totaux.get(batiment, Decimal('0')) + quantite
    return totaux


def controler_invariant(lignes, engagements, *, grandeur=GRANDEUR_MODULES):
    """« Quantités du bordereau = engagements portés sur les planches ».

    :param engagements: mapping `bâtiment → quantité engagée` (ou itérable de
        mappings `{batiment, modules}`) — ce que les planches montrent.
    :returns: tuple d'`Ecart`, vide quand l'invariant tient.
    """
    attendus = _engagements(engagements, grandeur)
    constates = quantites_par_batiment(lignes, grandeur=grandeur)
    ecarts = []
    for batiment in sorted(set(attendus) | set(constates)):
        planche = attendus.get(batiment)
        bordereau = constates.get(batiment)
        if planche is None:
            ecarts.append(Ecart(
                batiment, grandeur, bordereau, Decimal('0'),
                'le bordereau engage une quantité sur un bâtiment sans planche'))
        elif bordereau is None:
            ecarts.append(Ecart(
                batiment, grandeur, Decimal('0'), planche,
                'la planche engage une quantité absente du bordereau'))
        elif bordereau != planche:
            ecarts.append(Ecart(
                batiment, grandeur, bordereau, planche,
                'quantité du bordereau différente de l\'engagement de la '
                'planche'))
    return tuple(ecarts)


def _engagements(engagements, grandeur):
    if hasattr(engagements, 'items'):
        return {str(cle): _quantite(val)
                for cle, val in engagements.items() if val is not None}
    attendus = {}
    for engagement in engagements or ():
        valeur = engagement.get(grandeur, engagement.get('modules'))
        if valeur is None:
            continue
        attendus[str(engagement.get('batiment') or '')] = _quantite(valeur)
    return attendus


def total_engage(lignes, *, grandeur=GRANDEUR_MODULES):
    """Le total tous bâtiments — 152 + 120 + 288 = 560 sur le dossier réel."""
    totaux = quantites_par_batiment(lignes, grandeur=grandeur)
    return sum(totaux.values(), Decimal('0'))
