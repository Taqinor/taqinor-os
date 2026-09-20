"""CAL171 — la PLANCHE de calepinage cotée, rendue par le SERVEUR.

Le constat
==========
``PlancheAO`` existe, mais son PDF est un fichier **téléversé**
(``apps/ao/services.py`` ``store_attachment(fichier)``) : l'ERP ne RENDAIT
aucune planche. La seule image de calepinage qu'il produisait est l'affiche
client ``Devis.roof_image`` (``apps/ventes/quote_engine/builder.py``) — sans
cotes et sans cartouche. Une équipe de pose n'a donc jamais eu de plan.

Ce que fait ce module, et ce qu'il ne fait pas
===============================================
* il COMPOSE un SVG A3 paysage depuis ``Calepinage.roof_layout`` (contour,
  pans, obstacles, modules posés) — la géométrie STOCKÉE, jamais un tracé
  reconstitué ;
* le PDF est obtenu en encapsulant ce SVG dans un HTML rendu par
  ``core.pdf.render_pdf`` (ARC11) : jamais un ``import weasyprint`` ici, jamais
  une seconde plomberie PDF ;
* **le PNG n'est pas produit ici.** Aucun rasteriseur SVG n'est installé
  (WeasyPrint 62.3 n'a plus de sortie PNG ; ni ``cairosvg`` ni ``svglib`` ne
  sont des dépendances). Le PNG est la conversion NAVIGATEUR du SVG, par
  ``frontend/src/features/ao/studio/svgToPng.js``. Aucun accès réseau n'a lieu
  au rendu : le SVG est autonome, sans police distante ni image externe ;
* il ne RECALCULE rien. Aucune arithmétique métier (compter des modules,
  convertir des kWc) : les longueurs cotées sont MESURÉES sur la géométrie
  projetée, ce qui est le propos même d'une cote, et rien d'autre n'est dérivé.

Le refus plutôt que le blanc
=============================
Un calepinage sans conception ne rend pas une feuille vide : il lève
``PlancheRefusee`` en NOMMANT la donnée manquante (``champ``). Une planche
blanche remise à une équipe est un défaut invisible ; un refus ne l'est pas
(même doctrine qu'``AOF134``).

La projection
=============
``roof_layout`` mélange trois repères — ``outline`` en ``[lat, lng]``,
``zones[].vertices`` en ``[lng, lat]`` (convention GeoJSON du lecteur de
cartes) et ``zones[].geometry.panels`` en mètres ENU autour d'une ``origin``
``[lng, lat]``. Le piège est traité une fois pour toutes par
``core.calepinage.adaptateurs.villa.Projection`` (moteur pur, partagé) :
l'ordre des couples est un ARGUMENT EXPLICITE, jamais deviné — un contour
retourné est plausible à l'œil et faux au mètre près.
"""
from __future__ import annotations

from html import escape

__all__ = [
    'FORMAT_A3_MM', 'MARGE_MM', 'LARGEUR_BANDEAU_MM',
    'PlancheRefusee', 'dimensions_module', 'geometrie_de_planche',
    'svg_de_planche', 'html_de_planche', 'rendre_planche_svg',
    'rendre_planche_pdf', 'nom_de_fichier',
]

#: A3 PAYSAGE, en millimètres — le format des planches remises (même choix que
#: ``core.calepinage.rendu.feuille.FORMAT_DEFAUT``).
FORMAT_A3_MM = (420.0, 297.0)

#: Marge de feuille et largeur du bandeau latéral (cartouche + légende CAL172).
MARGE_MM = 12.0
LARGEUR_BANDEAU_MM = 84.0

#: Épaisseurs de trait (mm) — le contour relevé est le trait fort.
TRAIT_CONTOUR = 0.7
TRAIT_PAN = 0.4
TRAIT_MODULE = 0.15
TRAIT_COTE = 0.25

