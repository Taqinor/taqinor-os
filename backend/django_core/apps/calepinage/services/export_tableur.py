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

from .garde_montants import MOTS_D_ARGENT, mots_d_argent
from .rangees import rangees_du_pan

__all__ = [
    'FEUILLES', 'MOTS_D_ARGENT', 'ExportRefuse', 'verifier_absence_de_prix',
    'table_modules', 'table_chaines', 'table_nomenclature',
    'tables_du_resultat',
    'classeur_octets', 'csv_octets', 'exporter_xlsx', 'exporter_csv',
    'FEUILLE_COMPARATIF', 'exporter_comparatif_xlsx',
]

#: Les trois feuilles, dans l'ordre du classeur.
FEUILLES = ('Modules', 'Chaînes', 'Nomenclature')

# ACAL231 - ``MOTS_D_ARGENT`` (réexporté) est LA liste unique de
# ``services/garde_montants.py`` : une seule garde, à frontières de mot.


class ExportRefuse(ValueError):
    """L'export refuse de sortir, en disant ce qui l'en empêche."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


class _Designation(str):
    """Une cellule de désignation du bordereau (ACAL231).

    Le texte imprimé peut porter une spécification SAISIE (« décision
    société — remise aux normes ») ; la garde ne lit que ``garde`` : la
    désignation et la référence venues du catalogue ou du moteur.
    """

    garde = ''


def verifier_absence_de_prix(entetes, lignes, *, colonnes_exclues=()):
    """Refuse une table qui charrie un mot d'argent (en-tête OU cellule).

    ACAL231 - garde UNIQUE à frontières de mot (``garde_montants``) : « Hammadi »,
    « Madani » ou un pan « Remise » ne sont plus refusés. Elle ne porte jamais
    sur un texte SAISI : ``colonnes_exclues`` écarte les colonnes de saisie
    (libellé de pan, bâtiment) et une cellule ``_Designation`` ne présente à
    la garde que ses parties catalogue/moteur.
    """
    suspects = []
    for entete in entetes:
        suspects += ['en-tête « %s »' % entete
                     for _mot in mots_d_argent(entete)]
    for rang, ligne in enumerate(lignes, start=1):
        for colonne, cellule in enumerate(ligne):
            if colonne in colonnes_exclues or not isinstance(cellule, str):
                continue
            lu = getattr(cellule, 'garde', None) or cellule
            suspects += ['ligne %d : « %s »' % (rang, cellule)
                         for _mot in mots_d_argent(lu)]
    if suspects:
        raise ExportRefuse(
            "Export refusé : une sortie technique ne porte aucun prix "
            "(`prix_achat` alimente un indicateur réservé au générateur). "
            "Trouvé — %s." % ' ; '.join(sorted(set(suspects))),
            champ='colonnes')


def _affectation_par_module(resultat):
    """``{'<zone.id>#<n>': ligne}`` de l'affectation PUBLIÉE (ACAL265)."""
    affectations = (((resultat or {}).get('electrique') or {})
                    .get('affectation') or [])
    return {str(entree.get('module')): entree for entree in affectations
            if isinstance(entree, dict) and entree.get('module')}


