"""CAD175 — seconde livraison du panneau d'appel : agricole et industriel.

Ce que le SERVEUR doit servir pour que l'écran rende le bon jeu de questions
(``frontend/src/features/crm/relances/appelGuidance.js``, ``ORDRE_AGRICOLE`` /
``ORDRE_PRO``) : chaque question est une colonne ``crm.Lead`` EXISTANTE — la
pompe pour l'agricole, la puissance souscrite pour l'industriel et le
commercial — et une réponse déjà sur la fiche n'est jamais reposée.

Aucune base : un ``Lead`` NON ENREGISTRÉ suffit.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.crm import panneau_appel as panneau
from apps.crm.models import Lead

#: Les colonnes que l'écran pose, par famille (miroir des étapes de
#: `appelGuidance.js` ; le test écran prouve l'ordre, celui-ci la présence).
COLONNES_AGRICOLES = ('pompe_cv', 'pompe_hmt_m', 'pompe_debit_m3h',
                      'pompage_heures_jour', 'pompe_alim_actuelle',
                      'carburant_litres_mois')
COLONNES_PRO = ('conso_mensuelle_kwh', 'compteur_puissance_kva',
                'surface_toiture_m2', 'decideur')


def _champs(lead):
    return [q['champ'] for q in panneau.questions_a_poser(lead)]


class LeServeurSertLesQuestionsDuSegment(SimpleTestCase):
    def test_un_lead_agricole_se_voit_poser_sa_pompe(self):
        champs = _champs(Lead(nom='P', type_installation='agricole'))
        for colonne in COLONNES_AGRICOLES:
            self.assertIn(colonne, champs, colonne)

    def test_industriel_et_commercial_se_voient_poser_le_jeu_pro(self):
        for segment in ('industriel', 'commercial'):
            champs = _champs(Lead(nom='P', type_installation=segment))
            for colonne in COLONNES_PRO:
                self.assertIn(colonne, champs, f'{segment}:{colonne}')

    def test_le_residentiel_ne_recoit_ni_la_pompe_ni_la_puissance_souscrite(self):
        """En résidentiel, la puissance souscrite se lit sur la PHOTO du
        compteur (dernier recours à l'oral, CAD154) : pas une question."""
        champs = _champs(Lead(nom='P', type_installation='residentiel'))
        for colonne in ('pompe_cv', 'compteur_puissance_kva'):
            self.assertNotIn(colonne, champs, colonne)

    def test_chaque_colonne_de_segment_existe_sur_le_lead(self):
        for colonne in (*COLONNES_AGRICOLES, *COLONNES_PRO):
            self.assertIsNotNone(Lead._meta.get_field(colonne), colonne)

    def test_une_reponse_de_segment_deja_sur_la_fiche_n_est_pas_reposee(self):
        lead = Lead(nom='P', type_installation='agricole',
                    pompe_cv=Decimal('7.50'))
        self.assertNotIn('pompe_cv', _champs(lead))
        self.assertEqual(panneau.prefill_du_panneau(lead)['pompe_cv'], 7.5)
        pro = Lead(nom='P', type_installation='industriel',
                   compteur_puissance_kva=Decimal('60.00'))
        self.assertNotIn('compteur_puissance_kva', _champs(pro))
        self.assertEqual(
            panneau.prefill_du_panneau(pro)['compteur_puissance_kva'], 60.0)

    def test_la_pompe_est_servie_comme_un_nombre(self):
        questions = {q['champ']: q for q in panneau.questions_a_poser(
            Lead(nom='P', type_installation='agricole'))}
        for colonne in ('pompe_cv', 'pompe_hmt_m', 'pompe_debit_m3h'):
            self.assertEqual(questions[colonne]['nature'], 'nombre', colonne)
            self.assertIsNone(questions[colonne]['choix'], colonne)