#: Palette SOBRE, reprise de la planche du moteur (``rendu/couleurs.py``) :
#: noir pour la géométrie relevée, vert pour les modules posés, orange pour ce
#: qui reste à confirmer.
NOIR = '#111111'
VERT_MODULE = '#2e7d32'
VERT_MODULE_FOND = '#c8e6c9'
GRIS_PAN = '#f4f4f4'
ORANGE = '#ef6c00'
GRIS_TEXTE = '#444444'


class PlancheRefusee(ValueError):
    """Le rendu refuse de sortir, et il dit QUELLE donnée lui manque.

    ``champ`` nomme la saisie fautive pour que l'appelant HTTP la reporte telle
    quelle (règle fondateur « l'erreur pointe le champ », 08/09).
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


# ── Lecture TOLÉRANTE du document de conception ─────────────────────────────
#
# Les documents réellement en base sont hétérogènes (le schéma v2 le dit et
# l'assume) : certains ne portent que ``{zones: […]}``, d'autres un
# ``_pans_geometry`` interne. On lit donc ce qu'on reconnaît et on IGNORE le
# reste — mais on ne DEVINE jamais une valeur absente.

def _nombre(valeur):
    """``valeur`` en float, ou ``None`` — jamais un défaut inventé."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return nombre if nombre == nombre and abs(nombre) != float('inf') else None


def _couple(point, ordre):
    """``point`` -> ``(lat, lng)`` selon l'ORDRE déclaré. Jamais deviné."""
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    a, b = _nombre(point[0]), _nombre(point[1])
    if a is None or b is None:
        return None
    return (a, b) if ordre == 'latlng' else (b, a)


def _points_geo(brut, ordre):
    """Liste de couples -> ``[(lat, lng)]``, les points illisibles retirés."""
    if not isinstance(brut, (list, tuple)):
        return []
    lus = [_couple(point, ordre) for point in brut]
    return [point for point in lus if point is not None]


def _zones(roof_layout):
    zones = (roof_layout or {}).get('zones')
    return [z for z in zones if isinstance(z, dict)] \
        if isinstance(zones, (list, tuple)) else []


def _projection(roof_layout):
    """Ancre la projection ENU sur le barycentre de la géométrie relevée.

    Priorité au CONTOUR (``outline``, en ``[lat, lng]``), puis aux sommets des
    pans (``[lng, lat]``) : le repère doit être stable d'un rendu à l'autre
    pour deux documents identiques, sinon deux planches du même toit ne se
    superposeraient pas.
    """
    from core.calepinage.adaptateurs.villa import Projection

    points = _points_geo((roof_layout or {}).get('outline'), 'latlng')
    if not points:
        for zone in _zones(roof_layout):
            points.extend(_points_geo(zone.get('vertices'), 'lnglat'))
    if not points:
        return None
    lat0 = sum(p[0] for p in points) / len(points)
    lng0 = sum(p[1] for p in points) / len(points)
    return Projection(lat0_deg=lat0, lng0_deg=lng0)


# ── Les dimensions du module : SOURCÉES, ou absentes ────────────────────────

def dimensions_module(roof_layout):
    """``(long_m, court_m)`` du module, ou ``None`` si rien ne les SOURCE.

    Le document de conception ne porte PAS les dimensions physiques du module :
    il ne porte que sa puissance (``panelWatt``) et les CENTRES des modules
    posés. On ne les invente donc pas — on les retrouve dans les kits DÉCLARÉS
    du moteur (``core.calepinage.types``) quand la puissance correspond, et on
    rend ``None`` sinon. Un module sans dimension connue est figuré par son
    centre (voir ``svg_de_planche``), jamais par un rectangle de taille
    plausible : une emprise fausse au demi-mètre se lit comme une emprise
    vraie.
    """
    from core.calepinage.types import (
        KIT_AO_PAYSAGE, KIT_AO_PORTRAIT, KIT_VILLA_720,
    )

    watt = _nombre((roof_layout or {}).get('panelWatt'))
    if watt is None:
        return None
    for kit in (KIT_VILLA_720, KIT_AO_PORTRAIT, KIT_AO_PAYSAGE):
        if abs(float(kit.puissance_module_wc) - watt) < 0.5:
            return (float(kit.module_long_m), float(kit.module_court_m))
    return None


