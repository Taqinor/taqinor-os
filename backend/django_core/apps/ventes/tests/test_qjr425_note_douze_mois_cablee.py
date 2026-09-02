"""QJR425 / DR7 — la note de méthode « douze mois » et la note de factures
ATTEIGNENT enfin les surfaces d'étude.

TEST ROUGE D'ABORD. Les deux dernières moitiés du ``Done`` de QJR157 avaient
été livrées comme **capacité de bibliothèque testée** et n'étaient câblées
NULLE PART : ``calculate_savings_roi`` rendait bien ``factures_note_methode``
et PERSONNE ne le lisait — ``pricing.NOTE_DOUZE_MOIS`` était inatteignable
depuis l'ERP, et ``factures_note`` n'était publiée par aucune surface. Une note
de méthode que le client ne lit jamais ne remplit pas son office : la règle
checked-facts exige qu'un chiffre publié soit TRAÇABLE, et c'est cette note qui
porte la traçabilité (« sur quelle base ces douze mois ont-ils été tarifés »).

PÉRIMÈTRE (règle permanente 1) : cette tâche CÂBLE une note existante. Elle ne
touche à AUCUN montant — la moitié « tarifer les douze mois » de QJR157 reste
une capacité de bibliothèque, désormais ATTEIGNABLE par un paramètre
pass-through (``repartition_mensuelle``) dont aucun appelant ne se sert
aujourd'hui : sortie byte-identique.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr425_note_douze_mois_cablee"
"""
from django.test import TestCase

from apps.ventes.quote_engine import pricing
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)


LIGNES = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Installation', '1', '5000'),
]

#: 12 parts (somme ≈ 1) — une répartition mensuelle RÉELLE.
REPARTITION = [0.09, 0.08, 0.08, 0.07, 0.08, 0.09,
               0.10, 0.10, 0.08, 0.08, 0.07, 0.08]

ROI_ARGS = dict(conso_annuelle_kwh=9000, utility='onee')


class LaNoteAtteintLaSurfaceDEtude(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, LIGNES,
            reference='DEV-QJR425-0001',
            etude_params={'scenario': 'Sans batterie',
                          'conso_annuelle': 9000,
                          'distributeur': 'onee'})

    def test_la_surface_publie_la_note_avec_ses_montants(self):
        """ROUGE AVANT : ``factures_note`` n'était publiée par AUCUNE
        surface."""
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        self.assertEqual(data['savings_model'], 'factures')
        self.assertTrue(data['factures_note'])
        self.assertEqual(data['etude']['factures_note'],
                         data['factures_note'])
        self.assertEqual(data['savings_method']['note_methode'],
                         data['factures_note'])

    def test_la_note_publiee_est_celle_que_le_moteur_a_produite(self):
        """Jamais un texte par défaut : la note DIT la méthode employée."""
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        self.assertIn(data['factures_note'],
                      (pricing.NOTE_DOUZE_MOIS, pricing.NOTE_MOIS_MOYEN))


class SansModeleFacturesAucuneNote(TestCase):
    """Pas de note vide, pas de texte par défaut (règle Z2)."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        # Aucune consommation ⇒ le modèle « factures » ne peut pas s'appliquer.
        self.devis = make_devis(
            self.company, self.user, self.client_obj, LIGNES,
            reference='DEV-QJR425-0002',
            etude_params={'scenario': 'Sans batterie'})

    def test_aucune_note_n_est_publiee(self):
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        self.assertNotEqual(data['savings_model'], 'factures')
        self.assertIsNone(data['factures_note'])
        self.assertNotIn('factures_note', data['etude'])
        self.assertIsNone(data['savings_method'].get('note_methode'))


class LaNoteDouzeMoisEstAtteignableDepuisLErp(TestCase):
    """``NOTE_DOUZE_MOIS`` a désormais un chemin depuis ``calculate_savings_roi``
    — c'est ce qui manquait : la capacité existait, la porte non."""

    def test_avec_repartition_la_note_est_celle_des_douze_mois(self):
        roi = pricing.calculate_savings_roi(
            10.0, 150000, 190000, repartition_mensuelle=REPARTITION,
            **ROI_ARGS)
        self.assertEqual(roi['savings_model'], 'factures')
        self.assertEqual(roi['factures_note_methode'],
                         pricing.NOTE_DOUZE_MOIS)

    def test_sans_repartition_la_note_dit_le_mois_moyen(self):
        roi = pricing.calculate_savings_roi(10.0, 150000, 190000, **ROI_ARGS)
        self.assertEqual(roi['factures_note_methode'],
                         pricing.NOTE_MOIS_MOYEN)


class AucunMontantNeBouge(TestCase):
    """La note s'AJOUTE : tous les montants sont inchangés au centime."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, LIGNES,
            reference='DEV-QJR425-0003',
            etude_params={'scenario': 'Sans batterie',
                          'conso_annuelle': 9000,
                          'distributeur': 'onee'})

    def test_le_parametre_pass_through_ne_change_rien_par_defaut(self):
        avant = pricing.calculate_savings_roi(10.0, 150000, 190000, **ROI_ARGS)
        apres = pricing.calculate_savings_roi(
            10.0, 150000, 190000, repartition_mensuelle=None, **ROI_ARGS)
        for cle in ('facture_sans', 'facture_avec_s', 'facture_avec_a',
                    'eco_s_ann', 'eco_a_ann', 'roi_s', 'roi_a'):
            self.assertEqual(avant[cle], apres[cle], cle)

    def test_les_montants_de_la_surface_sont_inchanges(self):
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        self.assertEqual(data['etude']['facture_annuelle_sans_solaire'],
                         data['savings_method']['facture_actuelle'])
        self.assertEqual(
            data['savings_method']['economie'],
            data['savings_method']['facture_actuelle']
            - data['savings_method']['facture_avec_solaire'])
