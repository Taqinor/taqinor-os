"""AOF123 — renumérotation et déplacement de ligne à TOTAL INVARIANT.

**Le cas réel.** Sur remarque du client, la ligne « câbles DC Bâtiment B » a été
déplacée des PRESTATIONS COMMUNES vers la section BÂTIMENT B (elle y est
devenue l'item 16), avec renumérotation complète de 1 à 30. Les sous-totaux de
deux sections changent ; le TOTAL, lui, ne doit PAS bouger d'un centime. Fait à
la main sur 30 lignes, un soir de dépôt, c'est exactement l'opération qui
produit un bordereau à 5 219 280 pendant que sa lettre d'accompagnement dit
5 413 680.

**La garantie.** `deplacer()` et `renumeroter()` recalculent le total AVANT et
APRÈS et lèvent `TotalAltere` si le moindre centime a bougé. Ce n'est pas un
test : c'est une assertion d'exécution. Un réordonnancement ne peut donc pas
changer un montant, même en cas de bug futur dans ce module.

**Arithmétique.** Chaque ligne est arrondie au centime, PUIS les lignes sont
sommées. C'est la convention comptable, et elle a une propriété utile ici : la
somme de valeurs déjà arrondies ne dépend pas de l'ordre des termes, donc le
total est intrinsèquement invariant au réordonnancement.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

CENTIME = Decimal('0.01')


class TotalAltere(AssertionError):
    """Un réordonnancement a changé un montant — refusé, jamais absorbé."""


class LigneIntrouvable(KeyError):
    """La ligne à déplacer n'existe pas dans le bordereau."""


def _d(valeur, defaut=None):
    if valeur is None or valeur == '':
        return defaut
    return valeur if isinstance(valeur, Decimal) else Decimal(str(valeur))


def _cle(ligne):
    return str(ligne.get('cle') or ligne.get('numero') or
               ligne.get('designation') or '')


def montant_ligne(ligne):
    """Total HT d'une ligne, arrondi au centime. `None` si incalculable."""
    quantite = _d(ligne.get('quantite'))
    prix = _d(ligne.get('prix_unitaire'))
    if quantite is None or prix is None:
        return None
    brut = quantite * prix
    remise = _d(ligne.get('remise'), Decimal('0'))
    return (brut - remise).quantize(CENTIME, rounding=ROUND_HALF_UP)


def total_ht(lignes):
    """Somme des lignes calculables — les lignes sans PU ne comptent pas."""
    total = Decimal('0')
    for ligne in lignes or ():
        montant = montant_ligne(ligne)
        if montant is not None:
            total += montant
    return total.quantize(CENTIME, rounding=ROUND_HALF_UP)


def total_tva(lignes, taux_defaut=Decimal('20')):
    """TVA calculée LIGNE À LIGNE (le bordereau mêle 10 % et 20 %)."""
    total = Decimal('0')
    for ligne in lignes or ():
        montant = montant_ligne(ligne)
        if montant is None:
            continue
        taux = _d(ligne.get('taux_tva'), taux_defaut)
        total += (montant * taux / Decimal('100')).quantize(
            CENTIME, rounding=ROUND_HALF_UP)
    return total.quantize(CENTIME, rounding=ROUND_HALF_UP)


def total_ttc(lignes, taux_defaut=Decimal('20')):
    return (total_ht(lignes) + total_tva(lignes, taux_defaut)).quantize(
        CENTIME, rounding=ROUND_HALF_UP)


def sous_totaux(lignes):
    """Sous-total HT par section, dans l'ordre d'apparition des sections."""
    totaux, ordre = {}, []
    for ligne in lignes or ():
        section = str(ligne.get('section') or '')
        if section not in totaux:
            totaux[section] = Decimal('0')
            ordre.append(section)
        montant = montant_ligne(ligne)
        if montant is not None:
            totaux[section] += montant
    return {section: totaux[section].quantize(CENTIME) for section in ordre}


def _empreinte_montants(lignes):
    """Ce qui doit rester STRICTEMENT identique à travers un réordonnancement."""
    return (total_ht(lignes), total_tva(lignes), total_ttc(lignes),
            sorted((_cle(ligne), str(montant_ligne(ligne)))
                   for ligne in lignes or ()))


