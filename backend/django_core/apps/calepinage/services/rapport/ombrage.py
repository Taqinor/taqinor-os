"""CALX302 — la section « Ombrage » du rapport d'étude : accès solaire moyen
par pan, TOF/TSRF, la matrice d'ombrage 12×24 et la carte de chaleur déposée
par le navigateur (``POST image-document/``, ``services/images_document.py``).

Ce que la section imprime — LU, jamais recalculé
==================================================
* l'accès solaire moyen par pan et TOF/TSRF, LUS de ``production.par_pan[]
  .{tof, tsrf}`` (CALX58) et de ``ombrage.par_pan[].acces_solaire_moyen_pct``
  — une ligne SANS TOF/TSRF publie son ``motif_omission`` plutôt qu'un blanc ;
* la matrice d'ombrage horaire 12×24 (``roof_layout.shading12x24``), en
  chiffres — absente ou incomplète, la section le DIT plutôt que d'imprimer
  une grille à moitié fausse (même discipline que
  ``services/export_csv.py::_export_ombrage``) ;
* la carte de chaleur la plus récente déposée pour ce calepinage (genre
  ``ombrage``, CALX302) — absente, la section le DIT et n'invente aucune
  image.

``resultat['ombrage']['par_pan']`` (CALX58, non VIDE) est l'entrée EXIGÉE de
cette section (contrat ``rapport_etude.json``, ``entrees_exigees``) :
l'assembleur (``services/rapport/__init__.py``) n'appelle cette section QUE
si elle est publiée et non vide — la matrice et l'image restent, elles,
INDÉPENDAMMENT omettables (deux données qui n'existent pas encore pour tous
les calepinages).

``roof_layout`` ET L'IMAGE NE VOYAGENT PAS DANS ``resultat``
--------------------------------------------------------------
``shading12x24`` et l'image déposée vivent HORS du contrat
``calepinage_resultat.json`` (CALX70) — sur ``Calepinage.roof_layout`` et
``records.Attachment``. Cette section les relit ELLE-MÊME, par le PK publié
dans ``resultat['calepinage']`` (même résultat que le calepinage qui a
produit ce rapport — aucune fuite inter-société possible : ce PK est celui
de l'objet DÉJÀ borné société par la vue appelante). Toute lecture est
BEST-EFFORT : un incident (calepinage supprimé entre-temps, MinIO
injoignable) omet la pièce concernée plutôt que de faire tomber tout le
rapport — même discipline que ``versions_document``/``journal``.

AUCUN MONTANT (D5) — cette section ne lit que des pourcentages, des
facteurs d'ombrage et une image : aucune clé de coût n'y transite.
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi

__all__ = ['CSS_SECTION', 'html_de_section']

CSS_SECTION = (
    '.ombrage-orientation td.valeur,.ombrage-matrice td.valeur'
    '{text-align:right;}'
    '.ombrage-matrice{font-size:7pt;}'
    '.ombrage-matrice th{padding:0.6mm;}'
    '.ombrage-matrice td{padding:0.6mm;}'
    '.ombrage-image{max-width:100%;margin-top:2mm;border:0.2mm solid #999;}'
)


def _production_par_pan(resultat):
    """``{pan: ligne}`` depuis ``production.par_pan[]`` — TOF/TSRF (CALX58),
    LUS, jamais recalculés."""
    production = resultat.get('production') or {}
    return {str(p.get('pan') or ''): p
            for p in production.get('par_pan') or () if isinstance(p, dict)}


def _ligne_orientation(ligne_ombrage, production_par_pan):
    pan = str(ligne_ombrage.get('pan') or '')
    prod = production_par_pan.get(pan) or {}
    tof, tsrf = prod.get('tof'), prod.get('tsrf')
    acces = ligne_ombrage.get('acces_solaire_moyen_pct')
    motif = str(ligne_ombrage.get('motif_omission') or '').strip()
    cellule_tof = nombre_tel_que_servi(tof) if tof is not None else '—'
    cellule_tsrf = nombre_tel_que_servi(tsrf) if tsrf is not None else '—'
    note = ('<div class="note">%s</div>' % escape(motif)
            if tof is None and motif else '')
    return ('<tr><td>%s</td><td class="valeur">%s</td>'
            '<td class="valeur">%s</td><td class="valeur">%s%s</td></tr>'
            % (escape(pan),
               nombre_tel_que_servi(acces) if acces is not None else '—',
               cellule_tof, cellule_tsrf, note))


def _table_orientation(ombrage_par_pan, production_par_pan):
    entete = ('<th>Pan</th><th>Accès solaire moyen (%)</th><th>TOF</th>'
              '<th>TSRF</th>')
    lignes = ''.join(_ligne_orientation(ligne, production_par_pan)
                     for ligne in ombrage_par_pan)
    return ('<table class="ombrage-orientation generique"><tr>%s</tr>%s'
            '</table>' % (entete, lignes))


def _matrice_valide(roof_layout):
    matrice = (roof_layout or {}).get('shading12x24')
    if not (isinstance(matrice, list) and len(matrice) == 12
            and all(isinstance(mois, list) and len(mois) == 24
                    for mois in matrice)):
        return None
    return matrice


def _table_matrice(matrice):
    entete = '<th>Mois</th>' + ''.join(
        '<th>%02dh</th>' % heure for heure in range(24))
    lignes = []
    for rang, mois in enumerate(matrice, start=1):
        cellules = ''.join(
            '<td class="valeur">%s</td>'
            % (nombre_tel_que_servi(round(v, 2)) if isinstance(
                v, (int, float)) else '—')
            for v in mois)
        lignes.append('<tr><td>%s</td>%s</tr>' % (rang, cellules))
    return ('<table class="ombrage-matrice generique"><tr>%s</tr>%s</table>'
            % (entete, ''.join(lignes)))


def _calepinage_et_roof_layout(resultat):
    """Le calepinage QUI A PRODUIT ce résultat, relu pour SON
    ``roof_layout`` (``shading12x24`` n'est pas publié par ``resultat``,
    CALX70). ``None`` sur tout incident : best-effort, jamais bloquant."""
    pk = resultat.get('calepinage') if isinstance(resultat, dict) else None
    if not pk:
        return None
    try:
        from ...models import Calepinage

        return (Calepinage.objects
                .filter(pk=pk).only('id', 'roof_layout', 'company_id')
                .first())
    except Exception:  # noqa: BLE001 — matrice omise, jamais rapport cassé
        logger = _logger()
        logger.warning('CALX302 : relecture de roof_layout impossible '
                       '(calepinage %s)', pk)
        return None


def _image_ombrage_data_uri(calepinage):
    if calepinage is None:
        return None
    try:
        from ..images_document import derniere_image_encodee

        return derniere_image_encodee(calepinage, genre='ombrage')
    except Exception:  # noqa: BLE001 — image omise, jamais rapport cassé
        _logger().warning('CALX302 : relecture de la carte de chaleur '
                          'impossible (calepinage %s)',
                          getattr(calepinage, 'pk', None))
        return None


def _logger():
    import logging

    return logging.getLogger(__name__)


def html_de_section(contexte):
    """Le corps de la section ``ombrage`` (le titre est posé par
    l'assembleur)."""
    resultat = contexte.get('resultat') or {}
    ombrage = resultat.get('ombrage') or {}
    ombrage_par_pan = [p for p in ombrage.get('par_pan') or ()
                       if isinstance(p, dict)]
    production_par_pan = _production_par_pan(resultat)

    blocs = []
    if ombrage_par_pan:
        blocs.append(_table_orientation(ombrage_par_pan, production_par_pan))
    else:
        blocs.append(
            '<p class="note">Aucun accès solaire par module mesuré : ni '
            'accès solaire moyen, ni TOF, ni TSRF ne sont publiés pour ce '
            'toit.</p>')

    calepinage = _calepinage_et_roof_layout(resultat)
    roof_layout = getattr(calepinage, 'roof_layout', None) \
        if calepinage is not None else None
    matrice = _matrice_valide(roof_layout)
    if matrice is not None:
        blocs.append('<p class="grandeur">Matrice d’ombrage horaire '
                     '(12 mois × 24 h)</p>')
        blocs.append(_table_matrice(matrice))
    else:
        blocs.append(
            '<p class="note">Matrice d’ombrage horaire (12 × 24) non '
            'disponible : aucune ombre n’a été tracée sur ce toit, ou la '
            'matrice enregistrée est incomplète.</p>')

    data_uri = (_image_ombrage_data_uri(calepinage)
                if calepinage is not None else None)
    if data_uri:
        blocs.append(
            '<p class="grandeur">Carte de chaleur (déposée depuis '
            'l’atelier)</p><img class="ombrage-image" src="%s" '
            'alt="Carte de chaleur d’ombrage">' % escape(data_uri, quote=True))
    else:
        blocs.append(
            '<p class="note">Aucune carte de chaleur déposée : ouvrez '
            'l’atelier et joignez l’image depuis le panneau Documents.</p>')

    return ''.join(blocs)