# ── La GÉOMÉTRIE de planche : une projection en lecture seule ───────────────

def geometrie_de_planche(roof_layout):
    """``roof_layout`` -> géométrie PLANE en mètres, prête à dessiner.

    Rend ``{'contour', 'pans', 'obstacles', 'zones_interdites', 'etendue',
    'module_m'}``. Lève ``PlancheRefusee`` si le document ne porte AUCUNE
    géométrie exploitable — jamais une feuille blanche.
    """
    projection = _projection(roof_layout)
    if projection is None:
        raise PlancheRefusee(
            "Aucune géométrie enregistrée : la planche se compose du contour "
            "et des pans STOCKÉS, jamais d'un tracé reconstitué. Enregistrez "
            "la conception avant de demander la planche.",
            champ='roof_layout')

    def local(lat, lng):
        return projection.vers_local(lat, lng)

    contour = [local(lat, lng) for lat, lng
               in _points_geo((roof_layout or {}).get('outline'), 'latlng')]

    module_m = dimensions_module(roof_layout)
    pans, obstacles = [], []
    for rang, zone in enumerate(_zones(roof_layout), start=1):
        points = [local(lat, lng)
                  for lat, lng in _points_geo(zone.get('vertices'), 'lnglat')]
        geometrie = zone.get('geometry') \
            if isinstance(zone.get('geometry'), dict) else {}
        modules = _modules_du_pan(geometrie, local)
        pan = {
            'repere': str(zone.get('id') or 'PAN-%d' % rang),
            'libelle': str(zone.get('label') or ''),
            'points': points,
            # Chaque grandeur d'orientation est OMISE quand elle est absente :
            # un pan sans azimut connu n'affiche pas « 0° » (CAL172).
            'azimut_deg': _nombre(geometrie.get('azimuthDeg')
                                  if 'azimuthDeg' in geometrie
                                  else zone.get('facingAzimuthDeg')),
            'pente_deg': _nombre(geometrie.get('tiltDeg')
                                 if 'tiltDeg' in geometrie
                                 else zone.get('pitchDeg')),
            'modules': modules,
            'batiment': str(zone.get('buildingId') or ''),
        }
        pans.append(pan)
        obstacles.extend(_obstacles_du_pan(zone, local, rang))

    zones_interdites = []
    brutes = (roof_layout or {}).get('exclusionZones')
    for rang, zone in enumerate(brutes if isinstance(brutes, (list, tuple))
                                else [], start=1):
        if not isinstance(zone, dict):
            continue
        points = [local(lat, lng)
                  for lat, lng in _points_geo(zone.get('vertices'), 'lnglat')]
        if len(points) < 3:
            continue
        zones_interdites.append({
            'repere': str(zone.get('id') or 'ZONE-%d' % rang),
            'libelle': str(zone.get('label') or ''),
            'nature': str(zone.get('nature') or ''),
            'points': points,
        })

    geometrie = {
        'contour': contour,
        'pans': pans,
        'obstacles': obstacles,
        'zones_interdites': zones_interdites,
        'module_m': module_m,
    }
    geometrie['etendue'] = _etendue(geometrie)
    if geometrie['etendue'] is None:
        raise PlancheRefusee(
            "La conception enregistrée ne porte aucun point exploitable : ni "
            "contour, ni pan, ni module posé. La planche ne se rend pas à "
            "partir d'une géométrie vide.",
            champ='roof_layout')
    return geometrie


