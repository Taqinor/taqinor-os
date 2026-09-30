"""ERR-QAC-GRAPHE-MENSUEL-CLE-SOLAIRE — hors modèle « horaire », la série
mensuelle d'économie est la clé solaire PLAFONNÉE à la facture de chaque mois.

Avant : ``pricing.calculate_savings_roi`` répartissait l'économie annuelle par
la clé FIXE, le graphe plancher chaque mois à sa facture, et la page 1
imprimait une économie annuelle 3 à 12 % sous celle de la carte option
(DEV-202609-0077 : carte 23 776, graphe 22 412). Ici : Σ des douze mois =
économie de la carte, aucun mois au-dessus de sa facture.

Aucune base : helper pur ``pricing.repartir_economie_plafonnee``.

Run : ``python manage.py test apps.ventes.tests.test_err_graphe_mensuel_cle_solaire``
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.pricing import (
    CLE_SOLAIRE_MENSUELLE, repartir_economie_plafonnee,
)

# 24 600 MAD/an de factures (≈ 2 050/mois, un peu plus l'été) — la forme
# de DEV-202609-0077 : économie de la carte 23 776 (97 % de la facture).
FACTURES = [2000, 1900, 1950, 2000, 2050, 2150,
            2250, 2250, 2100, 2000, 1950, 2000]
ECO_CARTE = 23776


def _ancienne_serie_graphe(eco, factures):
    """Ce que le graphe dessinait : la clé fixe planchée à la facture."""
    return [min(round(eco * f), fa)
            for f, fa in zip(CLE_SOLAIRE_MENSUELLE, factures)]


class RepartitionPlafonneeTests(SimpleTestCase):

    def test_repro_ancienne_cle_perd_le_debordement(self):
        # Le défaut d'origine : la clé fixe dépasse la facture en été.
        self.assertLess(sum(_ancienne_serie_graphe(ECO_CARTE, FACTURES)),
                        ECO_CARTE - 1000)

    def test_somme_egale_economie_de_la_carte_et_aucun_mois_au_dessus(self):
        serie = repartir_economie_plafonnee(ECO_CARTE, FACTURES)
        self.assertEqual(len(serie), 12)
        self.assertEqual(sum(serie), ECO_CARTE)
        for eco_m, facture_m in zip(serie, FACTURES):
            self.assertLessEqual(eco_m, facture_m)
            self.assertGreaterEqual(eco_m, 0)
            self.assertIsInstance(eco_m, int)

    def test_economie_faible_suit_la_cle_solaire(self):
        # Aucun plafond atteint : la forme saisonnière reste celle de la clé.
        serie = repartir_economie_plafonnee(6000, FACTURES)
        self.assertEqual(sum(serie), 6000)
        attendu = [6000 * f for f in CLE_SOLAIRE_MENSUELLE]
        for v, a in zip(serie, attendu):
            self.assertLessEqual(abs(v - a), 1)

    def test_economie_superieure_aux_factures_plafonnee_au_total(self):
        serie = repartir_economie_plafonnee(sum(FACTURES) + 5000, FACTURES)
        self.assertEqual(serie, FACTURES)

    def test_entrees_inexploitables(self):
        self.assertIsNone(repartir_economie_plafonnee(1000, [100] * 11))
        self.assertIsNone(repartir_economie_plafonnee(1000, None))
        self.assertEqual(repartir_economie_plafonnee(0, FACTURES), [0] * 12)
