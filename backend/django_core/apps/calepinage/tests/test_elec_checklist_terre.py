"""CAL134 — la terre : une check-list, et la justification qui manquait.

La décision fondateur du 19/08/2026 retire la prise de terre du bordereau par
défaut (« le client est réputé déjà équipé »). Sa moitié manquante est ici :
sans prise de terre VENDUE, la continuité de la terre EXISTANTE doit être
justifiée avant publication (NF C 15-100 §542).

Et la règle qui ne se négocie pas : aucune valeur de résistance n'est
inventée. Sans mesure saisie, la ligne dit « non mesurée » — un « ≤ 100 Ω »
imprimé sans mesure serait un procès-verbal falsifié.

Run :
    python manage.py test apps.calepinage.tests.test_elec_checklist_terre -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import temperatures_site
from apps.calepinage.services.norme import norme_applicable
from apps.calepinage.services.terre import (
    TerreInvalide, checklist_terre, garde_terre,
)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}
NORME_FR = norme_applicable({'imagerie': {'pays': 'fr'},
                             'norme_electrique': {}})
NORME_MA = norme_applicable({'imagerie': {'pays': 'ma'},
                             'norme_electrique': {}})
LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-A', 'geometry': {'count': 12, 'azimuthDeg': 180.0,
                                    'tiltDeg': 15.0}}]}


def _conception(prise_vendue=False):
    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        inclure_prise_terre=prise_vendue)


class ChecklistTerreTest(SimpleTestCase):
    """Quatre lignes, chacune citant sa référence."""

    def test_les_quatre_lignes_citent_leur_reference(self):
        checklist = checklist_terre(_conception(), norme=NORME_FR)
        codes = [ligne['code'] for ligne in checklist['lignes']]

        self.assertEqual(codes, ['liaison_equipotentielle',
                                 'section_conducteur', 'piquet_barrette',
                                 'mesure_continuite'])
        for ligne in checklist['lignes']:
            self.assertTrue(ligne['reference'])

    def test_la_section_est_lue_sur_l_organe_du_noyau(self):
        checklist = checklist_terre(_conception(), norme=NORME_FR)
        section = [ligne for ligne in checklist['lignes']
                   if ligne['code'] == 'section_conducteur'][0]

        self.assertIn('mm²', section['valeur'])
        self.assertIn('542.4', section['reference'])

    def test_aucune_resistance_de_terre_inventee(self):
        checklist = checklist_terre(_conception(), norme=NORME_FR)
        mesure = [ligne for ligne in checklist['lignes']
                  if ligne['code'] == 'mesure_continuite'][0]

        self.assertIsNone(checklist['mesure'])
        self.assertFalse(mesure['fait'])
        self.assertIn('non mesurée', mesure['valeur'])
        self.assertNotIn('100', mesure['valeur'])

    def test_une_mesure_saisie_est_publiee_telle_quelle(self):
        checklist = checklist_terre(
            _conception(), norme=NORME_FR,
            decisions={'resistance_ohm': 42.5,
                       'justification_continuite': True})
        mesure = [ligne for ligne in checklist['lignes']
                  if ligne['code'] == 'mesure_continuite'][0]

        self.assertEqual(checklist['mesure'], 42.5)
        self.assertTrue(mesure['fait'])
        self.assertIn('42,5 Ω', mesure['valeur'])

    def test_une_mesure_illisible_est_refusee_en_nommant_le_champ(self):
        with self.assertRaises(TerreInvalide) as capture:
            checklist_terre(_conception(), norme=NORME_FR,
                            decisions={'resistance_ohm': 'trente'})

        self.assertEqual(capture.exception.champ, 'terre.resistance_ohm')


class JustificationTest(SimpleTestCase):
    """Sans prise vendue, la justification cochée est EXIGÉE."""

    def test_sans_prise_vendue_la_justification_est_requise(self):
        checklist = checklist_terre(_conception(), norme=NORME_FR)

        self.assertTrue(checklist['justification_requise'])
        self.assertFalse(checklist['justification_fournie'])
        with self.assertRaises(TerreInvalide) as capture:
            garde_terre(checklist)
        self.assertEqual(capture.exception.champ,
                         'terre.justification_continuite')

    def test_justification_cochee_laisse_publier(self):
        checklist = checklist_terre(
            _conception(), norme=NORME_FR,
            decisions={'justification_continuite': True})

        self.assertTrue(garde_terre(checklist))

    def test_prise_de_terre_vendue_n_exige_aucune_justification(self):
        checklist = checklist_terre(_conception(prise_vendue=True),
                                    norme=NORME_FR)
        piquet = [ligne for ligne in checklist['lignes']
                  if ligne['code'] == 'piquet_barrette'][0]

        self.assertFalse(checklist['justification_requise'])
        self.assertTrue(piquet['fait'])
        self.assertTrue(garde_terre(checklist))


class PieceJointeTest(SimpleTestCase):
    """La pièce jointe passe par la GED — jamais une référence fantôme."""

    def test_identifiant_illisible_refuse(self):
        with self.assertRaises(TerreInvalide) as capture:
            checklist_terre(_conception(), norme=NORME_FR,
                            decisions={'document_id': 'abc'})

        self.assertEqual(capture.exception.champ, 'terre.document_id')

    def test_hors_base_la_reference_n_est_pas_dite_verifiee(self):
        checklist = checklist_terre(_conception(), norme=NORME_FR,
                                    decisions={'document_id': 12})

        self.assertEqual(checklist['piece_jointe'],
                         {'document_id': 12, 'verifie': False})


class NormeTest(SimpleTestCase):
    """Sans norme sélectionnée, la check-list est OMISE (règle D5)."""

    def test_maroc_sans_norme_omet_la_checklist_et_n_exige_rien(self):
        checklist = checklist_terre(_conception(), norme=NORME_MA)

        self.assertEqual(checklist['lignes'], [])
        self.assertFalse(checklist['justification_requise'])
        self.assertTrue(garde_terre(checklist))
        self.assertIn('OMIS', checklist['omissions'][0])
