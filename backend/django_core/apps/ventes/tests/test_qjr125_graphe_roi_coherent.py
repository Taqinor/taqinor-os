"""QJR125 — le graphe ROI dit la même chose que sa courbe.

Deux défauts d'une même carte (« Gain cumulé sur 25 ans — Point de retour sur
investissement ») :

(a) l'étoile « ROI ~N ans » était posée à l'abscisse de ``roi_s``/``roi_a``,
    qui redevient un payback LINÉAIRE (``builder`` : ``_ref_total / eco``) dès
    que l'étude porte ses propres économies, alors que la courbe tracée est le
    cashflow NON linéaire (dégradation, rendement batterie, provision
    onduleur) : le point d'équilibre annoncé ne coïncidait pas avec le dessiné ;
(b) quand ``cashflow_sans``/``cashflow_avec`` manquaient ou faisaient moins de
    25 points, la courbe retombait sur la droite « économie plate » — que le
    commentaire M5 du moteur décrit lui-même comme fausse de +14,5 % et
    +36,6 % sur le gain final — tracée sans aucune mention.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr125_graphe_roi_coherent -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as moteur
from apps.ventes.tests import _moteur_fixtures as F


class TestEtoileSurLaCourbe(SimpleTestCase):
    """(a) — l'étoile tombe sur l'ordonnée ZÉRO de la série tracée."""

    def test_le_roi_derive_du_croisement_a_zero(self):
        moteur.apply_quote_data(F.donnees_legacy())
        for cumul in (moteur.CUMUL_S, moteur.CUMUL_A):
            roi = moteur._roi_de_la_courbe(cumul)
            self.assertIsNotNone(roi)
            annee = int(roi)
            # Ordonnée interpolée à l'abscisse de l'étoile ≈ 0.
            y = (cumul[annee]
                 + (roi - annee) * (cumul[annee + 1] - cumul[annee]))
            echelle = max(abs(cumul[0]), 1.0)
            self.assertLess(abs(y) / echelle, 0.02,
                            "l'étoile ne tombe pas sur le zéro de sa courbe")
            # …et l'année encadre bien le changement de signe.
            self.assertLess(cumul[annee], 0)
            self.assertGreaterEqual(cumul[annee + 1], 0)

    def test_precision_a_un_dixieme_d_annee(self):
        # Croisement EXACT à 2,5 ans sur une série synthétique.
        cumul = [-1000, -500, 0, 500]
        self.assertEqual(moteur._roi_de_la_courbe(cumul), 2.0)
        cumul = [-1000, -750, -250, 250]
        self.assertAlmostEqual(moteur._roi_de_la_courbe(cumul), 2.5, delta=0.1)

    def test_courbe_qui_ne_croise_jamais_zero_na_pas_d_etoile(self):
        self.assertIsNone(moteur._roi_de_la_courbe([-1000, -900, -800]))

    def test_l_etoile_ne_suit_plus_le_payback_lineaire(self):
        """Un payback annoncé DIVERGENT ne déplace plus l'étoile."""
        moteur.apply_quote_data(F.donnees_legacy(roi_s=1.0, roi_a=1.0))
        vrai = moteur._roi_de_la_courbe(moteur.CUMUL_S)
        self.assertNotAlmostEqual(vrai, 1.0, delta=0.2)


class TestAucunGrapheSansCashflowReel(SimpleTestCase):
    """(b) — la droite « économie plate » n'est plus TRACÉE."""

    def test_carte_omise_quand_le_cumul_manque(self):
        donnees = F.donnees_legacy()
        sans_cf = {k: v for k, v in donnees.items()
                   if k not in ("cashflow_sans", "cashflow_avec")}
        html = moteur.render_html_for(sans_cf)
        self.assertNotIn("Gain cumul", html)

    def test_carte_omise_quand_la_serie_est_trop_courte(self):
        donnees = F.donnees_legacy()
        donnees["cashflow_sans"] = donnees["cashflow_sans"][:10]
        html = moteur.render_html_for(donnees)
        self.assertNotIn("Gain cumul", html)

    def test_carte_rendue_avec_les_deux_series_reelles(self):
        self.assertIn("Gain cumul", F.html_legacy())

    def test_les_drapeaux_disent_la_verite(self):
        moteur.apply_quote_data(F.donnees_legacy())
        self.assertTrue(moteur.CUMUL_S_REEL)
        self.assertTrue(moteur.CUMUL_A_REEL)
        donnees = F.donnees_legacy()
        del donnees["cashflow_avec"]
        moteur.apply_quote_data(donnees)
        self.assertTrue(moteur.CUMUL_S_REEL)
        self.assertFalse(moteur.CUMUL_A_REEL)

    def test_le_repli_reste_bien_forme_pour_ses_lecteurs(self):
        """Le repli n'est plus tracé, mais la liste garde ses 26 points."""
        donnees = F.donnees_legacy()
        sans_cf = {k: v for k, v in donnees.items()
                   if k not in ("cashflow_sans", "cashflow_avec")}
        moteur.apply_quote_data(sans_cf)
        self.assertEqual(len(moteur.CUMUL_S), 26)
        self.assertEqual(moteur.CUMUL_S[25],
                         -donnees["total_sans"] + donnees["eco_s_ann"] * 25)


class TestBrancheAffichee(SimpleTestCase):
    """Seule la ou les branches AFFICHÉES exigent leur cumul réel."""

    def test_scenario_mono_option_ne_reclame_que_sa_branche(self):
        donnees = F.donnees_legacy(scenario="Sans batterie")
        del donnees["cashflow_avec"]
        html = moteur.render_html_for(donnees)
        self.assertIn("Gain cumul", html)