def _modules_du_pan(geometrie, local):
    """Centres des modules POSÉS, en mètres dans le repère de la planche.

    ``panels`` porte des centres ENU relatifs à ``origin`` (``[lng, lat]``) :
    on replace donc l'origine dans le repère commun avant d'y ajouter les
    décalages. Ce sont les cellules RÉELLEMENT OCCUPÉES (PV27) — jamais les
    ``count`` premières d'un pavage, qui effaceraient une édition manuelle.
    """
    panneaux = geometrie.get('panels')
    if not isinstance(panneaux, (list, tuple)):
        return []
    origine = _couple(geometrie.get('origin'), 'lnglat')
    if origine is None:
        return []
    est0, nord0 = local(origine[0], origine[1])
    centres = []
    for panneau in panneaux:
        if not isinstance(panneau, dict):
            continue
        cx, cy = _nombre(panneau.get('cx')), _nombre(panneau.get('cy'))
        if cx is None or cy is None:
            continue
        centres.append((est0 + cx, nord0 + cy))
    return centres


def _obstacles_du_pan(zone, local, rang_pan):
    """Obstacles relevés DANS un pan -> rectangles centrés, en mètres."""
    brut = zone.get('obstacles')
    obstacles = []
    for rang, obstacle in enumerate(
            brut if isinstance(brut, (list, tuple)) else [], start=1):
        if not isinstance(obstacle, dict):
            continue
        lat = _nombre(obstacle.get('centerLat'))
        lng = _nombre(obstacle.get('centerLng'))
        # ``lengthM`` est l'étendue NORD-SUD, ``widthM`` l'étendue EST-OUEST
        # (schéma v2) : les confondre pivote l'obstacle de 90°.
        nord_sud = _nombre(obstacle.get('lengthM'))
        est_ouest = _nombre(obstacle.get('widthM'))
        if None in (lat, lng, nord_sud, est_ouest):
            continue
        est, nord = local(lat, lng)
        obstacles.append({
            'repere': str(obstacle.get('id') or 'OBS-%d-%d' % (rang_pan, rang)),
            'type': str(obstacle.get('type') or ''),
            'x': est - est_ouest / 2.0,
            'y': nord - nord_sud / 2.0,
            'largeur': est_ouest,
            'hauteur': nord_sud,
            'hauteur_m': _nombre(obstacle.get('heightM')),
            'provenance': str(obstacle.get('provenance') or ''),
        })
    return obstacles


def _etendue(geometrie):
    """``(xmin, ymin, xmax, ymax)`` de tout ce qui sera dessiné, ou ``None``."""
    xs, ys = [], []

    def ajouter(points):
        for x, y in points:
            xs.append(x)
            ys.append(y)

    ajouter(geometrie['contour'])
    for pan in geometrie['pans']:
        ajouter(pan['points'])
        ajouter(pan['modules'])
    for zone in geometrie['zones_interdites']:
        ajouter(zone['points'])
    for obstacle in geometrie['obstacles']:
        ajouter([(obstacle['x'], obstacle['y']),
                 (obstacle['x'] + obstacle['largeur'],
                  obstacle['y'] + obstacle['hauteur'])])
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


# ── Mise en page SVG ────────────────────────────────────────────────────────

def _cadre_de_dessin():
    """``(x, y, largeur, hauteur)`` en mm de la zone de dessin (hors bandeau)."""
    largeur = FORMAT_A3_MM[0] - 2 * MARGE_MM - LARGEUR_BANDEAU_MM
    hauteur = FORMAT_A3_MM[1] - 2 * MARGE_MM
    return (MARGE_MM, MARGE_MM, largeur, hauteur)


def echelle_de_dessin(etendue, cadre=None):
    """Millimètres de feuille par mètre de terrain — la plus grande qui tienne.

    L'échelle n'est jamais ANNONCÉE en fraction (« 1/200 ») : un dossier
    imprimé n'est pas garanti à l'échelle (photocopie, réduction A3->A4), une
    mention chiffrée y devient fausse au premier tirage. C'est une BARRE
    d'échelle métrique qui est dessinée (CAL172).
    """
    x0, y0, x1, y1 = etendue
    cadre = cadre or _cadre_de_dessin()
    largeur_m = max(x1 - x0, 0.001)
    hauteur_m = max(y1 - y0, 0.001)
    return min(cadre[2] / largeur_m, cadre[3] / hauteur_m)


