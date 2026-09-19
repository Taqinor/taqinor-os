"""Tests NTAI31 — explicabilité des scores (facteurs contributifs).

Acceptance criteria couverte : un score de churn renvoie ses 3 principaux
facteurs en langage clair, purement déterministe ; un test par scorer.

Tests PURS (``SimpleTestCase``) : les scorers de ``core`` ne touchent ni la
base ni le réseau, et ces tests non plus.
"""
from django.test import SimpleTestCase

from core import score_factors
from core.attrition_risk import attrition_risk
from core.churn_risk import churn_risk
from core.payment_delay import payment_delay_risk
from core.win_probability import win_probability

CHURN_A_RISQUE = {
    'days_since_last_activity': 300,
    'contract_active': False,
    'days_since_contract_end': 200,
    'open_sav_tickets': 3,
    'last_intervention_age': 400,
}


class SocleFacteursTests(SimpleTestCase):
    """Le tri et le formatage vivent en UN endroit, et sont déterministes."""

    def test_tri_par_impact_absolu_puis_cle(self):
        facteurs = [
            score_factors.facteur('b', 'B', 0.2),
            score_factors.facteur('a', 'A', -0.2),
            score_factors.facteur('c', 'C', 0.5),
        ]
        ordre = [f.cle for f in score_factors.top_facteurs(facteurs)]
        # |0.5| d'abord ; puis 0.2 et -0.2 départagés par la CLÉ, jamais par
        # l'ordre d'insertion.
        self.assertEqual(ordre, ['c', 'a', 'b'])

    def test_contribution_negligeable_ecartee(self):
        facteurs = [
            score_factors.facteur('nul', 'Nul', 0.0),
            score_factors.facteur('reel', 'Réel', 0.3),
        ]
        self.assertEqual(
            [f.cle for f in score_factors.top_facteurs(facteurs)], ['reel'])

    def test_limite_par_defaut_est_trois(self):
        facteurs = [
            score_factors.facteur(f'c{i}', f'C{i}', 0.5 - i * 0.01)
            for i in range(8)
        ]
        self.assertEqual(len(score_factors.top_facteurs(facteurs)), 3)
        self.assertEqual(
            len(score_factors.top_facteurs(facteurs, limite=None)), 8)

    def test_sens_est_fige(self):
        self.assertEqual(score_factors.facteur('x', 'X', 0.4).sens, '+')
        self.assertEqual(score_factors.facteur('x', 'X', -0.4).sens, '-')

    def test_forme_serialisable(self):
        attendu = {'cle', 'libelle', 'impact', 'sens'}
        self.assertEqual(
            set(score_factors.facteur('x', 'X', 0.4).as_dict()), attendu)

    def test_somme_des_contributions_redonne_la_moyenne_ponderee(self):
        composantes = [
            ('a', 'A', 1.0, 0.4),
            ('b', 'B', 0.5, 0.6),
        ]
        poids_total = 1.0
        attendu = (1.0 * 0.4 + 0.5 * 0.6) / poids_total
        facteurs = score_factors.facteurs_ponderes(
            composantes, poids_total, limite=None)
        self.assertAlmostEqual(
            sum(f.impact for f in facteurs), attendu, places=4)

    def test_formatage_des_quantites(self):
        self.assertEqual(score_factors.nombre(3.0), '3')
        self.assertEqual(score_factors.nombre(2.5), '2.5')
        self.assertEqual(score_factors.jours(1), '1 jour')
        self.assertEqual(score_factors.jours(12), '12 jours')


class ChurnFacteursTests(SimpleTestCase):

    def test_trois_facteurs_en_langage_clair(self):
        resultat = churn_risk(CHURN_A_RISQUE)

        self.assertEqual(len(resultat.facteurs), 3)
        libelles = [f.libelle for f in resultat.facteurs]
        # Des phrases, valeur observée incluse — pas « inactivity: 0.8219 ».
        self.assertIn('Sans activité depuis 300 jours', libelles)
        self.assertIn('Contrat de maintenance expiré depuis 200 jours',
                      libelles)
        self.assertIn('3 ticket(s) SAV non résolu(s)', libelles)
        for f in resultat.facteurs:
            self.assertEqual(f.sens, '+')
            self.assertGreater(f.impact, 0)
        # ``factors`` garde le détail complet : rien n'est perdu.
        self.assertIn('intervention', resultat.factors)

    def test_facteurs_ordonnes_du_plus_determinant_au_moins(self):
        resultat = churn_risk(CHURN_A_RISQUE)
        impacts = [abs(f.impact) for f in resultat.facteurs]
        self.assertEqual(impacts, sorted(impacts, reverse=True))

    def test_purement_deterministe(self):
        premier = churn_risk(CHURN_A_RISQUE)
        for _ in range(3):
            suivant = churn_risk(CHURN_A_RISQUE)
            self.assertEqual(
                [(f.cle, f.impact, f.libelle) for f in suivant.facteurs],
                [(f.cle, f.impact, f.libelle) for f in premier.facteurs])

    def test_fidelite_est_un_facteur_negatif(self):
        resultat = churn_risk({
            'contract_active': True,
            'days_since_last_activity': 200,
            'open_sav_tickets': 2,
        })
        fidelite = [f for f in resultat.facteurs if f.cle == 'active_relief']
        self.assertEqual(len(fidelite), 1)
        self.assertEqual(fidelite[0].sens, '-')
        self.assertLess(fidelite[0].impact, 0)

    def test_repli_sans_feature_nexplique_rien(self):
        resultat = churn_risk({})
        self.assertTrue(resultat.used_fallback)
        self.assertEqual(resultat.facteurs, [])

    def test_score_inchange_par_lexplicabilite(self):
        """Garde-fou : NTAI31 n'a pas touché au calcul du score."""
        self.assertEqual(churn_risk(CHURN_A_RISQUE).score, 0.8228)


