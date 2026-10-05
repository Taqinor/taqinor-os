"""CALX314 — la PROVENANCE, posée sur TOUS les exports du module.

Le constat
==========
Seul le CSV de simulation portait un bloc de provenance
(``services/export_csv._lignes_de_provenance`` : base de rayonnement, fenêtre
d'années, version du moteur, perte passée et son détail — CAL144/CALX313) ; le
classeur XLSX écrivait trois feuilles nues (``services/export_tableur.py``) et
le DXF des calques purement géométriques (``services/export_dxf.py``). Un
fichier qui circule sans sa provenance devient un chiffre orphelin le
lendemain. Parité : PVsyst (le document de sortie porte les paramètres de la
simulation qui l'a produit).

UNE fonction, TROIS blocs
=========================
``lignes_de_provenance(calepinage)`` compose les lignes ``(libellé, valeur)``,
et elle seule : la feuille ``Provenance`` en tête du classeur XLSX, le bloc de
texte du calque DXF ``PROVENANCE`` et le bloc ``provenance`` de l'export JSON
(CALX312) en sont trois MISES EN FORME, jamais trois compositions.

Elle REPREND la composition du CSV — elle appelle
``export_csv._lignes_de_provenance`` sur le même document que le CSV
(``export_csv.document_exportable`` : production et pertes du résultat SERVI,
version du moteur, et les deux empreintes qui permettent de rejouer le fichier :
celle du document de pose et celle des entrées de la simulation — ACAL217).

Une valeur ABSENTE n'est jamais une chaîne vide : une empreinte absente écrit
« non calculée », toute autre grandeur absente « non publiée ». Aucun montant
(D5) : aucune de ces lignes ne lit un prix.
"""
from __future__ import annotations

from .export_csv import (
    LIBELLE_EMPREINTE_LAYOUT, LIBELLE_EMPREINTE_SIMULATION, NON_CALCULEE,
    NON_PUBLIEE, _lignes_de_provenance, document_exportable,
)

__all__ = [
    'NON_CALCULEE', 'NON_PUBLIEE', 'TITRE_FEUILLE', 'ENTETES',
    'LIBELLE_EMPREINTE_LAYOUT', 'LIBELLE_EMPREINTE_SIMULATION',
    'lignes_de_provenance', 'texte_de_ligne', 'lignes_json',
]

#: La feuille du classeur XLSX, et ses deux colonnes.
TITRE_FEUILLE = 'Provenance'
ENTETES = ('Grandeur', 'Valeur')


def _texte(valeur):
    return '' if valeur is None else str(valeur).strip()


def lignes_de_provenance(calepinage):
    """Les lignes ``(libellé, valeur)`` de la provenance — LA composition.

    ACAL217 — c'est ``export_csv._lignes_de_provenance`` sur le document
    d'export UNIQUE (``export_csv.document_exportable``, résultat SERVI) : les
    deux empreintes (document de pose, entrées de la simulation) y entrent
    déjà, rien n'est rajouté ici. Aucune valeur n'est une chaîne vide.
    """
    lignes = []
    for ligne in _lignes_de_provenance(
            document_exportable(calepinage, avec_points=False)):
        if not ligne:
            continue  # la ligne blanche qui sépare l'en-tête du tableau CSV
        libelle, valeur = ligne[0], ligne[1] if len(ligne) > 1 else ''
        lignes.append((str(libelle), _texte(valeur) or NON_PUBLIEE))
    return lignes


def texte_de_ligne(ligne):
    """« libellé : valeur » — la graphie d'une ligne dans un bloc de texte."""
    return '%s : %s' % (ligne[0], ligne[1])


def lignes_json(lignes):
    """``[{libelle, valeur}]`` — la forme du bloc ``provenance`` en JSON."""
    return [{'libelle': libelle, 'valeur': valeur}
            for libelle, valeur in lignes]
