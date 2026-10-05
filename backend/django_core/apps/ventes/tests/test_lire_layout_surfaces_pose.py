"""ERR-QAH-CALEPINAGE-SOL-DEVIS-422 — un champ au sol enregistré est COMPTÉ.

REPRO (QA 30/09) : calepinage → Terrain → « Calculer » → « Enregistrer le
champ » (≈340 modules sous ``poseSurfaces[0].engine.modules``) → « Générer le
devis » → 422 « Aucun panneau détecté dans le layout… ». Le lecteur unique
``geometrie.lire_layout`` (QJR165), qu'utilisent le pré-vol
``validate_composition_for_layout`` ET la création, ne lisait que ``result``
et les pans de toiture : il rendait 0.

ACAL59 — réécrit sur la sortie de ``pans_du_document`` (la primitive qui a
absorbé ``compte_surfaces_de_pose``) : une surface de pose est un PAN, son
compte s'ADDITIONNE à celui du toit (plus un simple repli).

``SimpleTestCase`` : la lecture est PURE (un dict entre, un tuple sort).

Run :
    python manage.py test apps.ventes.tests.test_lire_layout_surfaces_pose -v2
"""
from django.test import SimpleTestCase

from apps.ventes.domain.geometrie import lire_layout, pans_du_document


def _layout_sol(modules=340, **surface):
    """Le ``roof_layout`` qu'écrit ``ModeTerrain.jsx`` (``documentTerrain``)."""
    return {
        'poseSurfaces': [dict({
            'kind': 'sol', 'id': 'TERRAIN', 'label': 'Champ au sol',
            'contourM': [[0, 0], [40, 0], [40, 25], [0, 25]], 'areaM2': 1000,
            'rowAzimuthDeg': 180, 'tiltDeg': 25,
            'engine': {'modules': modules, 'tables': [], 'rowPitchM': 4.2},
        }, **surface)],
    }


class LireLayoutSurfacesDePoseTest(SimpleTestCase):
    def test_un_champ_au_sol_enregistre_est_compte(self):
        self.assertEqual(lire_layout(_layout_sol()).compte, 340)
        pans = pans_du_document(_layout_sol())
        self.assertEqual([(p['kind'], p['modules']) for p in pans],
                         [('sol', 340)])

    def test_le_kwc_est_mesure_quand_la_puissance_module_est_saisie(self):
        lecture = lire_layout(_layout_sol(moduleWc=550))
        self.assertEqual(lecture.compte, 340)
        self.assertAlmostEqual(lecture.kwc, 187.0)
        self.assertEqual(lecture.watt, 550)
        self.assertAlmostEqual(lecture.pans[0]['kwc'], 187.0)

    def test_sans_puissance_saisie_aucun_kwc_invente(self):
        pan, = pans_du_document(_layout_sol())
        self.assertEqual(pan['modules'], 340)
        self.assertIsNone(pan['kwc'])
        self.assertIn('Champ au sol', pan['refus'])
        self.assertEqual(lire_layout(_layout_sol()).kwc, 0.0)

    def test_le_toit_du_result_racine_s_additionne_a_la_surface(self):
        # D-ACAL-5 : le ``result`` racine est le TOIT seul ; sans zone, il
        # est lu, et la surface de pose est un pan de plus.
        layout = dict(_layout_sol(moduleWc=550),
                      result={'panels': 12, 'kwc': 6.6})
        lecture = lire_layout(layout)
        self.assertEqual(lecture.compte, 12 + 340)
        self.assertAlmostEqual(lecture.kwc, 6.6 + 187.0)

    def test_plusieurs_surfaces_se_totalisent(self):
        layout = _layout_sol(100, moduleWc=500)
        layout['poseSurfaces'].append({
            'kind': 'ombriere', 'moduleWc': 500,
            'engine': {'modules': 40}})
        pans = pans_du_document(layout)
        self.assertEqual(sum(p['modules'] for p in pans), 140)
        self.assertAlmostEqual(sum(p['kwc'] for p in pans), 70.0)
        self.assertEqual(lire_layout(layout).compte, 140)

    def test_surface_sans_plan_moteur_ignoree(self):
        layout = {'poseSurfaces': [{'kind': 'sol', 'engine': {'modules': None}},
                                   'pas-un-dict', {'kind': 'sol'}]}
        pans = pans_du_document(layout)
        self.assertEqual([p['modules'] for p in pans], [0, 0])
        self.assertTrue(all('non pavé' in p['avertissement'] for p in pans))
        self.assertEqual(lire_layout(layout).compte, 0)

    def test_layout_muet_reste_a_zero(self):
        self.assertEqual(lire_layout({}).compte, 0)
        self.assertEqual(pans_du_document(None), [])
