"""CAL179 — l'export CSV / XLSX : modules, chaînes, nomenclature.

Le constat
==========
L'utilitaire tableur PARTAGÉ existe (``apps/records/xlsx.py`` :
``build_workbook``, ``neutralize_rows``, ``coerce_cell``) et il neutralise déjà
l'injection de formules ; AO a son bordereau ; le calepinage ventes n'avait
rien. On ne recode donc NI le classeur, NI la coercition des cellules, NI la
neutralisation — on les appelle.

Trois feuilles, et ce qu'elles disent
=====================================
* **modules** — un module POSÉ par ligne : son pan, sa rangée, sa position
  relevée (est/nord, en mètres) et l'orientation de son pan ;
* **chaînes** — le chaînage publié par le moteur (modules par chaîne, nombre de
  chaînes, reste) et l'affectation module -> chaîne / onduleur / MPPT ;
* **nomenclature** — désignation et QUANTITÉ, rien d'autre.

LA RANGÉE EST UN GROUPEMENT, PAS UNE INVENTION
==============================================
Le document de conception ne stocke pas d'indice de rangée : il stocke les
CENTRES des modules. La colonne « Rangée » est donc obtenue en GROUPANT les
modules d'un pan sur leur ordonnée relevée (au centimètre près) et en les
numérotant du sud vers le nord. C'est une lecture de la donnée stockée, pas une
donnée nouvelle — et si deux modules ne partagent pas la même ordonnée, ils ne
partagent pas la même rangée. Aucun indice n'est deviné.

AUCUN PRIX, JAMAIS
==================
``Produit.prix_achat`` alimente un indicateur de marge réservé au GÉNÉRATEUR :
il ne doit paraître dans AUCUNE sortie. Ici la règle est ARMÉE, pas seulement
respectée : ``verifier_absence_de_prix`` inspecte les en-têtes ET les lignes
produites et refuse l'export si un mot d'argent s'y trouve. Une omission de
filtre est silencieuse ; un refus ne l'est pas.
"""
from __future__ import annotations

__all__ = [
    'FEUILLES', 'MOTS_D_ARGENT', 'ExportRefuse', 'verifier_absence_de_prix',
    'rangees_du_pan', 'table_modules', 'table_chaines', 'table_nomenclature',
    'tables_du_resultat',
    'classeur_octets', 'csv_octets', 'exporter_xlsx', 'exporter_csv',
]

#: Les trois feuilles, dans l'ordre du classeur.
FEUILLES = ('Modules', 'Chaînes', 'Nomenclature')

#: Les mots qui n'ont RIEN à faire dans une sortie technique. La garde porte
#: sur les en-têtes et sur les cellules texte — un prix glissé dans une
#: désignation passerait sinon.
MOTS_D_ARGENT = ('prix', 'achat', 'coût', 'cout', 'marge brute', 'montant',
                 'mad', 'dh ht', 'tarif', 'remise', 'facture')

#: Arrondi de groupement des rangées : le centimètre. Deux modules posés à
#: moins d'un centimètre l'un de l'autre en ordonnée sont sur la même rangée.
PAS_DE_RANGEE_M = 0.01


class ExportRefuse(ValueError):
    """L'export refuse de sortir, en disant ce qui l'en empêche."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def verifier_absence_de_prix(entetes, lignes):
    """Refuse une table qui charrie un mot d'argent (en-tête OU cellule)."""
    suspects = []
    for entete in entetes:
        texte = str(entete).lower()
        suspects += ['en-tête « %s »' % entete
                     for mot in MOTS_D_ARGENT if mot in texte]
    for rang, ligne in enumerate(lignes, start=1):
        for cellule in ligne:
            if not isinstance(cellule, str):
                continue
            texte = cellule.lower()
            suspects += ['ligne %d : « %s »' % (rang, cellule)
                         for mot in MOTS_D_ARGENT if mot in texte]
    if suspects:
        raise ExportRefuse(
            "Export refusé : une sortie technique ne porte aucun prix "
            "(`prix_achat` alimente un indicateur réservé au générateur). "
            "Trouvé — %s." % ' ; '.join(sorted(set(suspects))),
            champ='colonnes')


