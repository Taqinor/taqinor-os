"""Le DOCUMENT RENDU n'invente aucun chiffre (audit adversarial 19/08/2026).

RÈGLE : valeur inconnue ⇒ ``None`` + omission, JAMAIS un forfait.

Chaque classe épingle un item de l'audit sur le HTML RÉELLEMENT RENDU — pas sur
la fonction qui le calcule. C'est le trou par lequel le « 87,4 % » codé en dur
est passé le 18/08 : tous les tests interrogeaient des fonctions, aucun ne
regardait le document. Les fixtures (``_moteur_fixtures``) rendent le HTML exact
qui part chez WeasyPrint, sans BD et sans WeasyPrint : ``SimpleTestCase``.
"""

import re

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


class M2PuissanceInventeeParLePrixTests(SimpleTestCase):
    """M2 — le kWc n'est plus déduit du prix ; inconnu ⇒ vignettes omises."""

    INCONNUE = dict(puissance_inconnue=True, puissance_kwc=None,
                    nb_panneaux=None, watt_par_panneau=None, prod_kwh=0)

    def test_puissance_inconnue_le_document_n_imprime_ni_kwc_ni_panneaux(self):
        html = F.html_legacy(**self.INCONNUE)
        self.assertNotIn("Puissance Install", html)
        self.assertNotIn("panneaux &#215;", html)

    def test_puissance_inconnue_omet_production_et_economies(self):
        html = F.html_legacy(**self.INCONNUE)
        self.assertNotIn("Production Annuelle", html)
        self.assertNotIn("&#201;conomies estim&#233;es / an", html)
        self.assertNotIn("Retour en", html)

    def test_puissance_connue_les_vignettes_restent(self):
        html = F.html_legacy()
        self.assertIn("Puissance Install", html)
        self.assertIn("Production Annuelle", html)
        self.assertIn("&#201;conomies estim&#233;es / an", html)

    def test_une_page_omet_le_resume_systeme_sans_puissance(self):
        html = F.html_onepage(**self.INCONNUE)
        self.assertNotIn("Puissance cr&#234;te", html)
        self.assertNotIn("Prix par kWc", html)

    def test_detection_panneau_elargie_aux_designations_reelles(self):
        from apps.ventes.quote_engine import builder
        for designation in ("Panneau Canadien Solar 710W", "Module PV 550W",
                            "Module photovoltaïque 550 W",
                            "Canadian Solar TOPHiKu7 710 Wc"):
            self.assertTrue(builder._is_panel(designation), designation)
        # Une marque seule, ou un équipement d'une autre famille, jamais.
        for designation in ("Canadian Solar", "Onduleur réseau Huawei 10kW",
                            "Onduleur hybride Deye 10kW", "Batterie Dyness 10 kWh",
                            "Smart Meter", "Coffret PV DC",
                            "Module de communication", "Structures acier"):
            self.assertFalse(builder._is_panel(designation), designation)


class M3WattNonLuTests(SimpleTestCase):
    """M3 — « × 710 W » n'est plus imprimé sans lecture, et la désignation
    facturée n'est jamais réécrite."""

    def test_watt_non_lu_le_document_ecrit_n_panneaux_sans_puissance(self):
        html = F.html_legacy(watt_par_panneau=None)
        self.assertNotIn("panneaux &#215;", html)
        self.assertIn("8 panneaux</div>", html)

    def test_watt_lu_la_puissance_unitaire_reste_imprimee(self):
        html = F.html_legacy()
        self.assertIn("8 panneaux &#215; 710&nbsp;W", html)

    def test_la_designation_facturee_n_est_jamais_suffixee(self):
        # Le libellé contractuel de la ligne s'affiche tel quel : le moteur
        # ajoutait « 710 Wc » derrière, donc engageait une caractéristique
        # que le devis ne porte pas.
        html = F.html_legacy()
        self.assertIn("Panneau Canadien Solar 710W", html)
        self.assertNotIn("Panneau Canadien Solar 710W 710&#160;Wc", html)
        self.assertNotIn("710W 710", html)

    def test_le_moteur_lit_le_watt_sans_repli_catalogue(self):
        from apps.ventes.quote_engine import builder

        class _L:
            def __init__(self, designation, quantite):
                self.designation = designation
                self.quantite = quantite
                self.produit = None

        # Aucune puissance lisible nulle part → None, jamais 710.
        nb, watt = builder.panneaux_et_watt_lu([_L("Panneaux solaires", 16)])
        self.assertEqual(nb, 16)
        self.assertIsNone(watt)
        # Le contrat HISTORIQUE (KPI interne) garde, lui, son repli documenté.
        self.assertEqual(
            builder.puissance_panneaux_lignes([_L("Panneaux solaires", 16)]),
            (16, builder._DEFAULT_WATT))
        # Puissance écrite dans la désignation → elle est LUE.
        self.assertEqual(
            builder.panneaux_et_watt_lu([_L("Panneau Jinko 585W", 10)]),
            (10, 585))


class M4UnePageMemeBrancheTests(SimpleTestCase):
    """M4 — l'économie du format UNE PAGE vient de la branche facturée.

    Le document chiffre l'option SANS batterie et le dit ; il affichait
    pourtant ``max(éco sans, éco avec)``, donc l'économie de l'option AVEC.
    """

    @staticmethod
    def _eco(html):
        """Montant d'économie RENDU dans le résumé système, sans séparateurs."""
        i = html.find("conomie annuelle")
        if i < 0:
            return None
        m = re.search(r">([\d   ]+) MAD/an<", html[i:i + 300])
        if not m:
            return None
        return re.sub(r"[^\d]", "", m.group(1))

    def test_branche_sans_affiche_l_economie_sans_batterie(self):
        d = F.donnees_legacy()
        html = F.html_onepage(onepage_branche="sans")
        self.assertEqual(self._eco(html), str(d["eco_s_ann"]))

    def test_branche_avec_affiche_l_economie_avec_batterie(self):
        d = F.donnees_legacy()
        html = F.html_onepage(onepage_branche="avec")
        self.assertEqual(self._eco(html), str(d["eco_a_ann"]))

    def test_branche_inconnue_omet_la_vignette(self):
        self.assertIsNone(self._eco(F.html_onepage()))

    def test_jamais_le_maximum_des_deux_branches(self):
        d = F.donnees_legacy()
        self.assertNotEqual(d["eco_s_ann"], d["eco_a_ann"],
                            "fixture invalide : les deux branches doivent "
                            "différer pour que le test prouve quelque chose")
        maxi = str(max(d["eco_s_ann"], d["eco_a_ann"]))
        self.assertNotEqual(self._eco(F.html_onepage(onepage_branche="sans")),
                            maxi)


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