def _verifier_invariance(avant, apres, operation):
    if _empreinte_montants(avant) != _empreinte_montants(apres):
        raise TotalAltere(
            '%s a modifié un montant : total HT %s → %s, TTC %s → %s — '
            'un réordonnancement ne touche JAMAIS aux montants'
            % (operation, total_ht(avant), total_ht(apres),
               total_ttc(avant), total_ttc(apres)))


def ordre_des_sections(lignes):
    """L'ordre des sections, tel qu'il apparaît dans le bordereau."""
    ordre = []
    for ligne in lignes or ():
        section = str(ligne.get('section') or '')
        if section not in ordre:
            ordre.append(section)
    return tuple(ordre)


def renumeroter(lignes, *, depart=1, sections=None):
    """Renumérote 1..N, contigu et sans trou, en respectant les sections.

    Le total est vérifié avant/après : la renumérotation ne peut pas altérer
    un montant.
    """
    lignes = [dict(ligne) for ligne in lignes or ()]
    ordre = list(sections) if sections else list(ordre_des_sections(lignes))
    rang = {section: index for index, section in enumerate(ordre)}
    ordonnees = sorted(
        enumerate(lignes),
        key=lambda paire: (rang.get(str(paire[1].get('section') or ''),
                                    len(ordre)),
                           paire[1].get('position', paire[0]), paire[0]))
    numerotees = []
    for position, (_, ligne) in enumerate(ordonnees, start=depart):
        nouvelle = dict(ligne)
        nouvelle['numero'] = str(position)
        nouvelle['position'] = position
        numerotees.append(nouvelle)
    _verifier_invariance(lignes, numerotees, 'la renumérotation')
    return tuple(numerotees)


def deplacer(lignes, cle, section_cible, *, position=None):
    """Déplace UNE ligne vers une autre section, puis renumérote tout.

    :param cle: `cle`/`numero`/`designation` de la ligne à déplacer.
    :param position: rang souhaité DANS la section cible (1 = en tête) ;
        `None` place la ligne en fin de section.
    :raises TotalAltere: si le total HT/TTC a bougé (impossible par
        construction — l'assertion protège les évolutions futures).
    """
    lignes = [dict(ligne) for ligne in lignes or ()]
    index = next((i for i, ligne in enumerate(lignes) if _cle(ligne) == str(cle)),
                 None)
    if index is None:
        raise LigneIntrouvable(
            'aucune ligne « %s » dans le bordereau' % cle)

    deplacee = lignes.pop(index)
    deplacee['section'] = section_cible
    cibles = [i for i, ligne in enumerate(lignes)
              if str(ligne.get('section') or '') == str(section_cible)]
    if not cibles:
        insertion = len(lignes)
    elif position is None:
        insertion = cibles[-1] + 1
    else:
        rang = max(1, min(int(position), len(cibles) + 1))
        insertion = cibles[rang - 1] if rang <= len(cibles) else cibles[-1] + 1
    lignes.insert(insertion, deplacee)

    for rang, ligne in enumerate(lignes, start=1):
        ligne['position'] = rang
    renumerotees = renumeroter(lignes)
    _verifier_invariance(lignes, renumerotees, 'le déplacement de ligne')
    return renumerotees


# ------------------------------------------------------------- contrôles
@dataclass(frozen=True)
class Anomalie:
    """Un défaut de forme du bordereau — bloquant ou non."""

    cle: str
    code: str
    motif: str
    bloquant: bool = True

    def vers_dict(self):
        return {'cle': self.cle, 'code': self.code, 'motif': self.motif,
                'bloquant': self.bloquant}


