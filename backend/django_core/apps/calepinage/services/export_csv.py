"""CAL144 — export CSV de la simulation : horaire, mensuel, ombrage 12×24.

LE CONSTAT
----------
Le dépôt n'exporte AUCUNE série : côté calepinage, le seul export existant est
une conversion SVG→PNG côté navigateur. Or l'export CSV de la série horaire est
un standard de tous les outils comparés — c'est ce qui permet à un bureau
d'études de refaire le calcul ailleurs.

LES CHOIX, ET POURQUOI
----------------------
* **Séparateur ``;`` et décimale ``,``** — la convention CSV déjà en place dans
  le dépôt (``apps/compta/services.py``, ``apps/btp_chantier``,
  ``apps/adminops``) et celle qu'attend un Excel français. Les deux vont
  ENSEMBLE : un ``;`` avec un point décimal donnerait des colonnes justes et
  des nombres que le tableur lit comme du texte.
* **BOM UTF-8** (``utf-8-sig``) — sans lui, Excel sous Windows affiche
  « Ã©chauffement » à la place des accents. Même recette que les exports
  existants.
* **Un en-tête de PROVENANCE avant le tableau** — base PVGIS réellement
  utilisée, fenêtre d'années, version du moteur, et la perte passée avec le
  détail de ses postes (CAL238). Un CSV qui circule sans sa provenance devient
  un chiffre orphelin le lendemain.
* **AUCUN PRIX.** Ni prix de vente, ni ``prix_achat``, ni marge : cet export
  décrit de l'énergie. Un test le vérifie sur le texte produit.
* **Série indisponible ⇒ export REFUSÉ**, avec le motif en français. Jamais un
  fichier de zéros : un tableur ne sait pas distinguer « pas simulé » de
  « ne produit rien », mais un refus, si.

CALX313 — colonnes et pas de temps choisis, sur l'export HORAIRE seulement
--------------------------------------------------------------------------
``export_csv(quoi='horaire')`` servait TOUJOURS les mêmes sept colonnes
(renommées, CAL144) au pas horaire, sans sélection possible. Deux paramètres
s'ajoutent, ADDITIFS — un appel sans eux sort EXACTEMENT ce qu'il sortait
(``tests/test_calx142_contrat_serie.py`` le prouve ligne à ligne) :

* ``colonnes`` — un sous-ensemble de ``COLONNES_HORAIRE``, le vocabulaire
  RÉELLEMENT servi par le bloc ``serie_horaire`` (contrat CALX142, W3) : les
  sept colonnes historiques renommées, PLUS les treize colonnes additives à
  plat (``p_ac_kw``, ``charge_kwh``…), plus l'alias ``t`` pour ``heure``.
  Aucune colonne n'est FABRIQUÉE ici : chaque extracteur relit un champ que
  le moteur publie déjà, jamais une valeur dérivée à la volée. Une colonne
  hors de ce vocabulaire est REFUSÉE en la NOMMANT — jamais silencieusement
  ignorée. Le bloc de provenance liste désormais les colonnes retenues (une
  ligne ``Colonnes retenues``), pour que le fichier reste lisible seul.
* ``pas`` — ``horaire`` (défaut) ou ``15min``. Le second est REFUSÉ avec son
  motif : la série au pas de 15 minutes n'est pas encore produite par le
  moteur, et ce module n'INTERPOLE JAMAIS une série horaire pour la
  remplacer (même discipline que « série indisponible ⇒ refus », jamais un
  chiffre inventé entre deux heures mesurées).
"""
from __future__ import annotations

import csv
import io

__all__ = ['EXPORTS', 'PAS_DISPONIBLES', 'COLONNES_HORAIRE',
           'DEFAULT_COLONNES_HORAIRE', 'ExportImpossible',
           'encoder_pour_tableur', 'export_csv', 'nom_de_fichier']

#: Les trois exports du module — toute autre valeur est refusée en la nommant.
EXPORTS = ('horaire', 'mensuel', 'ombrage')