def table_modules(geometrie, resultat=None):
    """Un module POSÉ par ligne. Les quantités sont celles de la géométrie."""
    entetes = ['Pan', 'Bâtiment', 'Rangée', 'Module', 'Est (m)', 'Nord (m)',
               'Azimut (°)', 'Inclinaison (°)', 'Chaîne', 'Onduleur', 'MPPT']
    par_module = _affectation_par_module(resultat)
    lignes = []
    for pan in geometrie.get('pans') or ():
        # ACAL230 - la rangée a UNE définition ORIENTÉE (``rangees.py``).
        rangees = rangees_du_pan(pan['modules'], pan.get('azimut_deg'))
        reperes = pan.get('reperes_modules') or {}
        for rang, centre in enumerate(pan['modules'], start=1):
            # ACAL269 — le numéro STABLE (``panels[].n``) et l'étiquette de
            # rangée que le document porte ; à défaut l'index et la rangée
            # calculée (document ancien jamais numéroté).
            numero, rangee = reperes.get(centre) or (None, None)
            numero = numero if numero is not None else rang
            # ACAL265 — l'affectation se joint par LA clé de module
            # (``<repère du pan>#<n>``), jamais par la position dans la liste.
            affectation = par_module.get('%s#%d' % (pan['repere'], numero)) \
                or {}
            lignes.append([
                pan['libelle'] or pan['repere'],
                pan['batiment'] or '',
                rangee if rangee is not None else rangees[centre],
                numero,
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


def _designation_bordereau(ligne):
    """CALX304 — désignation + spec + référence, en UNE cellule (le tableau
    reste à 3 colonnes — ``Désignation``/``Quantité``/``Unité``, celles que
    CAL179 vérifie au caractère près). La référence produit n'apparaît QUE
    quand le stock en publie une ; la spec (chute de tension citée, norme,
    ou « décision société — <motif> » pour un organe ajouté à la main,
    ``services/protections.py::MENTION_SOCIETE``) est reprise TELLE QUELLE,
    jamais reformulée."""
    designation = str(ligne.get('designation') or '').strip()
    parties = [designation]
    spec = str(ligne.get('spec') or '').strip()
    if spec:
        parties.append(spec)
    reference = ligne.get('reference')
    if reference:
        parties.append('réf. %s' % reference)
    cellule = _Designation(' — '.join(p for p in parties if p))
    # La garde ne lit que le catalogue / le moteur : jamais la spécification
    # (qui peut être le motif saisi d'un organe ajouté).
    cellule.garde = ' — '.join(p for p in (
        designation, ('réf. %s' % reference) if reference else '') if p)
    return cellule


def _lignes_bordereau_electrique(resultat):
    """CALX304 — structure (``services/kits.py``), câble par section et
    longueur (``services/cables.py``), protections retenues et terre
    (``services/protections.py``/``services/terre.py``) : ces trois listes
    sont DÉJÀ calculées et servies par la clé racine
    ``resultat['nomenclature']`` (CALX246/247/227/230/232,
    ``core.electrique.nomenclature``) — une
    LECTURE, jamais un second calcul (le module n'a ici ni la conception ni
    la société pour recalculer quoi que ce soit). Une ligne dont la quantité
    n'est pas un nombre calculé est OMISE, jamais mise à 0 (D-CALX 7) :
    ``resultat['nomenclature']`` ne publie d'ailleurs déjà QUE des lignes
    dont la quantité est connue (CALX247 — sans règle de bordereau saisie,
    les lignes de structure sont absentes, pas nulles)."""
    lignes = []
    for entree in (resultat or {}).get('nomenclature') or ():
        if not isinstance(entree, dict):
            continue
        quantite = entree.get('quantite')
        if quantite is None:
            continue
        lignes.append([_designation_bordereau(entree), quantite,
                       entree.get('unite') or ''])
    return lignes


def table_nomenclature(resultat):
    """Désignation et QUANTITÉ. Pas de prix, pas de total, pas de fournisseur.

    CALX304 — étendue aux lignes de structure/câbles/protections/terre du
    bordereau électrique (``resultat['nomenclature']``), en plus des lignes
    module/onduleur historiques : MÊME table, MÊMES trois colonnes.
    """
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
    lignes.extend(_lignes_bordereau_electrique(resultat))
    return entetes, lignes


def tables_du_resultat(geometrie, resultat=None):
    """``[(titre, entetes, lignes)]`` pour les trois feuilles, PRIX VÉRIFIÉS."""
    tables = [
        (FEUILLES[0],) + table_modules(geometrie, resultat),
        (FEUILLES[1],) + table_chaines(resultat),
        (FEUILLES[2],) + table_nomenclature(resultat),
    ]
    # ACAL260 — la feuille DÉDIÉE des surfaces de pose, seulement quand le
    # document en porte : sans elles, le classeur d'aujourd'hui.
    surfaces = _table_surfaces_de_pose(geometrie)
    if surfaces is not None:
        tables.append((FEUILLE_SURFACES,) + surfaces)
    for titre, entetes, lignes in tables:
        # Colonnes Pan et Bâtiment : libellés SAISIS, hors garde (ACAL231) ;
        # même règle pour le libellé SAISI d'une surface de pose.
        if titre == FEUILLES[0]:
            exclues = (0, 1)
        elif titre == FEUILLE_SURFACES:
            exclues = (0,)
        else:
            exclues = ()
        verifier_absence_de_prix(entetes, lignes, colonnes_exclues=exclues)
    return tables


#: ACAL260 — le titre de la feuille des surfaces de pose.
FEUILLE_SURFACES = 'Surfaces de pose'


def _table_surfaces_de_pose(geometrie):
    """ACAL260 — une ligne par surface de pose (champ au sol, ombrière…) :
    genre, modules et tables RECOPIÉS du moteur, encombrement mesuré dans le
    repère LOCAL du moteur (m). ``None`` sans surface de pose."""
    from .planche import LIBELLE_GENRE_SURFACE

    surfaces = (geometrie or {}).get('surfaces_de_pose') or ()
    if not surfaces:
        return None
    entetes = ['Surface', 'Genre', 'Modules (moteur)', 'Tables',
               'Encombrement X (m)', 'Encombrement Y (m)', 'Repère']
    lignes = []
    for surface in surfaces:
        x0, y0, x1, y1 = surface['etendue']
        lignes.append([
            surface['libelle'],
            LIBELLE_GENRE_SURFACE.get(surface['kind'], surface['kind']),
            surface['modules'],
            len(surface['tables']),
            round(x1 - x0, 3),
            round(y1 - y0, 3),
            'local (non géoréférencé)',
        ])
    return entetes, lignes


# ── Les sorties, par l'utilitaire PARTAGÉ ───────────────────────────────────

def classeur_octets(tables, *, provenance=None):
    """Les trois feuilles dans UN classeur .xlsx, en octets.

    ``apps.records.xlsx.build_workbook`` construit la PREMIÈRE feuille (en-têtes
    en gras, largeurs lisibles) ; les suivantes sont ajoutées au même classeur
    avec la MÊME coercition (``coerce_cell``) et la MÊME neutralisation
    d'injection de formules (``neutralize_rows``) — l'utilitaire partagé ne sait
    pas encore faire plusieurs feuilles, mais on n'en recode aucune règle.

    CALX314 — ``provenance`` (les lignes de
    ``services.provenance_document.lignes_de_provenance``) pose une feuille
    ``Provenance`` EN TÊTE du classeur, sous la même garde de prix. Sans elle,
    le classeur est EXACTEMENT celui de CAL179.
    """
    import io

    from openpyxl.styles import Font

    from apps.records.xlsx import (
        build_workbook, coerce_cell, neutralize_rows,
    )

    if provenance is not None:
        from .provenance_document import ENTETES, TITRE_FEUILLE

        feuille_provenance = (TITRE_FEUILLE, list(ENTETES),
                              [list(ligne) for ligne in provenance])
        # Colonne « Valeur » exclue : elle porte le titre SAISI du calepinage
        # (ACAL231) ; les libellés (colonne 0) restent gardés.
        verifier_absence_de_prix(feuille_provenance[1],
                                 feuille_provenance[2],
                                 colonnes_exclues=(1,))
        tables = [feuille_provenance] + list(tables)

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
    from .. import selectors

    # ACAL216 — le résultat SERVI (pose, électrique, nomenclature), lecteur
    # tolérant : jamais la colonne brute, qui ne porte ni pose ni électrique.
    tables = tables_du_resultat(geometrie,
                                selectors.resultat_servi(calepinage))
    # CALX359 — la feuille « Fixation », EN FIN, seulement quand la société
    # a un catalogue de fixation : sans lui, le classeur est EXACTEMENT
    # celui d'aujourd'hui (D12). Même garde de prix que les trois autres.
    fixation = _table_fixation(calepinage)
    if fixation is not None:
        tables.append(fixation)
    return tables


def exporter_xlsx(calepinage):
    """Le classeur d'un ``Calepinage``. Lève ``PlancheRefusee`` sans conception.

    CALX314 — la feuille ``Provenance`` en tête, composée par
    ``provenance_document.lignes_de_provenance`` (la fonction PARTAGÉE avec le
    DXF et l'export JSON).
    """
    from .provenance_document import lignes_de_provenance

    return classeur_octets(_tables_du_calepinage(calepinage),
                           provenance=lignes_de_provenance(calepinage))


def exporter_csv(calepinage, feuille=None):
    """La variante CSV d'une feuille du même classeur."""
    return csv_octets(_tables_du_calepinage(calepinage), feuille=feuille)


# ── CALX341 — la feuille « Comparatif » de plusieurs calepinages ───────────

#: Le titre de la feuille du comparatif de calepinages (CALX341).
FEUILLE_COMPARATIF = 'Comparatif'


def _table_comparatif(comparaison):
    """``(entetes, lignes)`` du comparatif — LU dans la réponse du service.

    Les colonnes de grandeurs sont EXACTEMENT celles du contrat
    (``comparaison['colonnes']``, source unique
    ``services/comparaison_projets.COLONNES``) : l'écran et le classeur ne
    peuvent pas diverger. Une grandeur non simulée reste une cellule VIDE
    (``coerce_cell(None)``), jamais un 0 ; son motif est recopié dans la
    dernière colonne. Les identifiants REFUSÉS (autre société ou inexistants)
    sont listés en fin de feuille avec leur motif : un classeur qui les
    tairait laisserait croire qu'ils ont été comparés.
    """
    colonnes = list((comparaison or {}).get('colonnes') or ())
    entetes = (['Calepinage', 'Statut', 'Simulé']
               + ['%s (%s)' % (colonne['libelle'], colonne['unite'])
                  if colonne.get('unite') else colonne['libelle']
                  for colonne in colonnes]
               + ['Motif'])
    lignes = []
    for ligne in (comparaison or {}).get('lignes') or ():
        lignes.append(
            [ligne.get('titre') or 'Calepinage #%s' % ligne.get('id'),
             ligne.get('statut') or '',
             'oui' if ligne.get('simule') else 'non']
            + [ligne.get(colonne['cle']) for colonne in colonnes]
            + [ligne.get('motif') or ''])
    for refus in (comparaison or {}).get('refus') or ():
        lignes.append(['Calepinage #%s' % refus.get('id'), '', '']
                      + [None for _colonne in colonnes]
                      + [refus.get('motif') or ''])
    return entetes, lignes


def exporter_comparatif_xlsx(comparaison):
    """CALX341 — le classeur d'UNE feuille « Comparatif », en octets.

    AUCUN prix : la garde ``verifier_absence_de_prix`` porte sur les en-têtes
    et sur toutes les cellules produites par le serveur. La colonne
    « Calepinage » (le TITRE saisi par l'utilisateur) en est exclue, et c'est
    voulu : un titre n'est pas une donnée de coût, et un nom de famille comme
    « Hammadi » contient la sous-chaîne « mad » — la garde refuserait
    l'export d'un client pour son nom.
    """
    entetes, lignes = _table_comparatif(comparaison)
    verifier_absence_de_prix(entetes, [ligne[1:] for ligne in lignes])
    return classeur_octets([(FEUILLE_COMPARATIF, entetes, lignes)])
# ── CALX359 — la feuille « Fixation » ───────────────────────────────────────


def _table_fixation(calepinage):
    """``(titre, entetes, lignes)`` de la nomenclature de fixation, PRIX
    VÉRIFIÉS, ou ``None`` quand la société n'a aucun système de fixation.

    La nomenclature est celle de ``services/fixation.py`` (la MÊME que
    ``GET bom-fixation/``) : aucune quantité n'est recalculée ici.
    """
    from .fixation import table_fixation

    table = table_fixation(calepinage)
    if table is None:
        return None
    _titre, entetes, lignes = table
    verifier_absence_de_prix(entetes, lignes)
    return table
