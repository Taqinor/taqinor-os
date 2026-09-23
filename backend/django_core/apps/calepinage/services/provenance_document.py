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
``export_csv._lignes_de_provenance`` sur le même document que
``views/export_csv.document_exportable`` (production et pertes STOCKÉES,
version du moteur) — plutôt que d'en écrire une seconde. Elle y AJOUTE les deux
empreintes qui permettent de rejouer le fichier : celle du document de pose
(``layout_hash``) et celle des entrées de la simulation
(``resultat['simulation']['hash_entree']``).

Une valeur ABSENTE n'est jamais une chaîne vide : une empreinte absente écrit
« non calculée », toute autre grandeur absente « non publiée ». Aucun montant
(D5) : aucune de ces lignes ne lit un prix.
"""
from __future__ import annotations

__all__ = [
    'NON_CALCULEE', 'NON_PUBLIEE', 'TITRE_FEUILLE', 'ENTETES',
    'LIBELLE_EMPREINTE_LAYOUT', 'LIBELLE_EMPREINTE_SIMULATION',
    'document_de_provenance', 'lignes_de_provenance', 'texte_de_ligne',
    'lignes_json',
]

NON_CALCULEE = 'non calculée'
NON_PUBLIEE = 'non publiée'

#: La feuille du classeur XLSX, et ses deux colonnes.
TITRE_FEUILLE = 'Provenance'
ENTETES = ('Grandeur', 'Valeur')

LIBELLE_EMPREINTE_LAYOUT = 'Empreinte du calepinage'
LIBELLE_EMPREINTE_SIMULATION = "Empreinte d'entrée de la simulation"


def _dict(valeur):
    return valeur if isinstance(valeur, dict) else {}


def document_de_provenance(calepinage):
    """Le document que le CSV lit pour SA provenance — les mêmes trois clés.

    Miroir de ``views/export_csv.document_exportable`` sur les seules clés que
    la provenance consomme (``production``, ``pertes``, ``version_moteur``) :
    un test affirme que les deux compositions coïncident ligne à ligne.
    """
    resultat = _dict(getattr(calepinage, 'resultat', None))
    return {
        'production': _dict(resultat.get('production')),
        'pertes': resultat.get('pertes') or [],
        'version_moteur': getattr(calepinage, 'version_moteur', '') or None,
    }


def _texte(valeur):
    return '' if valeur is None else str(valeur).strip()


def lignes_de_provenance(calepinage):
    """Les lignes ``(libellé, valeur)`` de la provenance — LA composition.

    Les six premières sont celles du CSV (``export_csv``), dans son ordre ; les
    deux dernières sont les empreintes. Aucune valeur n'est une chaîne vide.
    """
    from .export_csv import _lignes_de_provenance

    lignes = []
    for ligne in _lignes_de_provenance(document_de_provenance(calepinage)):
        if not ligne:
            continue  # la ligne blanche qui sépare l'en-tête du tableau CSV
        libelle, valeur = ligne[0], ligne[1] if len(ligne) > 1 else ''
        lignes.append((str(libelle), _texte(valeur) or NON_PUBLIEE))

    simulation = _dict(_dict(getattr(calepinage, 'resultat', None))
                       .get('simulation'))
    lignes.append((LIBELLE_EMPREINTE_LAYOUT,
                   _texte(getattr(calepinage, 'layout_hash', ''))
                   or NON_CALCULEE))
    lignes.append((LIBELLE_EMPREINTE_SIMULATION,
                   _texte(simulation.get('hash_entree')) or NON_CALCULEE))
    return lignes


def texte_de_ligne(ligne):
    """« libellé : valeur » — la graphie d'une ligne dans un bloc de texte."""
    return '%s : %s' % (ligne[0], ligne[1])


def lignes_json(lignes):
    """``[{libelle, valeur}]`` — la forme du bloc ``provenance`` en JSON."""
    return [{'libelle': libelle, 'valeur': valeur}
            for libelle, valeur in lignes]
