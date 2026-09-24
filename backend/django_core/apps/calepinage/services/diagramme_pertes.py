"""CALX308 — le DIAGRAMME DE PERTES, rendu en SVG par le SERVEUR.

Le constat
==========
La cascade n'existait QUE dans le navigateur, en recharts
(``frontend/src/features/calepinage/production/DiagrammePertes.jsx``) : aucune
pièce imprimable ne pouvait l'emporter, et le module refuse toute dépendance
de rastérisation (``views/sorties.py``, en-tête). Ce module dessine la MÊME
cascade — ``resultat['cascade']``, contrat
``contract_samples/calepinage_pertes_cascade.json`` (CALX141) — en SVG
autonome, que le rapport d'étude embarque dans sa section « pertes » et que
``GET calepinages/<pk>/diagramme-pertes.svg/`` sert tel quel.

Ce qui est dessiné
==================
Une colonne par étape, dans l'ORDRE de la cascade, entre deux bornes :
« irradiance incidente » (le ``kwh_avant`` de la première étape) et « énergie
livrée » (le dernier ``kwh_apres`` connu) — deux valeurs LUES, imprimées
telles que servies. La HAUTEUR d'une barre est proportionnelle à la part
SERVIE (``perte_pct``) : ``hauteur = |perte_pct| × px_par_point``, l'échelle
étant publiée sur la racine (``data-px-par-point``) pour que la hauteur se
relise en points. AUCUNE part n'est recalculée : chaque barre porte sa part
servie (``data-pct``) et son libellé. Un gain (bifacial) garde son signe
servi. Une étape OMISE (part ``null``) n'a pas de barre proportionnelle : une
case hachurée « omis », jamais une barre de hauteur zéro qui se lirait
« 0 % ». Un poste SANS SOURCE est HACHURÉ.

La discipline de ``planche.svg_de_planche``
===========================================
Aucune police distante, aucune image externe, aucune feuille importée : le
SVG ne fait AUCUN accès réseau. La seule URI du document est l'identifiant
d'espace de noms SVG (``xmlns``), exigé par la norme pour qu'un fichier
``.svg`` soit lu comme du SVG, et qui n'est jamais chargé. Les dimensions
sont FIXES, en pixels (largeur ET hauteur explicites) : WeasyPrint ne devine
jamais la taille d'un SVG embarqué.
"""
from __future__ import annotations

from html import escape

__all__ = [
    'DiagrammeRefuse', 'ID_HACHURE', 'LARGEUR_DEFAUT_MM', 'HAUTEUR_TRACE_PX',
    'px_de_mm', 'echelle_px_par_point', 'svg_de_cascade', 'svg_embarquable',
    'svg_du_calepinage',
]

#: L'identifiant du motif de hachure — un poste non sourcé le porte.
ID_HACHURE = 'hachure-non-source'

#: Largeur par défaut : la largeur utile d'une page A4 du gabarit (CALX294).
LARGEUR_DEFAUT_MM = 170.0

#: Hauteur de la zone de tracé des barres, en pixels.
HAUTEUR_TRACE_PX = 180.0
MARGE_HAUTE_PX = 44.0
ZONE_LIBELLES_PX = 236.0
MARGE_LATERALE_PX = 8.0

#: Charte d'impression du gabarit (noir/gris) — aucune couleur de plus.
_NOIR, _GRIS_TEXTE, _GRIS_TRAIT, _GRIS_FOND = '#111', '#555', '#999', '#f2f2f2'
_POLICE = 'DejaVu Sans, Arial, sans-serif'


class DiagrammeRefuse(ValueError):
    """Pas de diagramme sans cascade — et le refus NOMME la donnée."""

    def __init__(self, message, *, champ='cascade'):
        super().__init__(message)
        self.champ = champ


def px_de_mm(millimetres):
    """Millimètres -> pixels CSS (96 px par pouce, 25,4 mm par pouce)."""
    return round(float(millimetres) * 96.0 / 25.4, 2)


def _n(valeur):
    """Une coordonnée SVG compacte (2 décimales, sans zéros inutiles)."""
    texte = ('%.2f' % valeur).rstrip('0').rstrip('.')
    return texte if texte not in ('', '-0') else '0'


def _etapes(cascade):
    if not isinstance(cascade, dict):
        return []
    return [e for e in cascade.get('etapes') or () if isinstance(e, dict)]