def _transformation(etendue, cadre=None):
    """``(x_m, y_m) -> (x_mm, y_mm)`` — le Y du SVG descend, celui du terrain monte."""
    cadre = cadre or _cadre_de_dessin()
    echelle = echelle_de_dessin(etendue, cadre)
    x0, y0, x1, y1 = etendue
    largeur_mm = (x1 - x0) * echelle
    hauteur_mm = (y1 - y0) * echelle
    # Le dessin est CENTRÉ dans son cadre ; le Y du SVG descend quand celui du
    # terrain monte, donc ``y0`` (le sud) se pose EN BAS.
    ox = cadre[0] + (cadre[2] - largeur_mm) / 2.0
    oy = cadre[1] + (cadre[3] - hauteur_mm) / 2.0

    def vers_feuille(point):
        x, y = point
        return (ox + (x - x0) * echelle,
                oy + hauteur_mm - (y - y0) * echelle)

    return vers_feuille, echelle


def _n(valeur):
    """Un nombre SVG court et stable (jamais de notation scientifique)."""
    return ('%.3f' % float(valeur)).rstrip('0').rstrip('.') or '0'


def _polygone(points, vers_feuille, *, contour, remplissage='none',
              trait=TRAIT_PAN, tirets=''):
    if len(points) < 2:
        return ''
    chaine = ' '.join('%s,%s' % tuple(_n(c) for c in vers_feuille(p))
                      for p in points)
    style = ('fill="%s" stroke="%s" stroke-width="%s"'
             % (remplissage, contour, _n(trait)))
    if tirets:
        style += ' stroke-dasharray="%s"' % tirets
    return '<polygon points="%s" %s />' % (chaine, style)


def texte_de_longueur(metres):
    """« 12,34 m » — la cote, écrite à la française, JAMAIS arrondie à l'entier."""
    return ('%.2f' % float(metres)).replace('.', ',') + ' m'


def _cote_horizontale(x0, x1, y, vers_feuille, *, couleur=NOIR):
    """Une cote MESURÉE sur la géométrie projetée (m), tracée sous l'objet."""
    a, b = vers_feuille((x0, y)), vers_feuille((x1, y))
    milieu = ((a[0] + b[0]) / 2.0, a[1] + 4.0)
    return (
        '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s" />'
        '<text x="%s" y="%s" font-size="3.2" text-anchor="middle" fill="%s">'
        '%s</text>'
    ) % (_n(a[0]), _n(a[1] + 6.0), _n(b[0]), _n(b[1] + 6.0), couleur,
         _n(TRAIT_COTE), _n(milieu[0]), _n(a[1] + 5.2), couleur,
         escape(texte_de_longueur(abs(x1 - x0))))


def _cote_verticale(y0, y1, x, vers_feuille, *, couleur=NOIR):
    a, b = vers_feuille((x, y0)), vers_feuille((x, y1))
    milieu_y = (a[1] + b[1]) / 2.0
    return (
        '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s" />'
        '<text x="%s" y="%s" font-size="3.2" text-anchor="middle" fill="%s" '
        'transform="rotate(-90 %s %s)">%s</text>'
    ) % (_n(a[0] - 6.0), _n(a[1]), _n(b[0] - 6.0), _n(b[1]), couleur,
         _n(TRAIT_COTE), _n(a[0] - 7.2), _n(milieu_y), couleur,
         _n(a[0] - 7.2), _n(milieu_y), escape(texte_de_longueur(abs(y1 - y0))))


