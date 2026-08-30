"""QJR124 — une ligne retirée du tableau est retirée des TOTAUX (garde Huawei).

``_guard_huawei_accessories`` supprimait les lignes « smart meter / wifi /
dongle » du TABLEAU une-page APRÈS que ``totaux_all`` a été figé sur les lignes
NON filtrées. Chemin atteignable prouvé : la branche « devis libre / pompage /
scénario non apparié » du builder posait ``onepage_source = items`` — la liste
COMPLÈTE — car le filtrage QF9 ne s'applique qu'à ``sans_items``/``avec_items``.
Le client lisait alors un « Total TTC » incluant un accessoire absent du
tableau.

Le filtrage est désormais fait EN AMONT (builder), avant le calcul des totaux ;
le re-filtrage au rendu du une-page est supprimé. Et la détection Huawei du
garde-fou passe de ``all`` à ``any`` : une liste portant deux marques
d'onduleur garde le Smart Meter de l'onduleur Huawei réellement facturé.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr124_garde_accessoires_totaux -v 2
"""
import re
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine import generate_devis_premium as moteur
from apps.ventes.tests.test_qf9_huawei_accessories import (
    make_client, make_company, make_devis, make_user)


ONDULEUR_DEYE = {"designation": "Onduleur hybride Deye 5kW", "marque": "Deye",
                 "quantite": 1, "prix_unit_ht": 20000.0,
                 "prix_unit_ttc": 24000.0, "taux_tva": 20.0}
ONDULEUR_HUAWEI = {"designation": "Onduleur réseau Huawei 5kW",
                   "marque": "Huawei", "quantite": 1, "prix_unit_ht": 12000.0,
                   "prix_unit_ttc": 14400.0, "taux_tva": 20.0}
SMART_METER = {"designation": "Smart Meter", "marque": "", "quantite": 1,
               "prix_unit_ht": 1500.0, "prix_unit_ttc": 1800.0,
               "taux_tva": 20.0}


class TestGardeAnyPlutotQueAll(SimpleTestCase):
    """Un accessoire n'est retiré que s'il est ORPHELIN."""

    def test_liste_sans_onduleur_huawei_perd_l_accessoire(self):
        garde = moteur._guard_huawei_accessories([ONDULEUR_DEYE, SMART_METER])
        self.assertEqual([it["designation"] for it in garde],
                         ["Onduleur hybride Deye 5kW"])

    def test_liste_a_deux_marques_garde_l_accessoire_de_huawei(self):
        # ``all`` retirait le Smart Meter de l'onduleur Huawei RÉELLEMENT
        # facturé dès qu'un second onduleur d'une autre marque figurait.
        garde = moteur._guard_huawei_accessories(
            [ONDULEUR_HUAWEI, ONDULEUR_DEYE, SMART_METER])
        self.assertIn("Smart Meter", [it["designation"] for it in garde])

    def test_liste_sans_onduleur_est_rendue_telle_quelle(self):
        garde = moteur._guard_huawei_accessories([SMART_METER])
        self.assertEqual(len(garde), 1)


class TestUnePageNeReFiltrePlus(SimpleTestCase):
    """Le rendu une-page imprime EXACTEMENT les lignes qu'on lui donne."""

    def test_les_lignes_servies_sont_toutes_rendues(self):
        # QJR162 — charge utile CANONIQUE (le moteur lève sans totaux).
        from apps.ventes.tests import _moteur_fixtures as F

        data = F.donnees_legacy(pdf_mode="onepage")
        # Charge utile « devis libre » : le builder l'aurait déjà filtrée ;
        # le renderer ne doit plus rien retirer de son côté.
        data["all_items"] = [ONDULEUR_DEYE, SMART_METER]
        data["totaux_all"] = {
            "ht_brut": 21500.0, "remise": 0.0, "ht_net": 21500.0,
            "tva": 4300.0, "ttc": 25800.0,
            "tva_par_taux": [{"taux": 20, "montant": 4300.0}],
        }
        html = moteur.render_html_for(data)
        self.assertIn("Smart Meter", html)
        self.assertIn("Onduleur hybride Deye 5kW", html)


class TestBuilderFiltreAvantLesTotaux(TestCase):
    """Devis LIBRE + onduleur Deye + Smart Meter : tableau et total d'accord."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _data(self, lignes, reference, etude_params=None):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           reference, etude_params=etude_params)
        return build_quote_data(devis, {"pdf_mode": "onepage"})

    def test_accessoire_orphelin_retire_des_lignes_ET_du_total(self):
        data = self._data(
            [("Onduleur hybride Deye 5kW", 1, "20000"),
             ("Smart Meter", 1, "1500"),
             ("Panneau Canadian Solar 580W", 10, "1000")],
            "DEV-QJR124-A")
        designations = [it["designation"] for it in data["all_items"]]
        self.assertNotIn("Smart Meter", designations)
        somme = sum(Decimal(str(it["quantite"])) * Decimal(str(it["prix_unit_ttc"]))
                    for it in data["all_items"])
        self.assertAlmostEqual(float(somme), float(data["totaux_all"]["ttc"]),
                               places=2)
        # …et le total d'affichage suit la MÊME liste.
        self.assertAlmostEqual(float(data["display_total"]),
                               float(data["totaux_all"]["ttc"]), places=2)

    def test_le_pdf_une_page_somme_ses_lignes_au_total_imprime(self):
        data = self._data(
            [("Onduleur hybride Deye 5kW", 1, "20000"),
             ("Smart Meter", 1, "1500"),
             ("Panneau Canadian Solar 580W", 10, "1000")],
            "DEV-QJR124-B")
        html = moteur.render_html_for(data)
        self.assertNotIn("Smart Meter", html)
        ttc = re.search(
            r'>Total TTC</span>'
            r'<span style="display:inline-block;min-width:110px;[^"]*">'
            r'([^<]*)</span>', html)
        self.assertIsNotNone(ttc, "Total TTC introuvable dans le une-page")
        imprime = Decimal(re.sub(r"[^0-9,]", "", ttc.group(1))
                          .replace(",", "."))
        somme = sum(
            Decimal(str(it["quantite"])) * Decimal(str(it["prix_unit_ttc"]))
            for it in data["all_items"])
        self.assertEqual(imprime.quantize(Decimal("0.01")),
                         somme.quantize(Decimal("0.01")))

    def test_un_devis_huawei_garde_ses_accessoires(self):
        data = self._data(
            [("Onduleur réseau Huawei 5kW", 1, "12000"),
             ("Smart Meter", 1, "1500"),
             ("Panneau Canadian Solar 580W", 10, "1000")],
            "DEV-QJR124-C")
        designations = [it["designation"] for it in data["all_items"]]
        self.assertIn("Smart Meter", designations)
        somme = sum(Decimal(str(it["quantite"])) * Decimal(str(it["prix_unit_ttc"]))
                    for it in data["all_items"])
        self.assertAlmostEqual(float(somme), float(data["totaux_all"]["ttc"]),
                               places=2)