def _est_nombre(valeur):
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


def echelle_px_par_point(etapes, hauteur_trace=HAUTEUR_TRACE_PX):
    """Pixels par point de pourcentage : la plus grande part SERVIE remplit le
    tracé. ``0`` quand aucune part n'est non nulle (rien à dessiner)."""
    parts = [abs(e['perte_pct']) for e in etapes
             if _est_nombre(e.get('perte_pct'))]
    plus_grande = max(parts) if parts else 0
    return hauteur_trace / plus_grande if plus_grande else 0.0


def _libelles(langue):
    from .documents.libelles_document import libelle

    return {code: libelle(code, langue) for code in (
        'pertes', 'irradiance_incidente', 'energie_livree', 'poste_omis',
        'gain', 'source_non_renseignee')}


def _energie_livree(etapes):
    for etape in reversed(etapes):
        if etape.get('kwh_apres') is not None:
            return etape['kwh_apres']
    return None


def _texte(x, y, contenu, *, taille=9, ancre='middle', couleur=_NOIR,
           gras=False, transformation=''):
    return ('<text x="%s" y="%s" font-size="%s" text-anchor="%s" fill="%s"%s'
            '%s>%s</text>' % (_n(x), _n(y), taille, ancre, couleur,
                              ' font-weight="bold"' if gras else '',
                              (' transform="%s"' % transformation)
                              if transformation else '', escape(contenu)))


