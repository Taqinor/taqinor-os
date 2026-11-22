"""ACAL761 — le schéma « où va l'énergie », du soleil aux usages, en SVG.

Deux blocs côte à côte, dessinés depuis le résultat SERVI (jamais recalculé) :

* A « Du soleil à l'électricité » : « Soleil reçu » (``depart_kwh``), les
  postes de perte de ``cascade.postes_lisibles`` (``perte_kwh``) et « Électricité
  produite » (``arrivee_kwh``) ;
* B « De l'électricité aux usages » : production brute, consommée sur place,
  injectée au réseau, écrêtée (si appliqué), importée du réseau et
  consommation (``autoconsommation.energie``), plus deux lignes de texte pour
  la batterie quand ``apres_batterie`` est vrai (``batterie.total``).

La LARGEUR d'un flux est sa valeur servie × l'échelle du bloc (publiée sur le
bloc : ``data-px-par-kwh``) ; la valeur est sur ``data-kwh``. Aucune somme,
aucune soustraction, aucune répartition. Deux totaux servis qui diffèrent
restent imprimés chacun. Un flux ``null`` ou un poste non compté est une case
hachurée « non calculé — <motif servi> », jamais 0. Noir et gris seulement,
aucun accès réseau, dimensions fixes en pixels (même discipline que
``diagramme_pertes.py``).
"""
from __future__ import annotations

from html import escape

from .diagramme_pertes import (
    ID_HACHURE, DiagrammeRefuse, _est_nombre, _n, _texte,
)

__all__ = ['svg_d_energie', 'svg_de_l_energie_du_calepinage']

_NOIR, _GRIS_TEXTE, _GRIS_TRAIT, _GRIS_FOND = '#111', '#555', '#999', '#f2f2f2'
_POLICE = 'DejaVu Sans, Arial, sans-serif'
#: Dimensions de MISE EN FORME du SVG (convention d'atelier, même discipline
#: que ``diagramme_pertes.py``) : largeur d'un bloc, longueur de la plus grande
#: barre, pas vertical entre deux lignes, épaisseur d'une barre, marge du
#: titre, et nombre de lignes réservées par bloc pour fixer la hauteur.
#: Aucune n'est une grandeur physique : elles ne changent aucun chiffre servi.
LARGEUR_BLOC_PX = 372.0
LARGEUR_BARRE_MAX_PX = 340.0
PAS_LIGNE_PX = 30.0
HAUTEUR_BARRE_PX = 10.0
MARGE_HAUTE_PX = 30.0
LIGNES_MAX = 8


def _libelles(langue):
    from .documents.libelles_document import libelle

    return {code: libelle(code, langue) for code in (
        'energie_titre', 'energie_titre_a', 'energie_titre_b',
        'energie_soleil', 'energie_produite', 'energie_production_brute',
        'energie_sur_place', 'energie_injectee', 'energie_ecretee',
        'energie_importee', 'energie_consommation', 'energie_non_calcule',
        'energie_batterie', 'energie_pertes_batterie', 'poste_non_compte')}


def _motif_poste(poste, textes):
    from .rapport.champs_lisibles import motif_lisible

    for etape in poste.get('etapes') or ():
        if isinstance(etape, dict) and etape.get('motif_omission'):
            return motif_lisible(etape['motif_omission'])
    return textes['poste_non_compte']


def _bloc(x0, titre, flux, textes, langue, notes=()):
    """Un bloc : ``flux`` = [(code, libellé, kWh ou None, motif)]."""
    from .rapport import nombre_tel_que_servi

    valeurs = [v for _c, _l, v, _m in flux if _est_nombre(v)]
    plus_grand = max(valeurs) if valeurs else 0
    echelle = LARGEUR_BARRE_MAX_PX / plus_grand if plus_grand else 0.0
    morceaux = ['<g class="bloc" data-px-par-kwh="%s" '
                'transform="translate(%s 0)">' % (repr(float(echelle)), _n(x0)),
                _texte(0, 16, titre, taille=11, ancre='start', gras=True)]
    y = MARGE_HAUTE_PX
    for code, nom, kwh, motif in flux:
        if _est_nombre(kwh):
            ligne = '%s — %s kWh' % (nom, nombre_tel_que_servi(kwh, langue))
        else:
            ligne = '%s — %s — %s' % (nom, textes['energie_non_calcule'],
                                      motif or '—')
        morceaux.append(_texte(0, y + 8, ligne, taille=9, ancre='start'))
        if _est_nombre(kwh):
            morceaux.append(
                '<rect class="flux" data-flux="%s" data-kwh="%s" x="0" y="%s" '
                'width="%s" height="%s" fill="%s" stroke="%s" '
                'stroke-width="0.6" />'
                % (escape(code, quote=True), repr(float(kwh)), _n(y + 12),
                   _n(round(kwh * echelle, 2)), _n(HAUTEUR_BARRE_PX),
                   _GRIS_TEXTE, _NOIR))
        else:
            morceaux.append(
                '<rect class="flux-non-calcule" data-flux="%s" x="0" y="%s" '
                'width="%s" height="%s" fill="url(#%s)" stroke="%s" '
                'stroke-width="0.6" stroke-dasharray="2 1" />'
                % (escape(code, quote=True), _n(y + 12),
                   _n(LARGEUR_BARRE_MAX_PX), _n(HAUTEUR_BARRE_PX),
                   ID_HACHURE, _GRIS_TRAIT))
        y += PAS_LIGNE_PX
    for note in notes:
        morceaux.append(_texte(0, y + 8, note, taille=9, ancre='start',
                               couleur=_GRIS_TEXTE))
        y += 14
    morceaux.append('</g>')
    return morceaux