def rangees_du_pan(modules):
    """``centre -> numéro de rangée`` par GROUPEMENT sur l'ordonnée relevée.

    PUBLIQUE parce qu'elle est la SEULE définition de « rangée » du module :
    le plan de pose (CAL211) l'appelle pour numéroter ses repères. Deux
    définitions de la rangée feraient diverger le plan remis à l'équipe et le
    tableau remis au bureau d'études — la duplication de la donnée est la
    seule source d'incohérence observée le 27/07/2026.
    """
    ordonnees = sorted({round(y / PAS_DE_RANGEE_M) for _x, y in modules})
    rang_par_ordonnee = {valeur: rang
                         for rang, valeur in enumerate(ordonnees, start=1)}
    return {centre: rang_par_ordonnee[round(centre[1] / PAS_DE_RANGEE_M)]
            for centre in modules}


def _affectation_par_pan(resultat):
    """``pan -> [affectations]`` telles que le moteur les publie, dans l'ordre."""
    affectations = (((resultat or {}).get('electrique') or {})
                    .get('affectation') or [])
    par_pan = {}
    for entree in affectations:
        if isinstance(entree, dict):
            par_pan.setdefault(str(entree.get('pan') or ''), []).append(entree)
    return par_pan


def table_modules(geometrie, resultat=None):
    """Un module POSÉ par ligne. Les quantités sont celles de la géométrie."""
    entetes = ['Pan', 'Bâtiment', 'Rangée', 'Module', 'Est (m)', 'Nord (m)',
               'Azimut (°)', 'Inclinaison (°)', 'Chaîne', 'Onduleur', 'MPPT']
    par_pan = _affectation_par_pan(resultat)
    lignes = []
    for pan in geometrie.get('pans') or ():
        rangees = rangees_du_pan(pan['modules'])
        affectations = par_pan.get(pan['repere'], [])
        for rang, centre in enumerate(pan['modules'], start=1):
            affectation = affectations[rang - 1] \
                if rang - 1 < len(affectations) else {}
            lignes.append([
                pan['libelle'] or pan['repere'],
                pan['batiment'] or '',
                rangees[centre],
                rang,
                round(centre[0], 3),
                round(centre[1], 3),
                pan['azimut_deg'],
                pan['pente_deg'],
                affectation.get('chaine'),
                affectation.get('onduleur'),
                affectation.get('mppt'),
            ])
    return entetes, lignes


def table_chaines(resultat):
    """Le chaînage PUBLIÉ par le moteur — aucune chaîne n'est recomposée ici."""
    entetes = ['Grandeur', 'Valeur']
    electrique = (resultat or {}).get('electrique') or {}
    chainage = electrique.get('chainage') or {}
    lignes = [
        ['Modules chaînés', chainage.get('modules')],
        ['Modules par chaîne', chainage.get('modules_par_chaine')],
        ['Nombre de chaînes', chainage.get('chaines')],
        ['Modules hors chaîne', chainage.get('reste')],
    ]
    for onduleur in electrique.get('onduleurs') or []:
        if not isinstance(onduleur, dict):
            continue
        lignes.append(['Onduleur — %s' % (onduleur.get('reference') or ''),
                       onduleur.get('nombre')])
        lignes.append(['Entrées MPPT — %s' % (onduleur.get('reference') or ''),
                       onduleur.get('n_mppt')])
    return entetes, lignes


def table_nomenclature(resultat):
    """Désignation et QUANTITÉ. Pas de prix, pas de total, pas de fournisseur."""
    entetes = ['Désignation', 'Quantité', 'Unité']
    pose = (resultat or {}).get('pose') or {}
    lignes = []
    if pose.get('total_modules') is not None:
        puissance = pose.get('puissance_module_wc')
        designation = ('Module photovoltaïque %s Wc' % puissance) \
            if puissance is not None else 'Module photovoltaïque'
        lignes.append([designation, pose['total_modules'], 'u'])
    for onduleur in ((resultat or {}).get('electrique') or {}) \
            .get('onduleurs') or []:
        if not isinstance(onduleur, dict):
            continue
        lignes.append(['Onduleur %s' % (onduleur.get('reference') or ''),
                       onduleur.get('nombre'), 'u'])
    return entetes, lignes


