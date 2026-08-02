"""AOF128 — rendu PDF du bordereau, STRICTEMENT concordant avec le classeur.

**Pourquoi la concordance se prouve au lieu de se supposer.** Le PDF est ce que
la commission lit ; le XLSX est ce que l'acheteur recalcule. Deux chemins de
rendu, deux occasions de diverger — et le dossier réel a produit exactement
cela : un bordereau frère resté à 5 219 280 quand le principal disait
5 413 680. Les deux sorties partent donc des MÊMES lignes et des MÊMES
fonctions de total (`ordonnancement.py`), et `comparer()` vérifie ligne à
ligne, AU CENTIME, que le classeur et le PDF disent la même chose.

**Aucun rendu ici.** Le module produit le CONTEXTE de gabarit et le nom du
template. L'appel `core.pdf.render_pdf(template=NOM_GABARIT, context=…)`
(ARC11) appartient à la couche Django : un seul point d'appel PDF pour tout le
dépôt, jamais un import direct de WeasyPrint.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

from core.formats_fr import formater_date

from ..clauses import CLAUSE_RESERVE_QUANTITES
from ..montants import arrete, en_chiffres, en_lettres
from ..ordonnancement import (montant_ligne, sections_et_lignes, sous_totaux,
                              totaux)
from ..styles import contexte_style

NOM_GABARIT = 'ao/bordereau.html'
TITRE_PIECE = 'Bordereau des prix — détail estimatif'


def _d(valeur):
    if valeur is None or valeur == '':
        return None
    return valeur if isinstance(valeur, Decimal) else Decimal(str(valeur))


def _ligne_rendue(ligne, devise):
    prix = _d(ligne.get('prix_unitaire'))
    total = montant_ligne(ligne)
    quantite = _d(ligne.get('quantite'))
    return {
        'cle': str(ligne.get('cle') or ligne.get('numero') or ''),
        'numero': str(ligne.get('numero') or ''),
        'designation': str(ligne.get('designation') or ''),
        'unite': str(ligne.get('unite') or ''),
        'quantite': quantite,
        'quantite_texte': ('' if quantite is None
                           else en_chiffres(quantite, devise='').strip()),
        'prix_unitaire': prix,
        'prix_unitaire_texte': en_chiffres(prix, devise=devise),
        'prix_unitaire_lettres': en_lettres(prix),
        'total': total,
        'total_texte': en_chiffres(total, devise=devise),
    }


def contexte_gabarit(lignes, contexte=None, *, texte_clause=None,
                     taux_tva=Decimal('20'), devise='DH'):
    """Le contexte du gabarit `ao/bordereau.html`.

    Toutes les valeurs y sont DÉJÀ calculées et formatées : le gabarit ne
    contient aucun chiffre littéral et ne fait aucune arithmétique.
    """
    contexte = contexte or {}
    lignes = list(lignes or ())
    calcules = totaux(lignes, taux_defaut=taux_tva)
    partiels = sous_totaux(lignes)

    sections = []
    for section, lignes_section in sections_et_lignes(lignes):
        sections.append({
            'libelle': section,
            'lignes': [_ligne_rendue(ligne, devise)
                       for ligne in lignes_section],
            'sous_total': partiels.get(section),
            'sous_total_texte': en_chiffres(partiels.get(section),
                                            devise=devise)})

    donnees = {
        'piece_titre': TITRE_PIECE,
        'contexte': contexte,
        'sections': sections,
        'totaux': calcules,
        'sous_total_ht_texte': en_chiffres(calcules.sous_total_ht,
                                           devise=devise),
        'remise_texte': en_chiffres(calcules.remise, devise=devise),
        'total_ht_texte': en_chiffres(calcules.total_ht, devise=devise),
        'taux_tva': taux_tva,
        'tva_texte': en_chiffres(calcules.tva, devise=devise),
        'total_ttc_texte': en_chiffres(calcules.total_ttc, devise=devise),
        'arrete': arrete(calcules.total_ttc),
        'clause_reserve': texte_clause or CLAUSE_RESERVE_QUANTITES,
        'avec_remise': bool(calcules.remise),
        # La date est formatée ICI, jamais par le gabarit : le rendu d'un
        # gabarit dépend de la locale active, et une pièce d'un marché
        # marocain ne doit pas s'imprimer « Aug. 1, 2026 » parce que le
        # processus qui l'a produite tournait sans locale française.
        'date_offre_texte': formater_date(
            (contexte.get('dates') or {}).get('offre')),
    }
    donnees.update(contexte_style())
    return donnees


def valeurs_de_controle(donnees):
    """Les montants PORTÉS par le PDF — la contrepartie de ceux du classeur."""
    lignes = {}
    for section in donnees['sections']:
        for ligne in section['lignes']:
            lignes[ligne['cle']] = ligne['total']
    return {
        'total_ht': donnees['totaux'].total_ht,
        'tva': donnees['totaux'].tva,
        'total_ttc': donnees['totaux'].total_ttc,
        'sous_totaux': {section['libelle']: section['sous_total']
                        for section in donnees['sections']},
        'lignes': lignes,
    }


@dataclass(frozen=True)
class Divergence:
    """Un montant sur lequel le PDF et le classeur ne s'accordent pas."""

    repere: str
    pdf: Optional[Decimal]
    xlsx: Optional[Decimal]

    @property
    def motif(self):
        return ('%s : le PDF porte %s, le classeur %s'
                % (self.repere, self.pdf, self.xlsx))

    def vers_dict(self):
        return {'repere': self.repere,
                'pdf': None if self.pdf is None else str(self.pdf),
                'xlsx': None if self.xlsx is None else str(self.xlsx),
                'motif': self.motif}


def comparer(valeurs_pdf, valeurs_xlsx) -> Tuple[Divergence, ...]:
    """Compare les deux sorties AU CENTIME. Vide = concordantes."""
    divergences = []
    for cle in ('total_ht', 'tva', 'total_ttc'):
        if valeurs_pdf.get(cle) != valeurs_xlsx.get(cle):
            divergences.append(Divergence(cle, valeurs_pdf.get(cle),
                                          valeurs_xlsx.get(cle)))
    lignes_pdf = valeurs_pdf.get('lignes') or {}
    lignes_xlsx = valeurs_xlsx.get('lignes') or {}
    for cle in sorted(set(lignes_pdf) | set(lignes_xlsx)):
        if lignes_pdf.get(cle) != lignes_xlsx.get(cle):
            divergences.append(Divergence('ligne %s' % cle,
                                          lignes_pdf.get(cle),
                                          lignes_xlsx.get(cle)))
    return tuple(divergences)


class ConcordanceRompue(AssertionError):
    """Le PDF et le classeur ne disent pas la même chose — dépôt refusé."""


def exiger_concordance(valeurs_pdf, valeurs_xlsx):
    """Porte : lève si les deux artefacts d'un même bordereau divergent."""
    divergences = comparer(valeurs_pdf, valeurs_xlsx)
    if divergences:
        raise ConcordanceRompue(' ; '.join(d.motif for d in divergences))
    return True
