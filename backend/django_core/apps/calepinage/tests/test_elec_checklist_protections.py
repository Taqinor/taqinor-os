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
        ligne = [o for o in checklist['organes']
                 if o['repere'] == repere][0]

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

    # ── ACAL675 — la question « coupure d'urgence DC / arrêt rapide ? » ──
    def _arret_rapide(self, reponse):
        decisions = ({'exigences': {'arret_rapide': reponse}}
                     if reponse is not None else None)
        return checklist_protections(_conception(), norme=NORME_FR,
                                     decisions=decisions)

    def test_arret_rapide_oui_ajoute_l_organe_repris_par_la_source_unique(
            self):
        checklist = self._arret_rapide('oui')
        organe = [ligne for ligne in checklist['organes']
                  if 'arrêt rapide' in ligne['designation']][0]

        self.assertEqual(organe['origine'], ORIGINE_SOCIETE)
        self.assertTrue(organe['repere'].startswith('SOC'))
        self.assertIn('exigé par le dossier', organe['regle_source'])
        self.assertIn(organe['repere'], {
            ligne['repere'] for ligne in organes_retenus(checklist)})
        self.assertEqual(checklist['questions'][0]['statut'], 'exige')

    def test_arret_rapide_non_n_ajoute_aucun_organe_et_le_dit(self):
        sans = self._arret_rapide(None)
        non = self._arret_rapide('non')

        self.assertEqual(len(non['organes']), len(sans['organes']))
        self.assertIn('non exigé', non['questions'][0]['libelle'])

    def test_arret_rapide_absent_est_une_question_non_renseignee(self):
        checklist = self._arret_rapide(None)

        self.assertEqual(
            checklist['questions'][0]['libelle'],
            "Coupure d'urgence DC / arrêt rapide exigé ? — non renseigné")
        self.assertEqual(checklist['questions'][0]['statut'],
                         'non_renseigne')

    def test_arret_rapide_illisible_est_refuse_en_nommant_le_champ(self):
        with self.assertRaises(DecisionInvalide) as capture:
            self._arret_rapide('peut-être')

        self.assertEqual(capture.exception.champ,
                         'protections.exigences.arret_rapide')

    def test_les_questions_du_dossier_portent_leur_libelle_seul(self):
        """ACAL1973 — la question servie (``protections.questions``) porte
        son libellé SEUL et son champ : l'écran ne le recopie plus en dur.
        Les MÊMES questions que la check-list ; une réponse illisible n'est
        jamais une exception, la question reste « non renseigné »."""
        from apps.calepinage.services.protections import questions_du_dossier

        oui = {'exigences': {'arret_rapide': 'oui'}}
        question = questions_du_dossier(oui)[0]
        self.assertEqual(question['question'],
                         "Coupure d'urgence DC / arrêt rapide exigé ?")
        self.assertEqual(question['champ'], 'protections.exigences.arret_rapide')
        self.assertEqual(questions_du_dossier(oui),
                         self._arret_rapide('oui')['questions'])
        for illisible in ({'exigences': {'arret_rapide': 'peut-être'}}, ['x']):
            self.assertEqual(questions_du_dossier(illisible)[0]['statut'],
                             'non_renseigne')

    # ── ACAL676 — distance de séparation foudre ──
    def _paratonnerre(self, paratonnerre, reglages=None):
        return checklist_protections(
            _conception(), norme=NORME_FR, reglages=reglages,
            decisions={'exigences': {'paratonnerre': paratonnerre}}
        )['questions']

    def test_distance_sous_le_minimum_saisi_est_a_surveiller(self):
        questions = self._paratonnerre(
            {'present': 'oui', 'distance_separation_m': 1.2},
            {'distance_separation_foudre_min_m': {
                'valeur': 1.5, 'source': 'saisie'}})

        ligne = questions[-1]
        self.assertEqual(
            ligne['libelle'], 'Paratonnerre : distance 1,2 m inférieure au '
            'minimum 1,5 m saisi par la société')
        self.assertEqual(ligne['statut'], 'a_surveiller')

    def test_minimum_non_saisi_la_distance_n_est_pas_controlee(self):
        for reglages in (None, {}, {'distance_separation_foudre_min_m': {
                'valeur': 1.5, 'source': ''}}):
            ligne = self._paratonnerre(
                {'present': 'oui', 'distance_separation_m': 0.1},
                reglages)[-1]

            self.assertIn('distance non contrôlée : valeur minimale non '
                          'saisie', ligne['libelle'])
            self.assertEqual(ligne['statut'], 'non_controle')

    def test_paratonnerre_absent_ou_non_ne_pose_aucune_ligne_de_distance(
            self):
        for paratonnerre in ({'present': 'non'}, {}, None):
            questions = self._paratonnerre(paratonnerre)

            self.assertEqual(len(questions), 1)
            self.assertNotIn('Paratonnerre', questions[0]['libelle'])


class ReglageFoudreBrancheTest(SimpleTestCase):
    """REP-676 — la check-list lue par l'évaluation reçoit le réglage société."""

    def test_la_lecture_tolerante_transmet_le_reglage_societe(self):
        from apps.calepinage.services.electrique import (
            _checklist_protections_tolerante,
        )

        decisions = {'exigences': {'paratonnerre': {
            'present': 'oui', 'distance_separation_m': 1.2}}}
        reglages = {'distance_separation_foudre_min_m': {
            'valeur': 1.5, 'source': 'saisie'}}

        sans, _avis = _checklist_protections_tolerante(
            _conception(), decisions, NORME_FR)
        avec, _avis = _checklist_protections_tolerante(
            _conception(), decisions, NORME_FR, reglages=reglages)

        self.assertEqual(sans['questions'][-1]['statut'], 'non_controle')
        self.assertEqual(avec['questions'][-1]['statut'], 'a_surveiller')


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
        self.assertIn('ne sont pas calculés', checklist['omissions'][0])