#: CALX313 — les deux pas de temps ÉNONCÉS. Seul ``horaire`` produit un
#: fichier aujourd'hui ; ``15min`` est un pas RECONNU mais pas encore
#: disponible (refus dédié, jamais une interpolation).
PAS_DISPONIBLES = ('horaire', '15min')

SEPARATEUR = ';'
ENCODAGE_TABLEUR = 'utf-8-sig'


class ExportImpossible(ValueError):
    """Un export refusé, avec son motif FRANÇAIS et le champ à pointer."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


def _decimal(valeur, decimales=3):
    """Un nombre à la française (décimale ``,``), ou une cellule VIDE.

    Vide ≠ 0 : une heure sans mesure reste vide, elle ne devient pas un zéro
    de production.
    """
    if valeur is None:
        return ''
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return ''
    return f'{nombre:.{decimales}f}'.replace('.', ',')


def _lignes_de_provenance(document, *, colonnes_retenues=None):
    """L'en-tête de provenance — d'où vient CE fichier, en clair.

    CALX313 — ``colonnes_retenues`` (les NOMS demandés par l'appelant, dans
    l'ordre) ajoute une ligne ``Colonnes retenues`` quand elle est fournie ;
    absente (``mensuel``/``ombrage``, qui n'ont pas de sélection de colonnes),
    rien ne change — l'ajout est ADDITIF.
    """
    production = (document or {}).get('production') or {}
    base = production.get('base') or {}
    pertes = (document or {}).get('pertes') or []
    detail = ' + '.join(
        f'{poste.get("poste")} {_decimal(poste.get("pct"), 2)} %'
        f' ({poste.get("source") or "source non renseignée"})'
        for poste in pertes) or 'aucun poste publié'
    lignes = [
        # Pas de marque en dur ici (SCA29, white-label) : le
        # branding client vient du thème de la société, pas d'un
        # export technique.
        ['Provenance', 'Module Calepinage'],
        ['Base de rayonnement', base.get('base_rayonnement') or
         base.get('source') or 'non publiée'],
        ["Fenêtre d'années", base.get('fenetre_annees') or 'non publiée'],
        ['Version du moteur',
         (document or {}).get('version_moteur') or 'non publiée'],
        ['Pertes passées à PVGIS (%)',
         _decimal(base.get('loss_passee_pct'), 3)],
        ['Détail des pertes', detail],
    ]
    if colonnes_retenues:
        lignes.append(['Colonnes retenues', ', '.join(colonnes_retenues)])
    lignes.append([])
    return lignes


def _ecrire(lignes):
    tampon = io.StringIO()
    graveur = csv.writer(tampon, delimiter=SEPARATEUR, lineterminator='\r\n')
    graveur.writerows(lignes)
    return tampon.getvalue()


def _brute(cle, decimales=3):
    """Un extracteur qui relit ``point[cle]`` TEL QUEL (arrondi d'affichage
    seulement) — CALX313, une des colonnes additives du bloc W3."""
    def extracteur(point):
        return _decimal(point.get(cle), decimales)
    return extracteur


def _production_kw(point):
    valeur = point.get('p_w')
    # P est rendu par PVGIS en W ; la colonne est en kW, unité écrite dans
    # l'en-tête (une colonne sans unité est une colonne fausse).
    return _decimal(valeur / 1000.0 if valeur is not None else None)


#: CALX313 — nom de colonne demandable -> extracteur ``point -> cellule``.
#: Le vocabulaire RÉELLEMENT servi par le bloc ``serie_horaire`` (contrat
#: CALX142, « W3 ») : les sept colonnes historiques renommées de CAL144
#: (jamais renommées à nouveau — ``tests/test_calx142_contrat_serie.py``),
#: les treize colonnes additives À PLAT (mêmes noms que le contrat), et
#: l'alias ``t`` (raccourci pour ``heure``, l'heure du jour). AUCUNE colonne
#: n'est calculée ici au-delà d'une conversion d'unité déjà en place
#: (``p_w`` -> kW) : chaque valeur relit un champ que le moteur publie.
COLONNES_HORAIRE = {
    'annee': lambda point: point.get('annee', ''),
    'mois': lambda point: point.get('mois', ''),
    'jour': lambda point: point.get('jour', ''),
    'heure': lambda point: point.get('heure', ''),
    # Alias : « t » désigne l'heure du jour, un champ RÉEL du point — jamais
    # une valeur inventée.
    't': lambda point: point.get('heure', ''),
    'production_kw': _production_kw,
    'irradiance_plan_w_m2': _brute('gi_w_m2', 2),
    'temperature_air_c': _brute('t2m_c', 2),
    'p_w': _brute('p_w'),
    'gi_w_m2': _brute('gi_w_m2', 2),
    't2m_c': _brute('t2m_c', 2),
    'gb_i_w_m2': _brute('gb_i_w_m2', 2),
    'gd_i_w_m2': _brute('gd_i_w_m2', 2),
    'gr_i_w_m2': _brute('gr_i_w_m2', 2),
    'ws10m': _brute('ws10m', 2),
    'h_sun_deg': _brute('h_sun_deg', 2),
    't_cell_c': _brute('t_cell_c', 2),
    'p_dc_kw': _brute('p_dc_kw'),
    'p_ac_kw': _brute('p_ac_kw'),
    'ecretage_kw': _brute('ecretage_kw'),
    'charge_kwh': _brute('charge_kwh'),
    'batterie_soc_pct': _brute('batterie_soc_pct', 1),
    'reseau_import_kwh': _brute('reseau_import_kwh'),
    'reseau_export_kwh': _brute('reseau_export_kwh'),
}

#: Le comportement D'AVANT CALX313, figé : un appel sans ``colonnes=`` doit
#: sortir EXACTEMENT ces sept colonnes, dans cet ordre (additif, jamais
#: substitutif — ``test_calx142_contrat_serie.py`` le prouve ligne à ligne).
DEFAULT_COLONNES_HORAIRE = ('annee', 'mois', 'jour', 'heure',
                            'production_kw', 'irradiance_plan_w_m2',
                            'temperature_air_c')


def _colonnes_retenues(colonnes):
    """Les noms de colonnes à servir, validés — ou un refus qui NOMME la
    colonne inconnue (CALX313)."""
    noms = list(colonnes) if colonnes is not None \
        else list(DEFAULT_COLONNES_HORAIRE)
    if not noms:
        raise ExportImpossible(
            'Aucune colonne demandée : « colonnes » ne peut pas être une '
            'liste vide.', champ='colonnes')
    inconnues = [nom for nom in noms if nom not in COLONNES_HORAIRE]
    if inconnues:
        raise ExportImpossible(
            'Colonne(s) inconnue(s) : « %s ». Colonnes disponibles : %s.'
            % (', '.join(inconnues), ', '.join(sorted(COLONNES_HORAIRE))),
            champ='colonnes')
    return noms


def _valider_pas(pas):
    """``pas`` refusé, nommé — CALX313 : le 15 minutes n'est jamais une
    interpolation d'une série horaire."""
    if pas not in PAS_DISPONIBLES:
        raise ExportImpossible(
            'Pas de temps inconnu : « %s ». Pas disponibles : %s.'
            % (pas, ', '.join(PAS_DISPONIBLES)), champ='pas')
    if pas == '15min':
        raise ExportImpossible(
            "L'export au pas de 15 minutes n'est pas disponible : la série "
            "au pas de 15 minutes n'est pas encore produite par le moteur, "
            'et ce module n\'interpole JAMAIS une série horaire pour la '
            'remplacer.', champ='pas')


def _export_horaire(document, *, colonnes=None, pas='horaire'):
    _valider_pas(pas)
    noms = _colonnes_retenues(colonnes)
    points = (document or {}).get('points') or []
    if not points:
        raise ExportImpossible(
            "La série horaire n'est pas disponible pour ce calepinage : "
            "lancez la simulation avant d'exporter. Aucun fichier de zéros "
            "n'est produit à la place.", champ='points')
    lignes = _lignes_de_provenance(document, colonnes_retenues=noms)
    lignes.append(list(noms))
    for point in points:
        lignes.append([COLONNES_HORAIRE[nom](point) for nom in noms])
    return _ecrire(lignes)


def _export_mensuel(document):
    mensuel = (((document or {}).get('production') or {}).get('mensuel')
               or [])
    if not mensuel:
        raise ExportImpossible(
            "Aucun agrégat mensuel n'est disponible pour ce calepinage : "
            "lancez la simulation avant d'exporter.", champ='mensuel')
    lignes = _lignes_de_provenance(document)
    lignes.append(['mois', 'production_kwh'])
    for mois in mensuel:
        lignes.append([mois.get('mois', ''),
                       _decimal(mois.get('p50_kwh'), 1)])
    total = ((document or {}).get('production') or {}).get('total') or {}
    lignes.append(['total_annuel', _decimal(total.get('p50_kwh'), 1)])
    return _ecrire(lignes)


def _export_ombrage(document):
    matrice = (document or {}).get('shading12x24')
    if not isinstance(matrice, list) or len(matrice) != 12 or not all(
            isinstance(mois, list) and len(mois) == 24 for mois in matrice):
        raise ExportImpossible(
            "Aucune matrice d'ombrage 12 × 24 n'est disponible pour ce "
            'calepinage (aucune ombre tracée, ou matrice incomplète) : '
            "l'export est refusé plutôt que de livrer une grille à moitié "
            'fausse.', champ='shading12x24')
    lignes = _lignes_de_provenance(document)
    lignes.append(['mois'] + [f'h{heure:02d}' for heure in range(24)])
    for rang, mois in enumerate(matrice, start=1):
        lignes.append([rang] + [_decimal(facteur, 3) for facteur in mois])
    return _ecrire(lignes)


_FABRIQUES = {
    'horaire': _export_horaire,
    'mensuel': _export_mensuel,
    'ombrage': _export_ombrage,
}


def export_csv(document, *, quoi='horaire', colonnes=None, pas='horaire'):
    """Le texte CSV d'un export, ou un refus MOTIVÉ.

    Args:
        document: ``{'production': {...}, 'points': [...],
            'shading12x24': [[…]], 'version_moteur': '…'}`` — la sortie de
            ``services.production`` enrichie de la série horaire et de la
            matrice d'ombrage du document de toiture.
        quoi: ``horaire`` | ``mensuel`` | ``ombrage``.
        colonnes: CALX313, ``horaire`` SEULEMENT — sous-ensemble de
            ``COLONNES_HORAIRE`` à servir, dans l'ordre demandé. ``None``
            (défaut) sert ``DEFAULT_COLONNES_HORAIRE`` — le comportement
            d'avant CALX313, inchangé. Ignoré pour ``mensuel``/``ombrage``.
        pas: CALX313, ``horaire`` SEULEMENT — ``horaire`` (défaut) ou
            ``15min`` (refusé : la série 15 minutes n'est pas encore
            produite). Ignoré pour ``mensuel``/``ombrage``.

    Raises:
        ExportImpossible: export inconnu, pas de temps indisponible, colonne
            inconnue, ou donnée absente / incomplète.
    """
    fabrique = _FABRIQUES.get(quoi)
    if fabrique is None:
        raise ExportImpossible(
            f'Export inconnu : « {quoi} ». Exports disponibles : '
            f'{", ".join(EXPORTS)}.', champ='quoi')
    if quoi == 'horaire':
        return fabrique(document, colonnes=colonnes, pas=pas)
    return fabrique(document)


def encoder_pour_tableur(texte):
    """Le CSV en octets, avec le BOM qu'Excel attend."""
    return texte.encode(ENCODAGE_TABLEUR)


def nom_de_fichier(calepinage_id, quoi):
    """Un nom de fichier parlant — sans donnée client, sans prix."""
    return f'calepinage-{calepinage_id}-{quoi}.csv'