def svg_de_cascade(cascade, *, largeur_mm=LARGEUR_DEFAUT_MM, langue='fr'):
    """Le SVG AUTONOME de la cascade — aucune part recalculée.

    Lève ``DiagrammeRefuse`` (champ ``cascade``) quand la cascade est absente
    ou vide : un diagramme vide se lirait « aucune perte ».
    """
    from .rapport import nombre_tel_que_servi

    etapes = _etapes(cascade)
    if not etapes:
        raise DiagrammeRefuse(
            "Aucune cascade de pertes produite pour ce calepinage : le "
            "diagramme se dessine depuis la simulation (onglet Production), "
            "jamais depuis une liste de postes sans ordre d'application.")
    textes = _libelles(langue)
    largeur = px_de_mm(largeur_mm)
    hauteur = MARGE_HAUTE_PX + HAUTEUR_TRACE_PX + ZONE_LIBELLES_PX
    base = MARGE_HAUTE_PX + HAUTEUR_TRACE_PX
    colonnes = len(etapes) + 2                      # + les deux bornes
    pas = (largeur - 2 * MARGE_LATERALE_PX) / colonnes
    epaisseur = pas * 0.62
    echelle = echelle_px_par_point(etapes)

    morceaux = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        'width="%spx" height="%spx" viewBox="0 0 %s %s" '
        'font-family="%s" data-px-par-point="%s" data-hauteur-trace="%s">'
        % (_n(largeur), _n(hauteur), _n(largeur), _n(hauteur), _POLICE,
           repr(float(echelle)), _n(HAUTEUR_TRACE_PX)),
        '<title>%s</title>' % escape(textes['pertes']),
        '<defs><pattern id="%s" patternUnits="userSpaceOnUse" width="6" '
        'height="6" patternTransform="rotate(45)"><rect x="0" y="0" '
        'width="6" height="6" fill="%s" /><line x1="0" y1="0" x2="0" y2="6" '
        'stroke="%s" stroke-width="2" /></pattern></defs>'
        % (ID_HACHURE, _GRIS_FOND, _GRIS_TEXTE),
        '<rect x="0" y="0" width="%s" height="%s" fill="#ffffff" />'
        % (_n(largeur), _n(hauteur)),
        '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
        'stroke-width="1" />' % (_n(MARGE_LATERALE_PX), _n(base),
                                 _n(largeur - MARGE_LATERALE_PX), _n(base),
                                 _GRIS_TRAIT),
    ]

    def centre(rang):
        return MARGE_LATERALE_PX + pas * (rang + 0.5)

    def libelle_sous(rang, texte):
        x = centre(rang)
        return _texte(x + 3, base + 6, texte, taille=8, ancre='end',
                      transformation='rotate(-90 %s %s)'
                      % (_n(x + 3), _n(base + 6)))

    # Les deux BORNES : des valeurs LUES, jamais des barres de la cascade.
    bornes = ((0, textes['irradiance_incidente'], etapes[0].get('kwh_avant')),
              (colonnes - 1, textes['energie_livree'],
               _energie_livree(etapes)))
    for rang, texte, kwh in bornes:
        x = centre(rang)
        morceaux.append(
            '<rect class="borne" x="%s" y="%s" width="%s" height="%s" '
            'fill="none" stroke="%s" stroke-width="1" stroke-dasharray="3 2" '
            '/>' % (_n(x - epaisseur / 2), _n(MARGE_HAUTE_PX),
                    _n(epaisseur), _n(HAUTEUR_TRACE_PX), _GRIS_TRAIT))
        morceaux.append(_texte(x, MARGE_HAUTE_PX - 6, '%s kWh'
                               % nombre_tel_que_servi(kwh, langue),
                               taille=8, gras=True))
        morceaux.append(libelle_sous(rang, texte))

    for index, etape in enumerate(etapes, start=1):
        x = centre(index)
        code = str(etape.get('etape') or '')
        non_source = not str(etape.get('source') or '').strip()
        remplissage = ('url(#%s)' % ID_HACHURE) if non_source else _GRIS_TEXTE
        pct = etape.get('perte_pct')
        if _est_nombre(pct):
            haut = round(abs(pct) * echelle, 2)
            texte_pct = '%s %%' % nombre_tel_que_servi(pct, langue)
            if etape.get('gain'):
                texte_pct += ' (%s)' % textes['gain']
            morceaux.append(
                '<rect class="barre-poste%s" data-etape="%s" data-pct="%s" '
                'data-source="%s" x="%s" y="%s" width="%s" height="%s" '
                'fill="%s" stroke="%s" stroke-width="0.6" />'
                % (' gain' if etape.get('gain') else '',
                   escape(code, quote=True), repr(float(pct)),
                   'non' if non_source else 'oui', _n(x - epaisseur / 2),
                   _n(base - haut), _n(epaisseur), _n(haut), remplissage,
                   _NOIR))
            morceaux.append(_texte(x, base - haut - 4, texte_pct, taille=8))
        else:
            # Étape OMISE : une case hachurée et « omis », jamais « 0 % ».
            morceaux.append(
                '<rect class="barre-omise" data-etape="%s" data-source="%s" '
                'x="%s" y="%s" width="%s" height="8" fill="url(#%s)" '
                'stroke="%s" stroke-width="0.6" stroke-dasharray="2 1" />'
                % (escape(code, quote=True), 'non' if non_source else 'oui',
                   _n(x - epaisseur / 2), _n(base - 8), _n(epaisseur),
                   ID_HACHURE, _GRIS_TRAIT))
            morceaux.append(_texte(x, base - 12, textes['poste_omis'],
                                   taille=8, couleur=_GRIS_TEXTE))
        libelle = str(etape.get('libelle') or code)
        if non_source:
            libelle = '%s (%s)' % (libelle, textes['source_non_renseignee'])
        morceaux.append(libelle_sous(index, libelle))

    morceaux.append('</svg>')
    return '\n'.join(morceaux)


#: La déclaration d'espace de noms du fichier autonome.
_XMLNS = ' xmlns="http://www.w3.org/2000/svg"'


def svg_embarquable(svg):
    """Le même SVG, prêt à s'inclure dans un HTML : sans déclaration XML ni
    ``xmlns`` (l'analyseur HTML place d'office ``<svg>`` dans l'espace de
    noms SVG) — le document hôte ne porte ainsi aucune URI."""
    texte = svg or ''
    if texte.startswith('<?xml'):
        texte = texte.split('?>', 1)[1].lstrip()
    return texte.replace(_XMLNS, '', 1)


def svg_du_calepinage(calepinage, *, langue=None, largeur_mm=LARGEUR_DEFAUT_MM):
    """Le diagramme d'un calepinage, depuis le résultat SERVI (fraîcheur
    CALX70, pare-feu de montants du rapport) — lève ``DiagrammeRefuse`` ou
    ``rapport.RapportRefuse`` en nommant la donnée."""
    from .documents.libelles_document import langue_du_document
    from .rapport import resultat_du_rapport

    servi, _stocke = resultat_du_rapport(calepinage)
    return svg_de_cascade(servi.get('cascade'), largeur_mm=largeur_mm,
                          langue=langue_du_document(calepinage, langue))
