"""ACAL261 (C-ACAL-035/042/116) — la liste blanche de la proposition publique
emporte surfaces de pose, module de chaque pan, retraits et zones
d'exclusion — GÉOMÉTRIE SEULE, jamais un prix ni un identifiant produit.

``public_views._safe_roof_layout`` réel, sur un Devis en base ; la forme
suit ``contract_samples/proposal_data.json`` (``exemple_roof_layout_riche``).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_liste_blanche_3d_publique"
"""
import json
from pathlib import Path

from django.test import TestCase

from apps.ventes.public_views import _safe_roof_layout
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user)

CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
           / 'proposal_data.json')

LAYOUT = {
    'version': 2,
    'modules': [{'id': 'm550', 'produitId': 575, 'libelle': 'Jinko Tiger 550',
                 'source': 'fiche', 'longueurMm': 2279, 'largeurMm': 1134,
                 'pmaxWc': 550, 'prix_vente': 3500, 'prix_achat': 2100}],
    'zones': [{'id': 'z1', 'label': 'Pan sud', 'vertices': [[0, 0], [1, 1]],
               'geometry': {'moduleId': 'm550', 'mode': 'free',
                            'azimuthDeg': 180, 'tiltDeg': 15, 'count': 2,
                            'panels': [{'cx': 1.0, 'cy': 2.0,
                                        'angleDeg': 17},
                                       {'cx': 3.0, 'cy': 2.0,
                                        'angleDeg': 17, 'marge': 12}]}}],
    'setbacksM': {'lateralM': 2, 'extremityM': 0.5, 'parapetM': 0.3,
                  'jointM': 0.02, 'prix': 99},
    'exclusionZones': [{'id': 'ex1', 'nature': 'INTERDITE',
                        'vertices': [[1, 1], [2, 1], [2, 2]],
                        'setbackM': 0.3, 'marge': 5}],
    'poseSurfaces': [{'id': 'omb1', 'kind': 'ombriere', 'label': 'Carport',
                      'contourM': [[0, 0], [20, 0], [20, 10], [0, 10]],
                      'tiltDeg': 10, 'rowAzimuthDeg': 90,
                      'moduleLongM': 2.279, 'moduleCourtM': 1.134,
                      'moduleWc': 550, 'produitId': 575,
                      'engine': {'modules': 60, 'rowPitchM': 3.1,
                                 'tables': [{'x0': 0.5, 'x1': 9.5,
                                             'y0': 0.5, 'y1': 3.6}],
                                 'prix_ht': 120000}}],
}

INTERDITES = ('prix', 'prix_vente', 'prix_achat', 'marge', 'produitId',
              'libelle', 'Jinko', 'prix_ht')


def _cles(noeud):
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            yield cle
            yield from _cles(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            yield from _cles(valeur)


class ListeBlanche3DPublique(TestCase):

    def setUp(self):
        company = make_company()
        self.devis = make_devis(company, make_user(company),
                                make_client(company),
                                [('Panneau mono 550W', '62', '1100')])
        self.devis.roof_layout = LAYOUT
        self.devis.save(update_fields=['roof_layout'])

    def test_modules_surfaces_retraits_exclusions_publies(self):
        safe = _safe_roof_layout(self.devis)
        self.assertEqual(safe['modules'], [
            {'id': 'm550', 'longueurMm': 2279, 'largeurMm': 1134,
             'pmaxWc': 550}])
        geo = safe['zones'][0]['geometry']
        self.assertEqual((geo['moduleId'], geo['mode']), ('m550', 'free'))
        self.assertEqual([p['angleDeg'] for p in geo['panels']], [17, 17])
        self.assertEqual(safe['setbacksM'], {
            'lateralM': 2, 'extremityM': 0.5, 'parapetM': 0.3,
            'jointM': 0.02})
        self.assertEqual(safe['exclusionZones'], [
            {'id': 'ex1', 'nature': 'INTERDITE',
             'vertices': [[1, 1], [2, 1], [2, 2]], 'setbackM': 0.3}])
        surface, = safe['poseSurfaces']
        self.assertEqual(surface['kind'], 'ombriere')
        self.assertEqual(surface['engine']['modules'], 60)
        self.assertEqual(surface['engine']['tables'],
                         [{'x0': 0.5, 'x1': 9.5, 'y0': 0.5, 'y1': 3.6}])
        self.assertEqual(surface['moduleWc'], 550)
        # Les clés publiées sont celles du contrat partagé.
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        riche = contrat['exemple_roof_layout_riche']['roof_layout']
        for cle in ('modules', 'setbacksM', 'exclusionZones', 'poseSurfaces'):
            self.assertIn(cle, riche)
            self.assertIn(cle, safe)
        self.assertLessEqual(set(surface), set(riche['poseSurfaces'][0]))
        self.assertLessEqual(set(safe['modules'][0]), set(riche['modules'][0]))

    def test_aucun_prix_ni_produit(self):
        safe = _safe_roof_layout(self.devis)
        cles = set(_cles(safe))
        for interdite in INTERDITES:
            self.assertNotIn(interdite, cles)
        texte = json.dumps(safe, ensure_ascii=False)
        self.assertNotIn('Jinko', texte)
        self.assertNotIn('575', texte)

    def test_ancien_devis_inchange(self):
        self.devis.roof_layout = {'version': 2, 'zones': []}
        self.devis.save(update_fields=['roof_layout'])
        self.assertIsNone(_safe_roof_layout(self.devis))