def _dessin_des_modules(pan, vers_feuille, module_m):
    """Les modules POSÉS : rectangle quand l'emprise est SOURCÉE, sinon croix."""
    morceaux = []
    for centre in pan['modules']:
        if module_m is None:
            # Emprise inconnue -> le module est figuré par son CENTRE. On ne
            # dessine pas un rectangle de taille plausible : il se lirait comme
            # une emprise mesurée.
            x, y = vers_feuille(centre)
            morceaux.append(
                '<circle cx="%s" cy="%s" r="0.7" fill="%s" />'
                % (_n(x), _n(y), VERT_MODULE))
            continue
        demi_l, demi_c = module_m[0] / 2.0, module_m[1] / 2.0
        coins = ((centre[0] - demi_l, centre[1] - demi_c),
                 (centre[0] + demi_l, centre[1] - demi_c),
                 (centre[0] + demi_l, centre[1] + demi_c),
                 (centre[0] - demi_l, centre[1] + demi_c))
        morceaux.append(_polygone(coins, vers_feuille, contour=VERT_MODULE,
                                  remplissage=VERT_MODULE_FOND,
                                  trait=TRAIT_MODULE))
    return morceaux


def svg_de_planche(geometrie, *, titre='', sous_titre='', bandeau=()):
    """Compose le SVG A3 paysage de la planche. Ne recalcule aucune grandeur.

    ``bandeau`` est une suite de lignes de texte DÉJÀ composées par l'appelant
    (CAL172/CAL173 : légende, nord, échelle, empreinte). Ce module ne rédige
    aucune affirmation — il met en page.
    """
    etendue = geometrie.get('etendue')
    if not etendue:
        raise PlancheRefusee(
            "Géométrie de planche vide : rien à dessiner.", champ='roof_layout')
    vers_feuille, echelle = _transformation(etendue)
    largeur, hauteur = FORMAT_A3_MM
    morceaux = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        'width="%smm" height="%smm" viewBox="0 0 %s %s">'
        % (_n(largeur), _n(hauteur), _n(largeur), _n(hauteur)),
        '<title>%s</title>' % escape(titre or 'Planche de calepinage'),
        '<rect x="0" y="0" width="%s" height="%s" fill="#ffffff" />'
        % (_n(largeur), _n(hauteur)),
    ]

    for zone in geometrie['zones_interdites']:
        morceaux.append(_polygone(zone['points'], vers_feuille, contour=ORANGE,
                                  remplissage='none', tirets='1.5 1'))
    for pan in geometrie['pans']:
        morceaux.append(_polygone(pan['points'], vers_feuille, contour=NOIR,
                                  remplissage=GRIS_PAN))
    morceaux.append(_polygone(geometrie['contour'], vers_feuille, contour=NOIR,
                              trait=TRAIT_CONTOUR))
    for pan in geometrie['pans']:
        morceaux.extend(_dessin_des_modules(pan, vers_feuille,
                                            geometrie.get('module_m')))
    for obstacle in geometrie['obstacles']:
        coins = ((obstacle['x'], obstacle['y']),
                 (obstacle['x'] + obstacle['largeur'], obstacle['y']),
                 (obstacle['x'] + obstacle['largeur'],
                  obstacle['y'] + obstacle['hauteur']),
                 (obstacle['x'], obstacle['y'] + obstacle['hauteur']))
        # Un obstacle dont la provenance N'EST PAS un relevé est tireté : il
        # ne se présente pas avec l'aplomb d'un obstacle mesuré.
        releve = obstacle['provenance'] in ('RELEVE', 'MESURE', '')
        morceaux.append(_polygone(
            coins, vers_feuille, contour=NOIR if releve else ORANGE,
            remplissage='#ffffff', tirets='' if releve else '1.2 0.8'))

    # Les cotes d'ENCOMBREMENT, mesurées sur la géométrie projetée.
    x0, y0, x1, y1 = etendue
    morceaux.append(_cote_horizontale(x0, x1, y0, vers_feuille))
    morceaux.append(_cote_verticale(y0, y1, x0, vers_feuille))

    morceaux.extend(_bandeau_svg(titre, sous_titre, bandeau, echelle,
                                 vers_feuille, etendue))
    morceaux.append('</svg>')
    return '\n'.join(m for m in morceaux if m)


