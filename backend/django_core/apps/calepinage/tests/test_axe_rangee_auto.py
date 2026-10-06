"""ERR-QAH-CALEPINAGE-SOL-AXE-NORD-SUD — l'axe des rangées « AUTO » est DÉRIVÉ.

L'écran terrain/ombrière envoyait toujours ``axe_rangee: "NORD_SUD"`` : un
champ au sol à UN module par table orienté SUD (180°, le cas courant) était
refusé 400 « NORD_SUD demandé (inconstructible) ». L'écran envoie désormais
``AUTO`` et ``moteur_io.deriver_axe_rangee`` applique la SEULE règle du moteur
(``core.calepinage.orientation.axe_rangee_impose``).

``SimpleTestCase`` : la dérivation et le calcul du moteur sont PURS (aucune
ligne lue ni écrite).

Run :
    python manage.py test apps.calepinage.tests.test_axe_rangee_auto -v2
"""
from django.test import SimpleTestCase

from apps.calepinage import moteur_service
from apps.calepinage.moteur_io import (
    AXE_AUTO, EntreeInvalide, deriver_axe_rangee,
)


def _demande(modules_par_table, azimut=180, axe=AXE_AUTO):
    """La demande EXACTE que ``ModeTerrain.jsx`` envoie (repro QA 30/09)."""
    contour = [[0, 0], [40, 0], [40, 25], [0, 25]]
    return {
        'schema_version': 1, 'repere': 'TERRAIN', 'contour': contour,
        'surfaces': [{
            'type': 'polygone', 'repere': 'TERRAIN', 'contour': contour,
            'trous': [], 'axe_rangee': axe, 'niveau': 0, 'pente_deg': 0,
            'azimut_deg': azimut, 'origine': [0, 0], 'coupures': [],
        }],
        'kits': [{
            'code': 'terrain', 'libelle': 'Table terrain',
            'module_long_m': 2.278, 'module_court_m': 1.134,
            'puissance_module_wc': 550, 'inclinaison_deg': 25,
            'orientation': 'PORTRAIT',
            'modules_par_table': modules_par_table, 'faitage_m': 0,
        }],
        'parametres': {
            'kits': ['terrain'], 'axe_rangee': axe,
            'mode_pose': 'rangees_explicites_dp', 'pas_recherche_m': 0.01,
        },
        'obstacles': [], 'zones': [],
    }


class DeriverAxeRangeeTest(SimpleTestCase):
    def test_un_module_par_table_plein_sud_donne_est_ouest(self):
        doc = deriver_axe_rangee(_demande(1, 180))
        self.assertEqual(doc['parametres']['axe_rangee'], 'EST_OUEST')
        self.assertEqual(doc['surfaces'][0]['axe_rangee'], 'EST_OUEST')

    def test_un_module_par_table_plein_est_donne_nord_sud(self):
        doc = deriver_axe_rangee(_demande(1, 90))
        self.assertEqual(doc['parametres']['axe_rangee'], 'NORD_SUD')

    def test_table_dos_a_dos_donne_nord_sud(self):
        doc = deriver_axe_rangee(_demande(2, 180))
        self.assertEqual(doc['parametres']['axe_rangee'], 'NORD_SUD')

    def test_un_axe_explicite_n_est_jamais_reecrit(self):
        demande = _demande(1, 180, axe='NORD_SUD')
        self.assertIs(deriver_axe_rangee(demande), demande)

    def test_la_demande_d_origine_n_est_pas_mutee(self):
        demande = _demande(1, 180)
        deriver_axe_rangee(demande)
        self.assertEqual(demande['parametres']['axe_rangee'], AXE_AUTO)
        self.assertEqual(demande['surfaces'][0]['axe_rangee'], AXE_AUTO)

    def test_kits_d_axes_incompatibles_refuses(self):
        demande = _demande(1, 180)
        demande['kits'].append(dict(demande['kits'][0], code='dos',
                                    modules_par_table=2))
        demande['parametres']['kits'] = ['terrain', 'dos']
        with self.assertRaises(EntreeInvalide):
            deriver_axe_rangee(demande)


class PoseSudUnModuleTest(SimpleTestCase):
    """La repro QA : 40 × 25 m, sud, 1 module par table → un champ POSÉ."""

    def test_le_moteur_pose_le_champ_sud_sans_refus(self):
        resultat = moteur_service.calepiner(
            deriver_axe_rangee(_demande(1, 180)), company=1,
            suggestions=False)
        self.assertGreater(resultat['total_modules'], 0)

    def test_sans_derivation_nord_sud_reste_refuse(self):
        """Le garde-fou du moteur n'est PAS affaibli : un axe faux explicite
        reste refusé, seule la valeur AUTO est dérivée."""
        _, incoherent = moteur_service.erreurs_moteur_calepinage()
        with self.assertRaises((incoherent, EntreeInvalide)):
            moteur_service.calepiner(
                _demande(1, 180, axe='NORD_SUD'), company=1,
                suggestions=False)
