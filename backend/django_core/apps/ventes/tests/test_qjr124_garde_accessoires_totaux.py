"""QJR124 — une ligne retirée du tableau est retirée des TOTAUX (garde Huawei).

``_guard_huawei_accessories`` supprimait les lignes « smart meter / wifi /
dongle » du TABLEAU une-page APRÈS que ``totaux_all`` a été figé sur les lignes
NON filtrées. Chemin atteignable prouvé : la branche « devis libre / pompage /
scénario non apparié » du builder posait ``onepage_source = items`` — la liste
COMPLÈTE — car le filtrage QF9 ne s'applique qu'à ``sans_items``/``avec_items``.
Le client lisait alors un « Total TTC » incluant un accessoire absent du
tableau.

Le re-filtrage au rendu du une-page est supprimé, et l'invariant qui reste est
celui-ci : **le total imprimé est la somme des lignes imprimées**.

QJR300 (01/09/2026) — la liste libre n'est PLUS filtrée du tout en amont : le
noyau monnaie ne retire l'accessoire que dans le cas DEUX-OPTIONS, et un
document qui retire une ligne que l'échéancier facture rouvre « deux prix pour
la même vente ». Les assertions de ce module portent donc sur l'ACCORD
tableau ↔ total, plus sur la disparition de la ligne.

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


def _regle_qf9(items):
    """QJR408 — LA règle QF9, telle que le builder l'applique aux paniers d'un
    document à deux options. Le moteur de rendu portait une SECONDE passe
    (``_guard_huawei_accessories``) qui reclassait sur la désignation seule :
    elle est supprimée, et ces assertions épinglent désormais le propriétaire
    unique."""
    from apps.ventes.quote_engine import builder as _b
    from apps.ventes.utils.options import retirer_accessoires_huawei
    return retirer_accessoires_huawei(
        list(items), classement=_b._item_classement, marque=_b._item_marque)


class TestGardeSuitLaRegleDuNoyau(SimpleTestCase):
    """QJR301 — le garde-fou legacy ne porte plus sa propre règle : il délègue
    à ``utils.options.retirer_accessoires_huawei``. Le verdict d'un panier
    mixte est donc celui du noyau (``all``, le plus conservateur), et plus le
    ``any`` local — deux verdicts pour le même panier, c'était le défaut."""

    def test_liste_sans_onduleur_huawei_perd_l_accessoire(self):
        garde = _regle_qf9([ONDULEUR_DEYE, SMART_METER])
        self.assertEqual([it["designation"] for it in garde],
                         ["Onduleur hybride Deye 5kW"])

    def test_liste_a_deux_marques_perd_l_accessoire(self):
        garde = _regle_qf9(
            [ONDULEUR_HUAWEI, ONDULEUR_DEYE, SMART_METER])
        self.assertNotIn("Smart Meter", [it["designation"] for it in garde])

    def test_liste_sans_onduleur_perd_l_accessoire_orphelin(self):
        # Règle du noyau : sans onduleur identifiable, l'accessoire est
        # orphelin. Inatteignable par le rendu (une option ne se rend jamais
        # sans onduleur), épinglé pour que les deux moitiés restent d'accord.
        garde = _regle_qf9([SMART_METER])
        self.assertEqual(garde, [])


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

    def test_accessoire_orphelin_reste_dans_les_lignes_ET_dans_le_total(self):
        """QJR300 — la liste libre N'EST PLUS filtrée : le noyau monnaie ne la
        filtre pas non plus, et un document qui retire une ligne que
        l'échéancier facture rouvre « deux prix pour la même vente ». Ce que ce
        test garde de QJR124 : le TABLEAU et le TOTAL décrivent le MÊME panier.
        """
        data = self._data(
            [("Onduleur hybride Deye 5kW", 1, "20000"),
             ("Smart Meter", 1, "1500"),
             ("Panneau Canadian Solar 580W", 10, "1000")],
            "DEV-QJR124-A")
        designations = [it["designation"] for it in data["all_items"]]
        self.assertIn("Smart Meter", designations)
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
        # QJR300 — la ligne est SERVIE (plus de filtrage de la liste libre) ;
        # l'invariant QJR124 tenu ici reste « le total imprimé == Σ des lignes
        # imprimées ».
        self.assertIn("Smart Meter", html)
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
