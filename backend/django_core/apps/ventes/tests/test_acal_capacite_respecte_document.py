"""ACAL272 (C-ACAL-116) — la carte « Max » et les dessins dérivés de la page
client respectent retraits saisis, dégagements propres, zones
INTERDITE/RÉSERVÉE et surfaces de pose — ou refusent d'étendre.

``calepinage_options`` réel, géométrie PURE (``SimpleTestCase``) : le toit
d'essai est celui de ``test_calepinage_options`` (forme assainie).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_capacite_respecte_document"
"""
from django.test import SimpleTestCase

from apps.ventes import calepinage_options as co
from apps.ventes.tests.test_calepinage_options import (
    _lnglat, obstacle, toit)


def _toit_huit():
    """2 rangées × 4 colonnes = 8 posés, toit 24 × 16 m."""
    return toit(rangees=2, colonnes=4)


class CapaciteRespecteLeDocument(SimpleTestCase):

    def test_retrait_saisi_reduit(self):
        base = co.capacite_du_layout(_toit_huit())
        regle = _toit_huit()
        regle['setbacksM'] = {'lateralM': 2, 'extremityM': 2, 'parapetM': 2}
        reduite = co.capacite_du_layout(regle)
        self.assertGreater(base, 8)
        self.assertLess(reduite, base)
        self.assertGreaterEqual(reduite, 8)
        # Aucun emplacement ajouté à moins de 2 m d'un bord.
        trame = co.lire_trames(regle)[0]
        self.assertEqual(trame.retrait, 2.0)
        sans_saisie = co.lire_trames(_toit_huit())[0]
        self.assertEqual(sans_saisie.retrait, co._RETRAIT_RIVE_M)

    def test_zone_interdite_refuse_extension(self):
        layout = _toit_huit()
        layout['exclusionZones'] = [{
            'id': 'ex1', 'nature': 'INTERDITE',
            'vertices': [_lnglat(0, -8), _lnglat(12, -8), _lnglat(12, 8),
                         _lnglat(0, 8)]}]
        self.assertEqual(co.capacite_du_layout(layout), 8)
        self.assertTrue(co.motif_non_extensible(layout))
        self.assertFalse(co.lire_trames(layout)[0].extensible())
        # Une zone PRÉFÉRÉE n'interdit rien.
        layout['exclusionZones'][0]['nature'] = 'PREFEREE'
        self.assertGreater(co.capacite_du_layout(layout), 8)

    def test_obstacle_non_rectangulaire_et_allee_refusent(self):
        cercle = obstacle(9, -1, 1, 1)
        cercle.update({'forme': 'cercle', 'rayonM': 0.5})
        layout = toit(rangees=2, colonnes=4, obstacles=[cercle])
        self.assertEqual(co.capacite_du_layout(layout), 8)
        allee = _toit_huit()
        allee['alleeTechnique'] = {'largeurM': 1.0, 'source': 'saisie'}
        self.assertEqual(co.capacite_du_layout(allee), 8)

    def test_degagement_propre(self):
        petit = obstacle(9, -1, 0.5, 0.5)
        sans = co.capacite_du_layout(
            toit(rangees=2, colonnes=4, obstacles=[petit]))
        large = dict(petit, degagementM=3.0)
        avec = co.capacite_du_layout(
            toit(rangees=2, colonnes=4, obstacles=[large]))
        self.assertLess(avec, sans)
        boite_type, = co.obstacles_enu([petit], [-7.58, 33.57])
        boite_propre, = co.obstacles_enu([large], [-7.58, 33.57])
        self.assertAlmostEqual(boite_propre[2] - boite_propre[0], 0.5 + 6.0,
                               places=3)
        self.assertAlmostEqual(boite_type[2] - boite_type[0], 0.5 + 0.6,
                               places=3)

    def test_surfaces_de_pose_comptees(self):
        layout = _toit_huit()
        layout['poseSurfaces'] = [{'id': 's1', 'kind': 'sol',
                                   'engine': {'modules': 40}}]
        self.assertEqual(co.nb_panneaux_publies(layout), 48)
        # Le toit n'est plus prolongé seul (le dessin dérivé ne redessinerait
        # pas la surface) : la contenance vaut le posé.
        self.assertEqual(co.capacite_du_layout(layout), 48)