def _flux_a(cascade, textes):
    lisibles = cascade.get('postes_lisibles')
    if not isinstance(lisibles, dict) or not isinstance(
            lisibles.get('postes'), list):
        raise DiagrammeRefuse(
            "Aucune cascade regroupée n'est servie pour ce calepinage : le "
            "schéma se dessine depuis la simulation (champ « cascade »).")
    flux = [('soleil', textes['energie_soleil'], lisibles.get('depart_kwh'),
             '')]
    for poste in lisibles['postes']:
        compte = poste.get('statut') != 'non_compte'
        flux.append((str(poste.get('poste') or ''),
                     str(poste.get('libelle') or poste.get('poste') or ''),
                     poste.get('perte_kwh') if compte else None,
                     '' if compte else _motif_poste(poste, textes)))
    flux.append(('produite', textes['energie_produite'],
                 lisibles.get('arrivee_kwh'), ''))
    return flux


def _flux_b(autoconsommation, textes):
    """``(flux, notes_batterie_a_ajouter)`` ; bloc entier hachuré sans
    ``autoconsommation.energie``."""
    from .rapport.champs_lisibles import motif_lisible

    energie = (autoconsommation or {}).get('energie')
    if not isinstance(energie, dict):
        motif = motif_lisible(
            (autoconsommation or {}).get('motif_absence') or '')
        return [('autoconsommation', textes['energie_consommation'], None,
                 motif)]
    plafond = autoconsommation.get('plafond')
    flux = [
        ('production_brute', textes['energie_production_brute'],
         energie.get('production_brute_kwh'), ''),
        ('sur_place', textes['energie_sur_place'],
         energie.get('autoconsomme_kwh'), ''),
        ('injectee', textes['energie_injectee'],
         energie.get('export_reseau_kwh'), ''),
    ]
    if isinstance(plafond, dict) and plafond.get('applique'):
        flux.append(('ecretee', textes['energie_ecretee'],
                     plafond.get('energie_ecretee_kwh'), ''))
    flux.append(('importee', textes['energie_importee'],
                 energie.get('import_reseau_kwh'), ''))
    flux.append(('consommation', textes['energie_consommation'],
                 energie.get('consommation_kwh'), ''))
    return flux


def _notes_batterie(resultat, textes, langue):
    from .rapport import nombre_tel_que_servi

    energie = ((resultat.get('autoconsommation') or {}).get('energie') or {})
    total = ((resultat.get('batterie') or {}).get('total') or {})
    if not energie.get('apres_batterie') or not isinstance(total, dict):
        return ()
    return ('%s : %s kWh · %s : %s kWh' % (
        textes['energie_batterie'],
        nombre_tel_que_servi(total.get('energie_restituee_kwh'), langue),
        textes['energie_pertes_batterie'],
        nombre_tel_que_servi(
            (total.get('energie') or {}).get('pertes_batterie_kwh'), langue)),)


def svg_d_energie(resultat, langue='fr'):
    """Le SVG AUTONOME des flux d'énergie — aucune valeur recalculée.

    Lève ``DiagrammeRefuse`` (champ ``cascade``) sans ``postes_lisibles``.
    """
    resultat = resultat if isinstance(resultat, dict) else {}
    textes = _libelles(langue)
    cascade = resultat.get('cascade')
    flux_a = _flux_a(cascade if isinstance(cascade, dict) else {}, textes)
    autoconsommation = resultat.get('autoconsommation')
    flux_b = _flux_b(autoconsommation, textes)
    largeur = 2 * LARGEUR_BLOC_PX + 24
    hauteur = MARGE_HAUTE_PX + PAS_LIGNE_PX * LIGNES_MAX + 28
    morceaux = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        'width="%spx" height="%spx" viewBox="0 0 %s %s" font-family="%s">'
        % (_n(largeur), _n(hauteur), _n(largeur), _n(hauteur), _POLICE),
        '<title>%s</title>' % escape(textes['energie_titre']),
        '<defs><pattern id="%s" patternUnits="userSpaceOnUse" width="6" '
        'height="6" patternTransform="rotate(45)"><rect x="0" y="0" '
        'width="6" height="6" fill="%s" /><line x1="0" y1="0" x2="0" y2="6" '
        'stroke="%s" stroke-width="2" /></pattern></defs>'
        % (ID_HACHURE, _GRIS_FOND, _GRIS_TEXTE),
        '<rect x="0" y="0" width="%s" height="%s" fill="#ffffff" />'
        % (_n(largeur), _n(hauteur)),
    ]
    morceaux += _bloc(8, textes['energie_titre_a'], flux_a, textes, langue)
    morceaux += _bloc(LARGEUR_BLOC_PX + 16, textes['energie_titre_b'], flux_b,
                      textes, langue,
                      notes=_notes_batterie(resultat, textes, langue))
    morceaux.append('</svg>')
    return '\n'.join(morceaux)


def svg_de_l_energie_du_calepinage(calepinage, *, langue=None):
    """Le schéma d'un calepinage, depuis le résultat SERVI (fraîcheur CALX70)
    — lève ``DiagrammeRefuse`` ou ``RapportRefuse`` en nommant la donnée."""
    from .documents.libelles_document import langue_du_document
    from .rapport import resultat_du_rapport

    servi, _stocke = resultat_du_rapport(calepinage)
    return svg_d_energie(servi, langue=langue_du_document(calepinage, langue))
