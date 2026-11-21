"""ACAL536 — l'export KML du calepinage, pour Google Earth.

Un ``Placemark`` par pan, par zone d'exclusion et par module POSÉ, dans l'ordre
KML ``lng,lat,0``. La géométrie est celle de la planche
(``services.planche.geometrie_de_planche``) : le KML, le DXF et le PDF ne
peuvent pas diverger. Un module dont l'emprise n'est pas SOURCÉE (cotes,
azimut, pente ou pose absents) est écrit en ``Point`` : on ne dessine jamais un
rectangle de taille plausible. Aucun prix, aucune donnée client.

XML par la bibliothèque standard ; aucun fichier n'est écrit sur le disque.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

__all__ = ['MIME_KML', 'exporter_kml']

MIME_KML = 'application/vnd.google-earth.kml+xml'

_ENTETE = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n')


def _coordonnees(points, projection):
    """``[(est, nord)]`` en mètres -> ``lng,lat,0`` (anneau refermé)."""
    geo = [projection.vers_geo(est, nord) for est, nord in points]
    if geo and geo[0] != geo[-1]:
        geo.append(geo[0])
    return ' '.join('%.8f,%.8f,0' % (lng, lat) for lat, lng in geo)


def _polygone(nom, points, projection):
    return ('<Placemark><name>%s</name><Polygon><outerBoundaryIs>'
            '<LinearRing><coordinates>%s</coordinates></LinearRing>'
            '</outerBoundaryIs></Polygon></Placemark>\n'
            % (escape(nom), _coordonnees(points, projection)))


def _point(nom, centre, projection):
    lat, lng = projection.vers_geo(*centre)
    return ('<Placemark><name>%s</name><Point><coordinates>%.8f,%.8f,0'
            '</coordinates></Point></Placemark>\n' % (escape(nom), lng, lat))


def exporter_kml(calepinage):
    """Le KML d'un ``Calepinage`` en OCTETS (utf-8). Lève ``PlancheRefusee``
    (champ ``roof_layout``) sans conception exploitable."""
    from .planche import (
        PlancheRefusee, _projection, coins_du_module, geometrie_de_planche,
    )

    layout = getattr(calepinage, 'roof_layout', None)
    geometrie = geometrie_de_planche(layout)
    projection = _projection(layout)
    if projection is None:
        raise PlancheRefusee(
            "Le KML exige une conception géoréférencée (contour ou pans en "
            "latitude/longitude).", champ='roof_layout')
    titre = str(getattr(calepinage, 'titre', '') or 'Calepinage')
    morceaux = [_ENTETE, '<name>%s</name>\n' % escape(titre)]
    for pan in geometrie.get('pans') or ():
        if len(pan['points']) >= 3:
            morceaux.append(_polygone(
                pan.get('libelle') or 'Pan %s' % pan.get('repere'),
                pan['points'], projection))
    for zone in geometrie.get('zones_interdites') or ():
        morceaux.append(_polygone(
            "Zone d'exclusion %s" % (zone.get('libelle') or zone['repere']),
            zone['points'], projection))
    for pan in geometrie.get('pans') or ():
        for rang, centre in enumerate(pan.get('modules') or (), start=1):
            nom = 'Module %s-%d' % (pan.get('repere'), rang)
            coins = coins_du_module(pan, centre)
            morceaux.append(_polygone(nom, coins, projection) if coins
                            else _point(nom, centre, projection))
    morceaux.append('</Document>\n</kml>\n')
    return ''.join(morceaux).encode('utf-8')
