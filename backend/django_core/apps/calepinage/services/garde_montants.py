"""ACAL231 - UNE garde « aucun montant » a frontieres de mot.

Le constat
==========
Trois gardes cohabitaient, par SOUS-CHAINE, avec trois listes qui divergeaient
(``planche.MOTS_D_ARGENT_POSE``, ``export_tableur.MOTS_D_ARGENT``,
``sld.MOTS_D_ARGENT``) : « Hammadi » et « El Madani » contiennent « mad »,
« Remise » est un nom de pan, « remise aux normes » un motif de derogation -
et un plan de pose, un classeur ou un rapport d'etude sortait en 500 ou en
refus pour un NOM. Seule la garde du schema unifilaire (frontieres de mot)
etait sans faux positif.

La regle
========
* UNE liste (``MOTS_D_ARGENT``, celle du schema unifilaire etendue de
  ``achat``, ``tarif``, ``cout``, ``dh ht``, ``prix_achat``) et UNE regex a
  frontieres de mot : ``\bmad\b`` trouve « 1 200 MAD », jamais « Hammadi » ;
* la garde ne porte JAMAIS sur un texte SAISI (titre du calepinage, nom de
  client, libelle ou repere de pan, motif de derogation, specification d'un
  organe ajoute) : seulement sur les en-tetes de colonnes et sur les textes
  qui viennent du catalogue ou du moteur (designations, references, fiches
  produit). Ce que l'appelant lui passe est son choix, et il le dit ;
* la garde PAR CLE (``export_projet._cle_de_montant``, ``note_calcul
  ._cle_interdite``, ``rapport.verifier_etancheite``) est INCHANGEE : elle ne
  lit pas du texte, elle lit des noms de cles.
"""
from __future__ import annotations

import re

__all__ = ['MOTS_D_ARGENT', 'mots_d_argent', 'premier_mot_d_argent']

#: Les mots d'argent refuses. Un schema, un plan de pose et un classeur
#: partent au bureau de controle, au chantier ou au bureau d'etudes : aucun
#: montant n'y a sa place (D5, D-CALX 5).
MOTS_D_ARGENT = ('prix', 'prix_achat', 'marge', 'montant', 'mad', 'tva',
                 'remise', 'achat', 'tarif', 'cout', 'coût', 'dh ht',
                 'facture')

_MOT_D_ARGENT_RE = re.compile(
    r'\b(?:%s)\b' % '|'.join(re.escape(mot) for mot in MOTS_D_ARGENT),
    re.IGNORECASE)


def mots_d_argent(texte):
    """Les mots d'argent TROUVES dans ``texte`` (minuscules, tries, sans doublon)."""
    return sorted({m.group(0).lower()
                   for m in _MOT_D_ARGENT_RE.finditer(str(texte or ''))})


def premier_mot_d_argent(texte):
    """Le premier mot d'argent de ``texte`` tel qu'ecrit, ou ``None``."""
    trouve = _MOT_D_ARGENT_RE.search(str(texte or ''))
    return trouve.group(0) if trouve else None