def tables_du_resultat(geometrie, resultat=None):
    """``[(titre, entetes, lignes)]`` pour les trois feuilles, PRIX VÉRIFIÉS."""
    tables = [
        (FEUILLES[0],) + table_modules(geometrie, resultat),
        (FEUILLES[1],) + table_chaines(resultat),
        (FEUILLES[2],) + table_nomenclature(resultat),
    ]
    for _titre, entetes, lignes in tables:
        verifier_absence_de_prix(entetes, lignes)
    return tables


# ── Les sorties, par l'utilitaire PARTAGÉ ───────────────────────────────────

def classeur_octets(tables):
    """Les trois feuilles dans UN classeur .xlsx, en octets.

    ``apps.records.xlsx.build_workbook`` construit la PREMIÈRE feuille (en-têtes
    en gras, largeurs lisibles) ; les suivantes sont ajoutées au même classeur
    avec la MÊME coercition (``coerce_cell``) et la MÊME neutralisation
    d'injection de formules (``neutralize_rows``) — l'utilitaire partagé ne sait
    pas encore faire plusieurs feuilles, mais on n'en recode aucune règle.
    """
    import io

    from openpyxl.styles import Font

    from apps.records.xlsx import (
        build_workbook, coerce_cell, neutralize_rows,
    )

    titre, entetes, lignes = tables[0]
    classeur = build_workbook(entetes, neutralize_rows(lignes),
                              sheet_title=titre)
    for titre, entetes, lignes in tables[1:]:
        feuille = classeur.create_sheet(title=titre)
        feuille.append([coerce_cell(entete) for entete in entetes])
        for cellule in feuille[1]:
            # ``Font(bold=True)`` et non ``font.copy(...)`` : la seconde est
            # dépréciée par openpyxl et un avertissement suffirait à rougir une
            # exécution en ``-W error``.
            cellule.font = Font(bold=True)
        for ligne in neutralize_rows(lignes):
            feuille.append([coerce_cell(valeur) for valeur in ligne])
    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()


def csv_octets(tables, feuille=None):
    """La variante CSV — UNE feuille par fichier (un CSV n'en porte qu'une).

    Sans ``feuille``, c'est la première (les modules). Le séparateur est le
    point-virgule et l'encodage porte sa marque d'ordre d'octets : c'est ce
    qu'Excel en fr-MA ouvre sans écran d'import, et un CSV qu'il faut
    reformater n'est pas un export.
    """
    import csv
    import io

    from apps.records.xlsx import coerce_cell, neutralize_rows

    voulue = (feuille or tables[0][0]).strip().lower()
    for titre, entetes, lignes in tables:
        if titre.strip().lower() != voulue:
            continue
        tampon = io.StringIO(newline='')
        graveur = csv.writer(tampon, delimiter=';', lineterminator='\r\n')
        graveur.writerow(entetes)
        for ligne in neutralize_rows(lignes):
            graveur.writerow([coerce_cell(valeur) for valeur in ligne])
        return tampon.getvalue().encode('utf-8-sig')
    raise ExportRefuse(
        "Feuille inconnue : « %s ». Feuilles disponibles — %s."
        % (feuille, ', '.join(titre for titre, _e, _l in tables)),
        champ='feuille')


def _tables_du_calepinage(calepinage):
    from .planche import geometrie_de_planche

    geometrie = geometrie_de_planche(getattr(calepinage, 'roof_layout', None))
    return tables_du_resultat(geometrie, getattr(calepinage, 'resultat', None))


def exporter_xlsx(calepinage):
    """Le classeur d'un ``Calepinage``. Lève ``PlancheRefusee`` sans conception."""
    return classeur_octets(_tables_du_calepinage(calepinage))


def exporter_csv(calepinage, feuille=None):
    """La variante CSV d'une feuille du même classeur."""
    return csv_octets(_tables_du_calepinage(calepinage), feuille=feuille)