def _bandeau_svg(titre, sous_titre, lignes, echelle, vers_feuille, etendue):
    """Le bandeau latéral : titre, sous-titre et les lignes de l'appelant."""
    x = FORMAT_A3_MM[0] - MARGE_MM - LARGEUR_BANDEAU_MM + 3.0
    morceaux = [
        '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s" />'
        % (_n(x - 3.0), _n(MARGE_MM), _n(x - 3.0),
           _n(FORMAT_A3_MM[1] - MARGE_MM), GRIS_TEXTE, _n(TRAIT_COTE)),
    ]
    y = MARGE_MM + 6.0
    if titre:
        morceaux.append(
            '<text x="%s" y="%s" font-size="5" font-weight="bold" fill="%s">'
            '%s</text>' % (_n(x), _n(y), NOIR, escape(titre)))
        y += 5.5
    if sous_titre:
        morceaux.append('<text x="%s" y="%s" font-size="3.4" fill="%s">%s'
                        '</text>' % (_n(x), _n(y), GRIS_TEXTE,
                                     escape(sous_titre)))
        y += 6.0
    for ligne in lignes:
        morceaux.append('<text x="%s" y="%s" font-size="3.4" fill="%s">%s'
                        '</text>' % (_n(x), _n(y), NOIR, escape(str(ligne))))
        y += 4.6
    return morceaux


# ── Les sorties : SVG, puis PDF par la plomberie PARTAGÉE ───────────────────

def html_de_planche(svg):
    """Encapsule le SVG dans un HTML A3 paysage — le chemin éprouvé du dépôt.

    Aucune police distante, aucune image externe : le document est autonome,
    donc le rendu ne fait AUCUN accès réseau.
    """
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<title>Planche de calepinage</title><style>'
        '@page{size:A3 landscape;margin:0;}'
        'html,body{margin:0;padding:0;background:#fff;}'
        'svg{display:block;width:100%;height:auto;}'
        '</style></head><body>' + svg + '</body></html>'
    )


def nom_de_fichier(calepinage, extension):
    """``calepinage-<pk>-<titre assaini>.<ext>`` — jamais un nom d'utilisateur brut."""
    titre = (getattr(calepinage, 'titre', '') or '').strip().lower()
    assaini = ''.join(c if c.isalnum() else '-' for c in titre).strip('-')
    while '--' in assaini:
        assaini = assaini.replace('--', '-')
    base = 'calepinage-%s' % (getattr(calepinage, 'pk', '') or 'sans-numero')
    return '%s%s.%s' % (base, '-' + assaini[:60] if assaini else '', extension)


def rendre_planche_svg(calepinage, **options):
    """SVG de la planche d'un ``Calepinage``. Lève ``PlancheRefusee`` si besoin."""
    geometrie = geometrie_de_planche(getattr(calepinage, 'roof_layout', None))
    return svg_de_planche(
        geometrie,
        titre=options.pop('titre', None) or str(calepinage),
        sous_titre=options.pop('sous_titre', ''),
        bandeau=options.pop('bandeau', ()))


def rendre_planche_pdf(calepinage, *, company=None, **options):
    """Octets PDF de la planche, via ``core.pdf.render_pdf`` (ARC11).

    JAMAIS un import direct de WeasyPrint : ``check_platform.py`` refuserait le
    fichier, et la plomberie PDF n'a pas à être re-codée par pièce. L'import
    est FONCTION-LOCAL — la bibliothèque est lourde et absente de certains
    postes de développement.
    """
    from core.pdf import render_pdf

    svg = rendre_planche_svg(calepinage, **options)
    return render_pdf(html=html_de_planche(svg),
                      company=company or getattr(calepinage, 'company', None))
