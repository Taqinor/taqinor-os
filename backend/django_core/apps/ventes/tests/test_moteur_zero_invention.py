"""Le DOCUMENT RENDU n'invente aucun chiffre (audit adversarial 19/08/2026).

RÈGLE : valeur inconnue ⇒ ``None`` + omission, JAMAIS un forfait.

Chaque classe épingle un item de l'audit sur le HTML RÉELLEMENT RENDU — pas sur
la fonction qui le calcule. C'est le trou par lequel le « 87,4 % » codé en dur
est passé le 18/08 : tous les tests interrogeaient des fonctions, aucun ne
regardait le document. Les fixtures (``_moteur_fixtures``) rendent le HTML exact
qui part chez WeasyPrint, sans BD et sans WeasyPrint : ``SimpleTestCase``.
"""

from django.test import SimpleTestCase

from apps.ventes.tests import _moteur_fixtures as F


class M1FactureProxyTests(SimpleTestCase):
    """M1 — la facture « avant PV » est une DONNÉE, jamais un rétro-calcul.

    Sans les 12 factures réelles du client, le document n'imprime ni barre de
    facture, ni légende ONEE, ni « facture réduite de N % ».
    """

    def test_sans_factures_le_document_n_imprime_aucune_facture_onee(self):
        html = F.html_legacy(factures_mensuelles=None)
        self.assertNotIn("Facture ONEE", html)
        self.assertIn("&#201;conomies solaires par mois", html)

    def test_avec_factures_reelles_la_carte_reste_celle_d_avant(self):
        html = F.html_legacy()
        self.assertIn("Facture ONEE vs &#233;conomies solaires par mois", html)

    def test_le_legacy_ne_plante_plus_sur_une_serie_absente(self):
        # Le renderer résidentiel refuse une série absente et dégrade vers le
        # legacy : si le legacy explose, le devis n'a PLUS aucun rendu.
        html = F.html_legacy(factures_mensuelles=None)
        self.assertGreater(len(html), 10_000)

    def test_serie_absente_le_renderer_residentiel_refuse_de_rendre(self):
        # La dégradation VOULUE : plutôt qu'une page 1 avec un « −N % »
        # fabriqué, le renderer résidentiel se déclare hors périmètre.
        from apps.ventes.quote_engine.residential import renderer
        data = F.donnees_residentiel(factures_mensuelles=None)
        with self.assertRaises(renderer.Unsupported):
            renderer._augment(data)
        self.assertIsNone(renderer.synthese_economies(data))


class M1GhiSourceUniqueTests(SimpleTestCase):
    """M1 (suite) — une SEULE dérivation du profil GHI dans tout le backend."""

    def test_public_views_importe_les_poids_au_lieu_de_les_recopier(self):
        from apps.ventes import public_views
        from apps.ventes.quote_engine import constants
        self.assertIs(public_views.MOROCCO_SOLAR_MONTHLY_WEIGHTS,
                      constants.MOROCCO_SOLAR_MONTHLY_WEIGHTS)

    def test_les_poids_derivent_de_la_table_ghi_verrouillee(self):
        from apps.ventes.quote_engine import constants
        attendu = [round(g / sum(constants.GHI), 6) for g in constants.GHI]
        self.assertEqual(constants.MOROCCO_SOLAR_MONTHLY_WEIGHTS, attendu)
