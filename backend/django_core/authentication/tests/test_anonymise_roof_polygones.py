"""ERR-ANON-ROOF-POLYGONES — l'export anonymisé ne laisse passer AUCUNE
coordonnée de toit précise.

``Devis.roof_layout`` porte le contour du toit du client (``outline`` en
``[[lat, lng], …]``, ``zones[].vertices`` en ``[[lng, lat], …]``, obstacles) :
à pleine précision, il désigne le domicile. Seules les clés nommées lat/lng
étaient arrondies ; les paires nues d'un polygone sortaient telles quelles.
Garde : après ``serialise_value`` (le chemin réel de ``build_export``), aucun
nombre du JSON géométrique n'a plus de 3 décimales — les nombres métier
(surface, puissance, compte de panneaux) restent intacts.
"""
import json
import re

from django.test import SimpleTestCase

from authentication import anonymise

# Toit réel type (Casablanca), aux deux conventions de serializeLayout.
CONTOUR = [[-7.6187423, 33.5731104], [-7.6185911, 33.5731876],
           [-7.6185102, 33.5730551], [-7.6186733, 33.5729803]]
ROOF_LAYOUT = {
    'version': 2,
    'pin': {'lat': 33.5730912, 'lng': -7.6186301},
    'outline': [[lat, lng] for lng, lat in CONTOUR],
    'zones': [{
        'id': 'auto',
        'label': 'Toit du client',
        'vertices': [list(p) for p in CONTOUR],
        'obstacles': [{'id': 'o1', 'vertices': [list(p) for p in CONTOUR[:3]]}],
        'neededPanels': 12,
        'result': {'count': 12, 'kwc': 6.6, 'areaM2': 81.37},
    }],
    # Paires nues hors clé géométrique nommée : le filet générique les prend.
    'traces': [[-7.6187423, 33.5731104]],
}

_PRECIS = re.compile(r'-?\d+\.\d{4,}')


def _devis_roof_layout_field():
    model = anonymise.model_for('ventes.Devis')
    return model, model._meta.get_field('roof_layout')


class RoofPolygonesAnonymisesTest(SimpleTestCase):

    def _export(self, value):
        _model, field = _devis_roof_layout_field()
        return anonymise.serialise_value(
            'ventes.Devis', field, value, anonymise.Scrambler())

    def test_aucune_coordonnee_a_plus_de_3_decimales(self):
        out = self._export(ROOF_LAYOUT)
        texte = json.dumps(out)
        self.assertFalse(_PRECIS.findall(texte), texte)

    def test_sommets_arrondis_au_dixieme_et_forme_conservee(self):
        out = self._export(ROOF_LAYOUT)
        self.assertEqual(out['outline'][0], [33.6, -7.6])
        self.assertEqual(out['zones'][0]['vertices'][0], [-7.6, 33.6])
        self.assertEqual(len(out['zones'][0]['vertices']), len(CONTOUR))
        self.assertEqual(
            out['zones'][0]['obstacles'][0]['vertices'][1], [-7.6, 33.6])
        self.assertEqual(out['traces'][0], [-7.6, 33.6])

    def test_nombres_metier_gardes(self):
        out = self._export(ROOF_LAYOUT)
        zone = out['zones'][0]
        self.assertEqual(zone['neededPanels'], 12)
        self.assertEqual(zone['result'],
                         {'count': 12, 'kwc': 6.6, 'areaM2': 81.37})
        self.assertEqual(out['version'], 2)

    def test_paires_non_geographiques_intactes(self):
        # Une paire de dimensions courtes (2 décimales) n'est pas un point GPS.
        scr = anonymise.Scrambler()
        self.assertEqual(scr.scrub_json({'dims': [1.65, 1.13]}),
                         {'dims': [1.65, 1.13]})