def controler(lignes):
    """Lignes vides, PU nuls, unités incohérentes, numérotation à trous."""
    anomalies = []
    unites_par_designation = {}
    numeros = []

    for ligne in lignes or ():
        cle = _cle(ligne)
        designation = str(ligne.get('designation') or '').strip()
        if not designation:
            anomalies.append(Anomalie(cle, 'designation_vide',
                                      'ligne sans désignation'))
        quantite = _d(ligne.get('quantite'))
        if quantite is None:
            anomalies.append(Anomalie(cle, 'quantite_absente',
                                      'quantité absente : %s' % designation))
        elif quantite <= 0:
            anomalies.append(Anomalie(
                cle, 'quantite_nulle',
                'quantité nulle ou négative : %s' % designation))
        prix = _d(ligne.get('prix_unitaire'))
        if prix is None:
            anomalies.append(Anomalie(
                cle, 'pu_absent',
                'prix unitaire non renseigné : %s' % designation))
        elif prix <= 0:
            anomalies.append(Anomalie(
                cle, 'pu_nul', 'prix unitaire nul : %s' % designation))

        unite = str(ligne.get('unite') or '').strip()
        if designation:
            connue = unites_par_designation.setdefault(designation.lower(),
                                                       unite)
            if unite and connue and unite != connue:
                anomalies.append(Anomalie(
                    cle, 'unite_incoherente',
                    'unité incohérente pour « %s » : %s puis %s'
                    % (designation, connue, unite), bloquant=False))
        numero = str(ligne.get('numero') or '')
        if numero:
            numeros.append(numero)

    anomalies.extend(_controler_numerotation(numeros))
    return tuple(anomalies)


def _controler_numerotation(numeros):
    anomalies = []
    doublons = sorted({n for n in numeros if numeros.count(n) > 1})
    for numero in doublons:
        anomalies.append(Anomalie(numero, 'numero_duplique',
                                  'numéro %s présent plusieurs fois' % numero))
    entiers = sorted(int(n) for n in numeros if n.isdigit())
    if entiers and entiers != list(range(entiers[0], entiers[0] + len(entiers))):
        manquants = sorted(set(range(entiers[0], entiers[-1] + 1))
                           - set(entiers))
        anomalies.append(Anomalie(
            '', 'numerotation_a_trous',
            'numérotation non contiguë, manque : %s'
            % ', '.join(str(m) for m in manquants)))
    return anomalies


def bloquants(anomalies):
    return tuple(a for a in anomalies if a.bloquant)


@dataclass(frozen=True)
class Totaux:
    """Les totaux publiés d'un bordereau — calculés, jamais saisis."""

    sous_total_ht: Decimal
    remise: Decimal
    total_ht: Decimal
    tva: Decimal
    total_ttc: Decimal

    def vers_dict(self):
        return {'sous_total_ht': self.sous_total_ht, 'remise': self.remise,
                'total_ht': self.total_ht, 'tva': self.tva,
                'total_ttc': self.total_ttc}


def totaux(lignes, *, remise_globale=None, taux_defaut=Decimal('20')):
    """La cascade PUBLIÉE : sous-total → remise → total HT → TVA → TTC."""
    sous_total = total_ht(lignes)
    remise = _d(remise_globale, Decimal('0')).quantize(CENTIME)
    net = (sous_total - remise).quantize(CENTIME)
    if remise:
        # La remise globale s'applique au prorata : la TVA suit le net.
        proportion = net / sous_total if sous_total else Decimal('0')
        tva = (total_tva(lignes, taux_defaut) * proportion).quantize(
            CENTIME, rounding=ROUND_HALF_UP)
    else:
        tva = total_tva(lignes, taux_defaut)
    return Totaux(sous_total_ht=sous_total, remise=remise, total_ht=net,
                  tva=tva, total_ttc=(net + tva).quantize(CENTIME))


def numero_de(lignes, cle) -> Optional[str]:
    """Le numéro courant d'une ligne — utile après un déplacement."""
    for ligne in lignes or ():
        if _cle(ligne) == str(cle):
            return str(ligne.get('numero') or '')
    return None


def sections_et_lignes(lignes) -> Tuple[Tuple[str, Tuple[dict, ...]], ...]:
    """Le bordereau regroupé par section, dans l'ordre — pour les rendus."""
    groupes = {}
    for ligne in lignes or ():
        groupes.setdefault(str(ligne.get('section') or ''), []).append(ligne)
    return tuple((section, tuple(groupes[section]))
                 for section in ordre_des_sections(lignes))