class WinProbabilityFacteursTests(SimpleTestCase):

    def test_facteurs_sont_des_deltas_de_probabilite(self):
        resultat = win_probability({
            'stage': 'QUOTE_SENT', 'age_days': 40,
            'canal': 'recommandation', 'relances': 2,
        })
        par_cle = {f.cle: f for f in resultat.facteurs}
        self.assertIn('stage_base', par_cle)
        self.assertEqual(par_cle['stage_base'].impact, resultat.base)
        # Un lead vieillissant TIRE la probabilité vers le bas.
        self.assertEqual(par_cle['recency'].sens, '-')
        self.assertIn('40 jours', par_cle['recency'].libelle)

    def test_lead_perdu_explique_par_un_seul_facteur(self):
        resultat = win_probability({'stage': 'QUOTE_SENT', 'perdu': True})
        self.assertEqual(resultat.probability, 0.0)
        self.assertEqual([f.cle for f in resultat.facteurs], ['perdu'])
        self.assertEqual(resultat.facteurs[0].sens, '-')

    def test_lead_signe_explique_par_un_seul_facteur(self):
        resultat = win_probability({'stage': 'SIGNED'})
        self.assertEqual(resultat.probability, 1.0)
        self.assertEqual([f.cle for f in resultat.facteurs], ['gagne'])

    def test_au_plus_trois_facteurs(self):
        resultat = win_probability({
            'stage': 'QUOTE_SENT', 'age_days': 40, 'priorite': 'haute',
            'canal': 'recommandation', 'relances': 2,
        })
        self.assertLessEqual(len(resultat.facteurs), 3)
        # Les multiplicateurs bruts restent disponibles pour les tests/l'UI.
        self.assertIn('priorite', resultat.factors)


class PaymentDelayFacteursTests(SimpleTestCase):

    def test_trois_facteurs_en_langage_clair(self):
        resultat = payment_delay_risk({
            'days_overdue': 45, 'client_avg_delay_days': 20,
            'client_prior_late_count': 4, 'relance_count': 3,
        })
        self.assertEqual(len(resultat.facteurs), 3)
        libelles = [f.libelle for f in resultat.facteurs]
        self.assertIn('Facture en retard de 45 jours', libelles)
        self.assertIn('4 facture(s) déjà payée(s) en retard', libelles)
        self.assertIn('3 relance(s) sans paiement', libelles)

    def test_repli_sans_feature_nexplique_rien(self):
        resultat = payment_delay_risk({})
        self.assertTrue(resultat.used_fallback)
        self.assertEqual(resultat.facteurs, [])

    def test_une_seule_composante_explique_tout_le_score(self):
        resultat = payment_delay_risk({'days_overdue': 90})
        self.assertEqual(len(resultat.facteurs), 1)
        self.assertAlmostEqual(
            resultat.facteurs[0].impact, resultat.score, places=4)


class AttritionFacteursTests(SimpleTestCase):

    def test_facteurs_a_lechelle_du_score(self):
        resultat = attrition_risk({
            'seniority_months': 4, 'recent_attendance_incidents': 3,
            'unplanned_absences': 2, 'last_evaluation_score': 2,
            'months_since_last_raise': 30, 'sanctions_count': 1,
        })
        self.assertEqual(len(resultat.facteurs), 3)
        # Le score est sur [0, 100] : les contributions doivent l'être aussi,
        # sinon l'explication ne serait pas comparable au score affiché.
        for f in resultat.facteurs:
            self.assertGreater(f.impact, 1.0)
            self.assertLessEqual(f.impact, 100.0)
        libelles = [f.libelle for f in resultat.facteurs]
        self.assertIn('Ancienneté de 4 mois', libelles)
        self.assertIn('Dernière évaluation : 2/5', libelles)

    def test_repli_sans_feature_nexplique_rien(self):
        resultat = attrition_risk({})
        self.assertTrue(resultat.used_fallback)
        self.assertEqual(resultat.facteurs, [])

    def test_une_seule_composante_explique_tout_le_score(self):
        resultat = attrition_risk({'sanctions_count': 3})
        self.assertEqual(len(resultat.facteurs), 1)
        self.assertAlmostEqual(
            resultat.facteurs[0].impact, resultat.score, places=2)
