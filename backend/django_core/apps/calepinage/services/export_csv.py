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
"""
from __future__ import annotations

import csv
import io

__all__ = ['EXPORTS', 'ExportImpossible', 'encoder_pour_tableur',
           'export_csv', 'nom_de_fichier']

#: Les trois exports du module — toute autre valeur est refusée en la nommant.
EXPORTS = ('horaire', 'mensuel', 'ombrage')

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


def _lignes_de_provenance(document):
    """L'en-tête de provenance — d'où vient CE fichier, en clair."""
    production = (document or {}).get('production') or {}
    base = production.get('base') or {}
    pertes = (document or {}).get('pertes') or []
    detail = ' + '.join(
        f'{poste.get("poste")} {_decimal(poste.get("pct"), 2)} %'
        f' ({poste.get("source") or "source non renseignée"})'
        for poste in pertes) or 'aucun poste publié'
    return [
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
        [],
    ]


def _ecrire(lignes):
    tampon = io.StringIO()
    graveur = csv.writer(tampon, delimiter=SEPARATEUR, lineterminator='\r\n')
    graveur.writerows(lignes)
    return tampon.getvalue()


def _export_horaire(document):
    points = (document or {}).get('points') or []
    if not points:
        raise ExportImpossible(
            "La série horaire n'est pas disponible pour ce calepinage : "
            "lancez la simulation avant d'exporter. Aucun fichier de zéros "
            "n'est produit à la place.", champ='points')
    lignes = _lignes_de_provenance(document)
    lignes.append(['annee', 'mois', 'jour', 'heure',
                   'production_kw', 'irradiance_plan_w_m2',
                   'temperature_air_c'])
    for point in points:
        lignes.append([
            point.get('annee', ''), point.get('mois', ''),
            point.get('jour', ''), point.get('heure', ''),
            # P est rendu par PVGIS en W ; la colonne est en kW, unité écrite
            # dans l'en-tête (une colonne sans unité est une colonne fausse).
            _decimal((point.get('p_w') / 1000.0)
                     if point.get('p_w') is not None else None),
            _decimal(point.get('gi_w_m2'), 2),
            _decimal(point.get('t2m_c'), 2),
        ])
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


def export_csv(document, *, quoi='horaire'):
    """Le texte CSV d'un export, ou un refus MOTIVÉ.

    Args:
        document: ``{'production': {...}, 'points': [...],
            'shading12x24': [[…]], 'version_moteur': '…'}`` — la sortie de
            ``services.production`` enrichie de la série horaire et de la
            matrice d'ombrage du document de toiture.
        quoi: ``horaire`` | ``mensuel`` | ``ombrage``.

    Raises:
        ExportImpossible: export inconnu, ou donnée absente / incomplète.
    """
    fabrique = _FABRIQUES.get(quoi)
    if fabrique is None:
        raise ExportImpossible(
            f'Export inconnu : « {quoi} ». Exports disponibles : '
            f'{", ".join(EXPORTS)}.', champ='quoi')
    return fabrique(document)


def encoder_pour_tableur(texte):
    """Le CSV en octets, avec le BOM qu'Excel attend."""
    return texte.encode(ENCODAGE_TABLEUR)


def nom_de_fichier(calepinage_id, quoi):
    """Un nom de fichier parlant — sans donnée client, sans prix."""
    return f'calepinage-{calepinage_id}-{quoi}.csv'
