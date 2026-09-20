"""CAL132 — la check-list de protections est éditable SANS mentir sur la règle.

Trois garanties :

1. un organe AJOUTÉ à la main est marqué « décision société » et ne porte
   JAMAIS une référence normative — même si le corps de requête en propose une ;
2. ÉCARTER un organe exigé demande un motif écrit, et l'organe reste dans la
   liste (barré, avec sa raison) au lieu de disparaître ;
3. la nomenclature et le schéma lisent CETTE liste (``organes_retenus``) —
   source unique, jamais une seconde décision prise ailleurs.

Run :
    python manage.py test apps.calepinage.tests.test_elec_checklist_protections -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import temperatures_site
from apps.calepinage.services.norme import norme_applicable
from apps.calepinage.services.protections import (
    MENTION_SOCIETE, ORIGINE_ECARTE, ORIGINE_REGLE, ORIGINE_SOCIETE,
    DecisionInvalide, checklist_protections, organes_retenus,
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


def _conception():
    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        onduleur_designation='Onduleur d essai')


class ChecklistTest(SimpleTestCase):
    """Chaque ligne garde sa source."""

    def test_les_organes_du_moteur_citent_leur_regle(self):
        checklist = checklist_protections(_conception(), norme=NORME_FR)

        self.assertTrue(checklist['organes'])
        for ligne in checklist['organes']:
            self.assertEqual(ligne['origine'], ORIGINE_REGLE)
            self.assertTrue(ligne['regle_source'])
            self.assertTrue(ligne['retenu'])

    def test_un_ajout_societe_n_est_jamais_presente_comme_normatif(self):
        checklist = checklist_protections(
            _conception(), norme=NORME_FR,
            decisions={'ajouts': [{
                'repere': 'PDC9', 'designation': 'Parafoudre DC Type 2',
                'calibre': '1000 V DC', 'quantite': 1,
                'motif': 'exigence du bureau de contrôle du client',
                # Tentative d'habiller la décision d'une norme : IGNORÉE.
                'regle_source': 'UTE C 15-712-1 §7'}]})
        ajout = [ligne for ligne in checklist['organes']
                 if ligne['repere'] == 'PDC9'][0]

        self.assertEqual(ajout['origine'], ORIGINE_SOCIETE)
        self.assertTrue(ajout['regle_source'].startswith(MENTION_SOCIETE))
        self.assertNotIn('UTE C 15-712-1 §7', ajout['regle_source'])
        self.assertIn('bureau de contrôle', ajout['regle_source'])

    def test_un_ajout_sans_motif_est_refuse_en_nommant_le_champ(self):
        with self.assertRaises(DecisionInvalide) as capture:
            checklist_protections(
                _conception(), norme=NORME_FR,
                decisions={'ajouts': [{'designation': 'Parafoudre'}]})

        self.assertEqual(capture.exception.champ,
                         'protections.ajouts.motif')

    def test_ecarter_un_organe_exige_un_motif_ecrit(self):
        repere = checklist_protections(
            _conception(), norme=NORME_FR)['organes'][0]['repere']

        with self.assertRaises(DecisionInvalide) as capture:
            checklist_protections(_conception(), norme=NORME_FR,
                                  decisions={'ecartes': [{'repere': repere}]})

        self.assertEqual(capture.exception.champ,
                         'protections.ecartes.motif')

    def test_un_organe_ecarte_reste_dans_la_liste_avec_sa_raison(self):
        repere = checklist_protections(
            _conception(), norme=NORME_FR)['organes'][0]['repere']

        checklist = checklist_protections(
            _conception(), norme=NORME_FR,
            decisions={'ecartes': [{'repere': repere,
                                    'motif': 'organe déjà en place'}]})
        ligne = [l for l in checklist['organes']  # noqa: E741
                 if l['repere'] == repere][0]

        self.assertFalse(ligne['retenu'])
        self.assertEqual(ligne['origine'], ORIGINE_ECARTE)
        self.assertEqual(ligne['motif'], 'organe déjà en place')
        # La règle d'origine n'est PAS effacée : on voit ce qui a été écarté.
        self.assertTrue(ligne['regle_source'])

    def test_ecarter_un_repere_inconnu_est_refuse_en_le_nommant(self):
        with self.assertRaises(DecisionInvalide) as capture:
            checklist_protections(
                _conception(), norme=NORME_FR,
                decisions={'ecartes': [{'repere': 'XX9', 'motif': 'non'}]})

        self.assertIn('XX9', str(capture.exception))


class SourceUniqueTest(SimpleTestCase):
    """Le bordereau et le schéma lisent CETTE liste."""

    def test_organes_retenus_exclut_les_ecartes_et_garde_les_ajouts(self):
        base = checklist_protections(_conception(), norme=NORME_FR)
        repere = base['organes'][0]['repere']

        checklist = checklist_protections(
            _conception(), norme=NORME_FR,
            decisions={'ecartes': [{'repere': repere, 'motif': 'déjà posé'}],
                       'ajouts': [{'designation': 'Coffret supplémentaire',
                                   'motif': 'demande client'}]})
        retenus = {ligne['repere'] for ligne in organes_retenus(checklist)}

        self.assertNotIn(repere, retenus)
        self.assertIn('SOC1', retenus)
        self.assertEqual(len(organes_retenus(checklist)),
                         len(base['organes']))


class NormeTest(SimpleTestCase):
    """Sans norme sélectionnée, la check-list est OMISE (règle D5)."""

    def test_maroc_sans_norme_omet_la_checklist(self):
        checklist = checklist_protections(_conception(), norme=NORME_MA)

        self.assertEqual(checklist['organes'], [])
        self.assertIn('OMIS', checklist['omissions'][0])
