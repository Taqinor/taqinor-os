"""Moteur premium — le BUILDER et ses chiffres (quasi aucun rendu PDF).

Scindé de `test_quote_engine` le 2026-08-19 (voir ce module).

Correspondance devis OS → dict du générateur (puissance dérivée des
panneaux, découpe par batterie, TTC/remise), dossier moyenne tension,
productible canonique, payback honnête, barèmes ONEE et économies, garde
« aucun chiffre inventé », wattage depuis la fiche technique, câblage du
site du locataire.

Fixtures partagées : `apps.ventes.tests._quote_engine_common`.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_quote_engine_builder -v 2
"""

import re
from decimal import Decimal

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)


class TestBuildQuoteData(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_power_derived_from_panels(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ])
        data = build_quote_data(devis)
        # 10 panels x 450W = 4.5 kWc
        self.assertEqual(data['nb_panneaux'], 10)
        self.assertEqual(data['watt_par_panneau'], 450)
        self.assertEqual(data['puissance_kwc'], 4.5)
        # ROI fields present and sane
        self.assertGreater(data['prod_kwh'], 0)
        self.assertGreater(data['eco_a_ann'], 0)
        self.assertIn('eco_s_monthly', data)
        self.assertEqual(len(data['eco_s_monthly']), 12)

    def test_real_catalogue_panel_reports_its_true_wattage(self):
        """Le devis auto utilise un VRAI panneau du catalogue : la désignation
        porte sa puissance (« Panneau Canadien Solar 710W ») et le moteur lit
        710 — jamais une valeur inventée."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '10', '1400'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-QE-REAL')
        data = build_quote_data(devis)
        self.assertEqual(data['nb_panneaux'], 10)
        self.assertEqual(data['watt_par_panneau'], 710)  # vraie puissance lue
        self.assertEqual(data['puissance_kwc'], 7.1)

    def test_unparseable_panel_defaults_to_catalogue_standard_not_stale_450(self):
        """Repli SÛR : une ligne panneau sans puissance lisible (ni désignation
        ni nom produit) ne doit PLUS inventer l'ancien 450 W obsolète — elle
        retombe sur le STANDARD du catalogue (710 W), panneau moderne réaliste.
        Garde la régression « pourquoi 450 W alors que la donnée est là ? »."""
        from apps.ventes.quote_engine import build_quote_data
        from apps.ventes.quote_engine.builder import _DEFAULT_WATT
        # désignation SANS chiffre de puissance + produit lié au même nom : aucun
        # wattage lisible → le repli s'applique.
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau photovoltaïque monocristallin', '12', '1400'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-QE-NOWATT')
        data = build_quote_data(devis)
        self.assertEqual(data['nb_panneaux'], 12)
        # le repli est le standard catalogue, JAMAIS l'ancien 450 périmé
        self.assertEqual(_DEFAULT_WATT, 710)
        self.assertEqual(data['watt_par_panneau'], 710)
        self.assertNotEqual(data['watt_par_panneau'], 450)

    def test_no_hybrid_means_single_option_no_fabricated_battery(self):
        """RÈGLE DURE : sans onduleur hybride, l'option « avec batterie » ne
        se rend pas — document à option unique, jamais de batterie fabriquée
        sur une option sans onduleur."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '8', '2000'),
            ('Onduleur reseau', '1', '14000'),
        ])
        data = build_quote_data(devis)
        self.assertEqual(data['scenario'], 'Sans batterie')
        self.assertEqual(data['recommended'], 'Sans batterie')
        sans = [it['designation'].lower() for it in data['sans_items']]
        self.assertTrue(any('reseau' in d or 'réseau' in d for d in sans))

    def test_residential_hybrid_without_battery_never_synthesizes_a_module(self):
        """Z1 (ORDRE FONDATEUR, 20/08/2026) — hybride sans ligne batterie :
        AUCUNE batterie n'est fabriquée. Le moteur ajoutait ici une « Batterie
        5 kWh » de catalogue pour composer l'option « Avec batterie » : un
        composant et un prix INVENTÉS sur un document client. Le devis devient
        mono-option « Sans batterie » (factuellement vrai) et sa composition
        porte TOUTES ses lignes réelles — l'onduleur hybride compris, donc son
        total reste le total du devis."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '8', '2000'),
            ('Onduleur hybride 5kW', '1', '14000'),
        ])
        data = build_quote_data(devis)
        self.assertEqual(data['scenario'], 'Sans batterie')
        self.assertFalse(data['avec_ok'])
        self.assertTrue(data['sans_ok'])
        self.assertFalse(data['deux_options'])
        # Aucune ligne « batterie » nulle part dans le document rendu.
        for panier in ('sans_items', 'avec_items'):
            self.assertFalse(
                any('batterie' in it['designation'].lower()
                    for it in data[panier]),
                f"une batterie fabriquée a survécu dans {panier}")
        # L'onduleur hybride RÉEL est bien dans l'option rendue (il n'est pas
        # perdu au passage) et le total du document = total des lignes.
        sans = [it['designation'].lower() for it in data['sans_items']]
        self.assertTrue(any('hybride' in d for d in sans))
        attendu = round(sum(it['quantite'] * it['prix_unit_ht']
                            for it in data['sans_items']), 2)
        self.assertAlmostEqual(data['totaux_sans']['ht_brut'], attendu, places=2)

    def test_hybrid_without_battery_still_renders_a_pdf(self):
        """Z1 — la règle dure « une option ne se rend jamais sans onduleur » ne
        doit PAS refuser un devis dont le seul onduleur est hybride : il porte
        bien un onduleur, c'est la batterie qui manque."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '8', '2000'),
            ('Onduleur hybride 5kW', '1', '14000'),
        ], reference='DEV-QE-HYBNOBAT')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertEqual(data['nb_options'], 1)

    def test_large_plant_never_gets_token_battery(self):
        """> 15 kWc sans batterie : pas de batterie symbolique fabriquée —
        l'option avec batterie est indisponible."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 710W', '176', '1166.67'),
            ('Onduleur réseau 100kW', '1', '65000'),
            ('Onduleur hybride 20kW', '1', '40000'),
        ])
        data = build_quote_data(devis)
        # hybride présent mais pas de batterie et 124.96 kWc → pas de synthèse
        avec = [it['designation'].lower() for it in data['avec_items']]
        self.assertFalse(any('batterie' in d for d in avec))
        self.assertEqual(data['scenario'], 'Sans batterie')

    def test_no_inverter_at_all_fails_option_pdf(self):
        """Un devis sans aucun onduleur ne peut pas produire le PDF à options."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '6', '1500'),
            ('Batterie 5 kWh', '1', '16000'),
        ], reference='DEV-QE-NOINV')
        with self.assertRaises(ValueError):
            build_quote_data(devis, {'pdf_mode': 'full'})
        # …mais le format une page (liste simple, sans options) reste possible
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertEqual(data['pdf_mode'], 'onepage')

    def test_option_split_routes_both_inverters(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Onduleur réseau', '1', '11700'),
            ('Onduleur hybride', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Installation', '1', '4000'),
        ], etude_params=DEUX_OPTIONS)
        data = build_quote_data(devis)
        sans = [it['designation'].lower() for it in data['sans_items']]
        avec = [it['designation'].lower() for it in data['avec_items']]
        # Option 1: réseau inverter, NO hybrid, NO battery.
        self.assertTrue(any('réseau' in d or 'reseau' in d for d in sans))
        self.assertFalse(any('hybride' in d for d in sans))
        self.assertFalse(any('batterie' in d for d in sans))
        # Option 2: hybrid inverter + battery, NO réseau inverter.
        self.assertTrue(any('hybride' in d for d in avec))
        self.assertTrue(any('batterie' in d for d in avec))
        self.assertFalse(any('réseau' in d or 'reseau' in d for d in avec))

    def test_existing_battery_not_duplicated(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '6', '1500'),
            ('Onduleur hybride 5kW', '1', '14000'),
            ('Batterie 5 kWh', '1', '16000'),
        ])
        data = build_quote_data(devis)
        # Battery already present: avec keeps the single one (no synthesis).
        batteries = [it for it in data['avec_items']
                     if 'batterie' in it['designation'].lower()]
        self.assertEqual(len(batteries), 1)

    def test_ttc_conversion_and_global_discount(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1000'),
        ], remise_globale='10')
        # format une page : pas d'options, la règle onduleur ne s'applique pas
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        # 10 x 1000 HT x1.20 TTC = 12000 before; -10% global = 10800.
        self.assertEqual(data['total_sans_before'], 12000.0)
        self.assertEqual(data['discount_pct'], 10.0)
        self.assertEqual(data['total_sans'], 10800)


class TestDossierMoyenneTension(TestCase):
    """QXMT — un dossier raccordé en MT ne porte JAMAIS un chiffre BT.

    ``solar.js`` pose ``tension_raccordement='MT'`` et, sans répartition
    horaire, laisse ``economies_annuelles`` à ``None`` : l'écran affiche alors
    « économies et payback volontairement omis ». Le PDF, lui, ne lisait aucune
    de ces clés et retombait sur ``calculate_savings_roi`` — le tarif BASSE
    TENSION de l'ONEE. Le client recevait donc une économie et un payback qui
    ne sont pas les siens."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _data(self, etude_params, reference):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '120', '1500'),
            ('Onduleur réseau 50kW', '1', '60000'),
        ], reference=reference, etude_params=etude_params)
        return build_quote_data(devis, {'pdf_mode': 'full'})

    def test_mt_sans_economies_detude_masque_le_bloc(self):
        data = self._data({'tension_raccordement': 'MT'}, 'DEV-MT-0001')
        self.assertTrue(data['masquer_economies'])
        # Aucune mention de barème ne part avec un chiffre qui n'existe pas.
        self.assertEqual(data['tarif_mt_mention'], '')

    def test_mt_avec_economies_detude_rend_la_mention_source(self):
        from apps.ventes.quote_engine.constants_82_21 import MENTION_MT
        data = self._data({'tension_raccordement': 'MT',
                           'production_annuelle': 82000,
                           'economies_annuelles': 96000}, 'DEV-MT-0002')
        self.assertFalse(data['masquer_economies'])
        self.assertEqual(data['tarif_mt_mention'], MENTION_MT)
        self.assertIn('one.org.ma', data['tarif_mt_mention'])
        # Le chiffre servi EST celui de l'étude, jamais un recalcul BT.
        self.assertEqual(data['eco_s_ann'], 96000)

    def test_un_dossier_BT_est_strictement_inchange(self):
        data = self._data({'tension_raccordement': 'BT'}, 'DEV-MT-0003')
        self.assertFalse(data['masquer_economies'])
        self.assertEqual(data['tarif_mt_mention'], '')
        self.assertGreater(data['eco_s_ann'], 0)

    def test_un_devis_sans_etude_est_strictement_inchange(self):
        data = self._data(None, 'DEV-MT-0004')
        self.assertFalse(data['masquer_economies'])
        self.assertEqual(data['tarif_mt_mention'], '')

    def test_le_renderer_industriel_n_herite_plus_du_chiffre_BT(self):
        """Le repli ``eco_s_ann``/``roi_s`` était la porte d'entrée du chiffre
        BT sur le document CFO."""
        from apps.ventes.quote_engine.industriel import renderer as industriel

        data = self._data({'tension_raccordement': 'MT'}, 'DEV-MT-0005')
        self.assertGreater(data['eco_s_ann'], 0)   # la valeur BT EXISTE…
        augmentee = industriel._augment(data)
        self.assertTrue(augmentee['ind_masquer_economies'])
        self.assertEqual(augmentee['ind_economies'], 0)   # …et n'est PAS reprise
        self.assertIsNone(augmentee['ind_payback'])

    def test_le_renderer_commercial_n_herite_plus_du_chiffre_BT(self):
        from apps.ventes.quote_engine.commercial import renderer as commercial

        data = self._data({'tension_raccordement': 'MT'}, 'DEV-MT-0006')
        augmentee = commercial._augment(data)
        self.assertTrue(augmentee['com_masquer_economies'])
        self.assertEqual(augmentee['com_economies'], 0)
        self.assertIsNone(augmentee['com_payback'])

    def test_la_page_CFO_remplace_les_chiffres_par_le_motif(self):
        """Page 2 industrielle : ni cashflow, ni TRI, ni payback BT — le motif
        de l'omission et le geste qui la lève. La page RACCOURCIT (elle ne peut
        donc pas déborder)."""
        from apps.ventes.quote_engine.industriel import (
            finance, render as industriel_render, renderer as industriel)

        data = self._data({'tension_raccordement': 'MT'}, 'DEV-MT-0007')
        ctx = industriel_render.build_ctx(industriel._augment(data))
        html = finance.build(ctx)
        self.assertIn('MOYENNE TENSION', html)
        self.assertNotIn('Cashflow cumulé', html)
        self.assertNotIn('TRI sur', html)
        self.assertNotIn('Payback</b>', html)

    def test_la_couverture_CFO_omet_la_vignette_economies(self):
        from apps.ventes.quote_engine.industriel import (
            cover, render as industriel_render, renderer as industriel)

        data = self._data({'tension_raccordement': 'MT'}, 'DEV-MT-0008')
        ctx = industriel_render.build_ctx(industriel._augment(data))
        html = cover.build(ctx)
        # Pas de vignette « Économies / an » — et surtout pas un « 0 » (la
        # règle fondateur : un chiffre manquant s'OMET, il ne s'écrit pas 0).
        self.assertNotIn('Économies / an', html)
        self.assertIn('MOYENNE TENSION', html)

    def test_la_couverture_CFO_garde_sa_vignette_hors_MT(self):
        from apps.ventes.quote_engine.industriel import (
            cover, render as industriel_render, renderer as industriel)

        data = self._data({'tension_raccordement': 'BT'}, 'DEV-MT-0009')
        ctx = industriel_render.build_ctx(industriel._augment(data))
        html = cover.build(ctx)
        self.assertIn('Économies / an', html)


class TestCanonicalProductible(TestCase):
    """QX38 — un seul modèle de productible (PVGIS par ville), partagé par
    l'écran, le PDF et la proposition web. CompanyProfile.productible (1600)
    devient un override, pas un modèle concurrent ; le barème ONEE est aligné.
    """

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_productible_lookup_per_city(self):
        from apps.ventes.quote_engine.productible import (
            productible_for_city, PRODUCTIBLE_PAR_VILLE, DEFAULT_PRODUCTIBLE)
        self.assertEqual(productible_for_city('Agadir'), 1687)
        self.assertEqual(productible_for_city('agadir'), 1687)
        self.assertEqual(productible_for_city('Casablanca'),
                         PRODUCTIBLE_PAR_VILLE['casablanca'])
        # ville inconnue → repli central (jamais un chiffre inventé)
        self.assertEqual(productible_for_city('Oujda'), DEFAULT_PRODUCTIBLE)
        # alias secondaire → ville de référence
        self.assertEqual(productible_for_city('Kenitra'),
                         PRODUCTIBLE_PAR_VILLE['rabat'])

    def test_company_override_beats_pvgis_only_when_non_default(self):
        from apps.ventes.quote_engine.productible import productible_for_city
        # override = défaut historique 1600 → on lit le PVGIS de la ville
        self.assertEqual(productible_for_city('Agadir', override=1600), 1687)
        # override société explicite (≠ 1600) → il prime
        self.assertEqual(productible_for_city('Agadir', override=1750), 1750)

    def test_builder_uses_city_productible_for_production(self):
        from apps.crm.models import Lead
        from apps.ventes.quote_engine.builder import build_quote_data
        lead = Lead.objects.create(
            company=self.company, nom='Agadiri', ville='Agadir')
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '10', '1272.73'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-QX38-1')
        devis.lead = lead
        devis.save(update_fields=['lead'])
        data = build_quote_data(devis)
        # QRES54 — 7,1 kWc × 1687 (Agadir PVGIS) × 0,86 (pertes système 14 %)
        from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
        self.assertEqual(data['puissance_kwc'], 7.1)
        self.assertEqual(data['prod_kwh'],
                         round(7.1 * 1687 * PRODUCTION_DERATE))

    def test_onee_tranche_ceilings_aligned(self):
        """Les plafonds ONEE sont ceux de la grille officielle publiée
        (100 / 150 / 200 / 300 / 500 / ∞), et la table porte la règle SÉLECTIVE
        (progressif ≤ 150, puis toute la conso au tarif de sa tranche, avec la
        tolérance officielle de 10 kWh → bornes effectives 210/310/510)."""
        from apps.ventes.quote_engine.pricing import ONEE_TRANCHES
        ceilings = [c for c, _ in ONEE_TRANCHES]
        self.assertEqual(ceilings, [100, 150, 200, 300, 500, None])
        self.assertEqual(ONEE_TRANCHES.selective_threshold, 150)
        self.assertEqual(ONEE_TRANCHES.boundary_tolerance, 10)


class TestHonestCashflowPayback(TestCase):
    """QX39 — payback par cashflow 25 ans (dégradation/escalade/batterie/
    onduleur), croisement du cumul à zéro, hypothèses rendues sur le PDF."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_cashflow_payback_zero_crossing(self):
        from apps.ventes.quote_engine.pricing import compute_cashflow_payback
        cf = compute_cashflow_payback(50000, 10000)
        # 25 années de cumul, payback interpolé au croisement de zéro
        self.assertEqual(len(cf['cumulative']), 25)
        self.assertGreater(cf['payback_years'], 0)
        self.assertLess(cf['payback_years'], 25)
        # le cumul est croissant puis positif (rentabilisé)
        self.assertLess(cf['cumulative'][0], 0)
        self.assertGreater(cf['cumulative'][-1], 0)
        self.assertGreater(cf['net_gain'], 0)

    def test_degenerate_inputs_return_zero(self):
        from apps.ventes.quote_engine.pricing import compute_cashflow_payback
        self.assertEqual(compute_cashflow_payback(0, 10000)['payback_years'], 0.0)
        self.assertEqual(compute_cashflow_payback(50000, 0)['payback_years'], 0.0)

    def test_battery_roundtrip_lengthens_payback(self):
        from apps.ventes.quote_engine.pricing import compute_cashflow_payback
        cf_no = compute_cashflow_payback(50000, 10000)
        cf_bat = compute_cashflow_payback(50000, 10000, battery=True)
        # le rendement aller-retour < 1 réduit l'économie → payback plus long
        self.assertGreaterEqual(cf_bat['payback_years'], cf_no['payback_years'])

    def test_assumptions_block_documented(self):
        from apps.ventes.quote_engine.pricing import cashflow_assumptions
        a = cashflow_assumptions()
        self.assertEqual(a['years'], 25)
        self.assertEqual(a['degradation_pct'], 0.5)
        # QRES54 (fondateur) — AUCUNE hausse tarifaire supposée : la projection
        # est à tarif constant, seule la dégradation érode les économies.
        self.assertEqual(a['escalation_pct'], 0.0)
        self.assertTrue(any('82-21' in n for n in a['notes']))
        self.assertTrue(any('injection' in n.lower() for n in a['notes']))

    # ── Z4 (ORDRE FONDATEUR, 20/08/2026) — la courbe ne change JAMAIS de pente
    #    sans raison de modèle, et le seul palier autorisé est ANNONCÉ ──────────
    def _points_traces(self, investissement, cumul):
        """Les points EXACTEMENT tels que residential/charts.payback_curve les
        trace : l'année 0 vaut −investissement, puis le cumul année par année."""
        return [-float(investissement)] + [float(v) for v in cumul[:25]]

    def test_curve_has_exactly_one_declared_slope_step(self):
        """Z4 — le tracé s'aplatit UNE fois (l'année du remplacement onduleur,
        provisionné par le modèle) puis repart à sa pente normale. C'est le seul
        « redémarrage » légitime : partout ailleurs la pente DÉCROÎT doucement
        (dégradation panneau 0,5 %/an, tarif constant). Un second décrochement,
        ou un dernier segment plus pentu, signalerait un point dupliqué, un
        décalage d'indice ou un changement de pas — jamais le modèle."""
        from apps.ventes.quote_engine.pricing import (
            INVERTER_REPLACE_YEAR, compute_cashflow_payback,
        )
        cf = compute_cashflow_payback(50000, 10000)
        pts = self._points_traces(50000, cf['cumulative'])
        self.assertEqual(len(pts), 26, "26 points pour les années 0 à 25")
        pentes = [pts[i + 1] - pts[i] for i in range(len(pts) - 1)]
        hausses = [i for i in range(1, len(pentes))
                   if pentes[i] > pentes[i - 1]]
        # Un SEUL redémarrage, et c'est l'année qui SUIT le remplacement.
        self.assertEqual(hausses, [INVERTER_REPLACE_YEAR],
                         f"pentes={[round(p) for p in pentes]}")
        # Le creux vaut bien la PROVISION annoncée (≈ 8 % de l'investissement),
        # pas un artefact : c'est ce qui rend le palier explicable au client.
        from apps.ventes.quote_engine.pricing import INVERTER_REPLACE_FRACTION
        creux = pentes[INVERTER_REPLACE_YEAR - 2] - pentes[INVERTER_REPLACE_YEAR - 1]
        self.assertGreater(creux, 50000 * INVERTER_REPLACE_FRACTION * 0.9)
        # Partout ailleurs la pente décroît strictement (jamais un plateau
        # inexpliqué, jamais une remontée).
        for i in range(1, len(pentes)):
            if i == INVERTER_REPLACE_YEAR:
                continue
            self.assertLess(pentes[i], pentes[i - 1], f"segment {i}")
        # LE SYMPTÔME SIGNALÉ : le dernier segment n'est jamais plus pentu.
        self.assertLessEqual(pentes[-1], pentes[-2])

    def test_replacement_step_is_declared_in_the_rendered_assumptions(self):
        """Z4 — le palier de la courbe est le SEUL décrochement du tracé ; il
        était SILENCIEUX (aucune note ne le mentionnait), donc illisible comme
        autre chose qu'une erreur. Sa raison voyage désormais avec le chiffre."""
        from apps.ventes.quote_engine.pricing import (
            INVERTER_REPLACE_YEAR, cashflow_assumptions,
        )
        notes = ' '.join(cashflow_assumptions()['notes']).lower()
        self.assertIn('onduleur', notes)
        self.assertIn(str(INVERTER_REPLACE_YEAR), notes)

    # ── Z5 (ORDRE FONDATEUR, 20/08/2026) — le rendement aller-retour ne frappe
    #    QUE l'énergie qui transite par la batterie ─────────────────────────────
    def test_battery_roundtrip_only_hits_the_stored_share(self):
        """Z5 — le moteur multipliait TOUTE l'économie de l'option 2 par 0,90,
        y compris la part autoconsommée DIRECTEMENT au fil du soleil, qui
        n'entre jamais dans la batterie. Double peine → payback allongé."""
        from apps.ventes.quote_engine.pricing import (
            BATTERY_ROUNDTRIP, compute_cashflow_payback,
        )
        sans = compute_cashflow_payback(50000, 10000)
        part_zero = compute_cashflow_payback(50000, 10000, battery=True,
                                             battery_share=0.0)
        part_tout = compute_cashflow_payback(50000, 10000, battery=True,
                                             battery_share=1.0)
        forfait = compute_cashflow_payback(50000, 10000, battery=True)
        # Rien ne transite par la batterie → aucune perte, cashflow identique.
        self.assertEqual(part_zero['cashflow'], sans['cashflow'])
        # Tout transite → strictement l'ancien forfait (aucune régression).
        self.assertEqual(part_tout['cashflow'], forfait['cashflow'])
        self.assertEqual(part_tout['payback_years'], forfait['payback_years'])
        # Une part réaliste tombe ENTRE les deux, jamais au-delà.
        part_40 = compute_cashflow_payback(50000, 10000, battery=True,
                                           battery_share=0.4)
        self.assertGreater(part_40['payback_years'], sans['payback_years'])
        self.assertLess(part_40['payback_years'], forfait['payback_years'])
        attendu = 1 - (1 - BATTERY_ROUNDTRIP) * 0.4
        self.assertEqual(part_40['cashflow'][0], round(10000 * attendu))

    def test_roi_uses_the_derived_battery_share_not_a_flat_penalty(self):
        """Z5 — bout en bout : ``calculate_savings_roi`` dérive la part batterie
        des taux d'autoconsommation qu'il vient de calculer, donc le payback de
        l'option 2 est plus COURT qu'avec l'ancien forfait 0,90 appliqué à tout,
        sans jamais devenir plus court que le cas « aucune perte »."""
        from apps.ventes.quote_engine.pricing import (
            calculate_savings_roi, compute_cashflow_payback,
        )
        roi = calculate_savings_roi(
            5.68, 33902, 55902, utility='onee', conso_annuelle_kwh=9000,
            battery_kwh=10, productible=1651)
        forfait = compute_cashflow_payback(55902, roi['eco_a_ann'],
                                           battery=True)
        aucune_perte = compute_cashflow_payback(55902, roi['eco_a_ann'])
        self.assertLess(roi['roi_a'], forfait['payback_years'])
        self.assertGreaterEqual(roi['roi_a'], aucune_perte['payback_years'])
        # La part batterie est bien DÉRIVÉE (socle direct exclu), pas forfaitaire.
        self.assertGreater(roi['autoconso_avec'], roi['autoconso_sans'])

    def test_builder_roi_from_cashflow_and_assumptions_rendered(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73'),
            ('Onduleur réseau Huawei 10kW', '1', '16666.67'),
        ], reference='DEV-QX39-1')
        data = build_quote_data(devis)
        # le cumul du cashflow est porté dans les données de rendu
        self.assertIsNotNone(data.get('cashflow_sans'))
        self.assertEqual(len(data['cashflow_sans']), 25)
        # les hypothèses documentées apparaissent dans le bloc « Nos hypothèses »
        items = ' '.join(data['hypotheses']['items'])
        self.assertIn('82-21', items)
        self.assertIn('gradation', items.replace('é', 'e'))


class TestQuoteNumbersHonestyPack(TestCase):
    """QX7 — pack d'honnêteté des chiffres du PDF : couverture réelle (a),
    échéancier custom sans case morte (b), ville résolue depuis le lead (c),
    marques dérivées des vraies lignes (e). Sous-item (d) hors périmètre
    (public_views, autre lane)."""

    FULL_LINES = [
        ('Onduleur réseau 10kW', '1', '11700'),
        ('Onduleur hybride 5kW', '1', '24000'),
        ('Panneau mono 550W', '14', '1100'),
        ('Batterie 5 kWh', '1', '14000'),
        ('Structures acier', '14', '375'),
        ('Installation', '1', '4000'),
    ]

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _render_legacy(self, pdf_options=None, devis=None):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G
        data = build_quote_data(devis or self._devis(), pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_qx7_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html']

    def _devis(self, ref='DEV-QX7-0'):
        # PV86 — document à deux options : le devis le DÉCLARE (générateur).
        return make_devis(self.company, self.user, self.client_obj,
                          self.FULL_LINES, reference=ref,
                          etude_params=dict(DEUX_OPTIONS))

    # ── (a) couverture ──────────────────────────────────────────────────────
    def test_coverage_uses_real_consumption_when_known(self):
        """Avec une conso réelle (étude), la couverture = prod/conso, pas un
        diviseur /1.3 fabriqué, et n'est plus étiquetée « estimation »."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.residential import renderer
        devis = self._devis(ref='DEV-QX7-COV')
        devis.etude_params = {**DEUX_OPTIONS, 'conso_annuelle': 12000,
                              'distributeur': 'onee'}
        devis.save(update_fields=['etude_params'])
        data = build_quote_data(devis)
        self.assertEqual(data['conso_annuelle_kwh'], 12000)
        d = renderer._augment(data)
        self.assertFalse(d['coverage_estimated'])
        # couverture = prod/conso arrondie, jamais planchée à 40
        self.assertEqual(d['coverage_pct'],
                         min(100, max(1, round(data['prod_kwh'] / 12000 * 100))))

    def test_coverage_flagged_estimation_without_real_conso(self):
        """Sans conso réelle MAIS avec un barème distributeur réel, la
        couverture est DÉRIVÉE de la facture au tarif réel — une dérivation
        traçable : elle reste rendue, étiquetée « estimation » (drapeau vrai).
        Z2 ne touche PAS ce cas (voir le test d'omission ci-dessous)."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.residential import renderer
        devis = self._devis(ref='DEV-QX7-EST')
        devis.etude_params = {**DEUX_OPTIONS, 'distributeur': 'onee'}
        devis.save(update_fields=['etude_params'])
        data = build_quote_data(devis)
        self.assertIsNone(data['conso_annuelle_kwh'])
        self.assertFalse(data['savings_estimated'])
        d = renderer._augment(data)
        self.assertFalse(d['masquer_synthese'])
        self.assertTrue(d['coverage_estimated'])

    def test_no_real_data_at_all_omits_the_savings_synthesis(self):
        """Z2 (ORDRE FONDATEUR, 20/08/2026) — un devis SANS aucune donnée
        réelle d'ancrage (ni 12 factures réelles, ni conso annuelle, ni
        distributeur/tarif) ne rend PLUS de synthèse économies : le −N %,
        l'avant/après, la couverture et le graphe mensuel descendaient tous du
        tarif de REPLI × un taux forfaitaire. Ils disparaissent ENSEMBLE ;
        aucun « 0 » ne les remplace."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.residential import renderer
        data = build_quote_data(self._devis(ref='DEV-Z2-NODATA'))
        self.assertIsNone(data['conso_annuelle_kwh'])
        self.assertFalse(data['factures_reelles'])
        self.assertTrue(data['savings_estimated'])
        self.assertTrue(renderer.ancrage_reel_absent(data))
        self.assertIsNone(renderer.synthese_economies(data))
        # Le document reste rendu (aucune Unsupported), simplement sans sa
        # couche économique — jamais un bloc à moitié.
        d = renderer._augment(data)
        self.assertTrue(d['masquer_synthese'])
        for k in ('pct_cut', 'annual_before', 'annual_after',
                  'coverage_pct', 'coverage_estimated',
                  'bills_before', 'bills_after'):
            self.assertNotIn(k, d, f"{k} ne doit pas être publié")
        from apps.ventes.quote_engine.residential import render as r_render
        html = r_render.build_html(d)
        for marqueur in ('<div class="c1-bigcut">', '<img class="c1-donut"',
                         'Votre facture mois par mois', 'Économie estimée',
                         'Rentabilisé en', 'Rentabilité sur 25 ans',
                         'Gain net sur 25 ans'):
            self.assertNotIn(marqueur, html, f"{marqueur} aurait dû être omis")
        # Ce qui reste est intégralement traçable : prix, puissance, production.
        self.assertIn('c1-opt-price', html)
        self.assertIn('Production estimée', html)

    # ── (b) échéancier custom sans case morte ───────────────────────────────
    def test_custom_acompte_full_collapses_to_two_boxes(self):
        """Un acompte custom qui absorbe la tranche matériel → échéancier à
        DEUX cases (Acompte + Solde), jamais une case « Matériel » à 0 %."""
        devis = self._devis(ref='DEV-QX7-ACPT')
        # acompte custom énorme → materiel clampé à 0
        html = self._render_legacy(
            {'devis_final': True, 'payment_mode': 'custom',
             'custom_acompte': 999999}, devis=devis)
        self.assertIn('Modalit', html)                    # bloc présent
        # aucune case « Matériel » morte
        self.assertNotIn('Avant installation', html)
        self.assertIn('la livraison', html)               # solde à la livraison
        # pas de « 0% » orphelin dans une case de paiement
        self.assertNotIn('>0%</div>', html)

    def test_standard_payment_keeps_three_boxes(self):
        """Chemin standard (materiel > 0) : trois cases, rendu inchangé."""
        html = self._render_legacy(
            {'devis_final': True}, devis=self._devis(ref='DEV-QX7-STD'))
        self.assertIn('Avant installation', html)         # case Matériel présente
        self.assertIn('Acompte', html)
        self.assertIn('Solde', html)

    # ── (c) ville résolue depuis le lead ────────────────────────────────────
    def test_client_city_resolved_from_lead_ville(self):
        from apps.crm.models import Lead
        from apps.ventes.quote_engine.builder import build_quote_data
        lead = Lead.objects.create(
            company=self.company, nom='Bennani', ville='Agadir')
        devis = self._devis(ref='DEV-QX7-CITY')
        devis.lead = lead
        devis.save(update_fields=['lead'])
        data = build_quote_data(devis)
        self.assertEqual(data['client_city'], 'Agadir')

    def test_client_city_empty_without_lead(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(self._devis(ref='DEV-QX7-NOCITY'))
        self.assertEqual(data['client_city'], '')

    # ── (e) marques dérivées des vraies lignes ──────────────────────────────
    #
    # 2026-08-14 — POURQUOI CES DEUX GARDES ONT CHANGÉ D'ANCRAGE.
    # Elles épinglaient le libellé « Équipements premium certifiés [IEC] » de la
    # rangée de puces de la page 3. Cette rangée PAR DÉFAUT a été retirée du
    # moteur par QRES57 (commit b2e188a2, directive fondateur du 18/07/2026 :
    # elle répétait mot pour mot le ruban de crédibilité de la page 1) ; elle ne
    # subsiste que pour une société ayant personnalisé ``doc_texts.trust_values``.
    # Les assertions ne pouvaient donc plus passer — le PDF, lui, est correct.
    # L'EXIGENCE QX7(e) n'a pas bougé d'un pouce : une marque imprimée doit
    # VENIR D'UNE VRAIE LIGNE du devis, jamais d'une liste gravée dans le
    # moteur. Elle est ré-épinglée sur le SEUL endroit du PDF qui imprime encore
    # une marque : la pastille ``<span class="p2-mk">`` du tableau d'équipement
    # (``residential/options.py::_row``), alimentée par ``item['marque']``,
    # lui-même lu sur ``Produit.marque`` (``builder._line_to_item``).
    _MARQUE_CHIP_RE = re.compile(r'<span class="p2-mk">([^<]*)</span>')

    def _marques_imprimees(self, html):
        """Ensemble des marques réellement IMPRIMÉES sur le PDF."""
        return {m.strip() for m in self._MARQUE_CHIP_RE.findall(html)
                if m.strip()}

    def _marques_du_devis(self, data):
        """Ensemble des marques portées par les VRAIES lignes du devis."""
        lignes = (data.get('sans_items') or []) + (data.get('avec_items') or [])
        return {(it.get('marque') or '').strip() for it in lignes
                if (it.get('marque') or '').strip()}

    @tag('pdf')
    def test_brand_chips_derive_from_real_line_marques(self):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.quote_engine.builder import build_quote_data
        # produits porteurs de marques réelles distinctives
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73'),
            ('Onduleur réseau Huawei 10kW', '1', '16666.67'),
            ('Onduleur hybride Deye 10kW', '1', '23333.33'),
            ('Batterie Dyness 10 kWh', '1', '25000'),
            ('Installation', '1', '4000'),
        ], reference='DEV-QX7-BRAND', etude_params=DEUX_OPTIONS)
        for li in devis.lignes.all():
            if 'Canadien' in li.designation:
                li.produit.marque = 'Canadian Solar'
            elif 'Huawei' in li.designation:
                li.produit.marque = 'Huawei'
            elif 'Deye' in li.designation:
                li.produit.marque = 'Deye'
            elif 'Dyness' in li.designation:
                li.produit.marque = 'Dyness'
            li.produit.save(update_fields=['marque'])
        data = build_quote_data(devis)
        html = render.build_html(renderer._augment(data))
        imprimees = self._marques_imprimees(html)
        # Le panneau porte la marque PRODUIT « Canadian Solar » alors que sa
        # DÉSIGNATION dit « Canadien Solar » : la pastille imprimée ne peut donc
        # venir que de la vraie donnée produit, jamais d'un mot lu dans le
        # libellé de la ligne. C'est le cœur de la garde (a).
        self.assertIn('Canadian Solar', imprimees)
        self.assertNotIn('Canadien Solar', imprimees)
        # (b) et AUCUNE marque inventée : tout ce qui est imprimé est porté par
        # une ligne réelle du devis.
        self.assertTrue(
            imprimees <= self._marques_du_devis(data),
            f'marques imprimées hors des lignes du devis : '
            f'{imprimees - self._marques_du_devis(data)}')

    @tag('pdf')
    def test_brand_chip_falls_back_to_iec_without_marques(self):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.quote_engine.builder import build_quote_data
        # lignes sans AUCUNE marque → le moteur n'en invente pas une
        devis = self._devis(ref='DEV-QX7-NOBRAND')
        for li in devis.lignes.all():
            li.produit.marque = ''
            li.produit.save(update_fields=['marque'])
        data = build_quote_data(devis)
        # précondition du scénario : plus une seule marque dans les données
        self.assertEqual(self._marques_du_devis(data), set())
        html = render.build_html(renderer._augment(data))
        # … donc plus une seule pastille de marque sur le PDF client.
        self.assertEqual(self._marques_imprimees(html), set())


# ─── SCA27 (complément) — site_url/produits_base du tenant câblés au moteur ────


class TestNormalizeSiteHost(SimpleTestCase):
    """SCA27 — forme d'affichage d'un site tenant (fonction pure, aucune DB)."""

    def test_strips_scheme_www_path_and_trailing_slash(self):
        from apps.ventes.quote_engine.builder import _normalize_site_host
        self.assertEqual(_normalize_site_host('https://www.helios.ma/'),
                         'helios.ma')
        self.assertEqual(_normalize_site_host('http://helios.ma'), 'helios.ma')
        self.assertEqual(_normalize_site_host('helios.ma/produits'), 'helios.ma')
        self.assertEqual(_normalize_site_host('  helios.ma  '), 'helios.ma')

    def test_empty_or_none_yields_empty(self):
        from apps.ventes.quote_engine.builder import _normalize_site_host
        self.assertEqual(_normalize_site_host(''), '')
        self.assertEqual(_normalize_site_host(None), '')
        self.assertEqual(_normalize_site_host('   '), '')


class TestBuilderWiresTenantSite(TestCase):
    """SCA27 (complément) — ``build_quote_data`` passe le site du tenant au
    renderer (ligne site + base des fiches), fermant la fuite ``taqinor.ma``.

    Trois cas : tenant AVEC site → SES clés ; tenant SANS site → aucune clé
    (défauts renderer = littéraux fondateur, byte-identique DC1) ; profil
    fondateur (site = taqinor.ma) → base taqinor conservée (fiches gardées)."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _residential_devis(self, reference):
        # Forme résidentielle « deux options » (panneaux + les deux onduleurs +
        # batterie) → le renderer résidentiel s'applique.
        return make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '14', '1100'),
            ('Onduleur réseau 10kW', '1', '11700'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Batterie 5 kWh', '1', '14000'),
        ], reference=reference, etude_params=DEUX_OPTIONS)

    def _set_site(self, site):
        from apps.parametres.models import CompanyProfile
        p = CompanyProfile.get(company=self.company)
        p.site_web = site
        p.save()

    def test_tenant_with_site_gets_own_site_url_and_produits_base(self):
        from apps.ventes.quote_engine import build_quote_data
        self._set_site('https://www.helios.ma/')
        devis = self._residential_devis('DEV-SCA27-WITH')
        data = build_quote_data(devis)
        # Ligne site du pied de page = SON site (forme d'affichage normalisée).
        self.assertEqual(data['site_url'], 'helios.ma')
        # Base des liens fiches = SON site → theme.fiche_href omet taqinor.ma.
        self.assertEqual(data['links']['produits'], 'helios.ma/produits')
        self.assertEqual(data['links']['realisations'], 'helios.ma/realisations')
        # QX6 (fusion) — le lien de signature est tokenisé VERS LA VRAIE
        # proposition (ShareLink), sur la base DU TENANT : plus jamais l'ancien
        # « /signer/<ref> » 404, et aucun domaine fondateur ne fuit.
        self.assertIn('/proposition/', data['links']['signer'])
        self.assertTrue(data['links']['signer'].startswith('https://helios.ma/'))
        self.assertNotIn('/signer/', data['links']['signer'])
        # Aucune valeur ne fuit vers le site du fondateur.
        for v in [data['site_url']] + list(data['links'].values()):
            self.assertNotIn('taqinor', v.lower())

    def test_siteless_tenant_omits_keys_founder_defaults_preserved(self):
        """Tenant SANS site → aucune BASE tenant n'est posée : ``site_url`` est
        vide et ``links`` ne porte AUCUNE fiche tenant (produits/réalisations/
        garanties), donc le renderer garde ses littéraux historiques (taqinor.ma)
        — repli fondateur DC1.

        QX6 (fusion) : ``data`` porte quand même ``links`` avec l'UNIQUE lien de
        signature tokenisé (sur la base fondateur ``SITE_URL`` puisqu'il n'y a pas
        de site tenant) — c'est un vrai lien de proposition, jamais un 404, et il
        ne fait fuiter aucun AUTRE tenant."""
        from apps.ventes.quote_engine import build_quote_data
        self._set_site('')  # profil rempli MAIS sans site
        devis = self._residential_devis('DEV-SCA27-NOSITE')
        data = build_quote_data(devis)
        # Aucune base tenant : site_url vide → renderer applique taqinor.ma.
        self.assertEqual(data.get('site_url', ''), '')
        # links ne contient AUCUNE fiche tenant (seul le signer QX6 peut y être).
        _links = data.get('links') or {}
        for k in ('produits', 'realisations', 'garanties'):
            self.assertNotIn(k, _links)

    def test_founder_site_keeps_taqinor_base(self):
        """Profil fondateur (site = taqinor.ma) → base taqinor conservée : les
        fiches produits taqinor.ma restent liées (byte-identique fondateur)."""
        from apps.ventes.quote_engine import build_quote_data
        self._set_site('taqinor.ma')
        devis = self._residential_devis('DEV-SCA27-FOUNDER')
        data = build_quote_data(devis)
        self.assertEqual(data['site_url'], 'taqinor.ma')
        self.assertEqual(data['links']['produits'], 'taqinor.ma/produits')


# ─── QJ13 — Loi 82-21 self-consumption-first savings + utility tranche tables ──


class TestSavingsMath(TestCase):
    """QJ13 — Pure-Python tests for the self-consumption-first savings model.

    These tests are DB-free (no Devis needed): they exercise pricing.py directly.
    """

    def test_self_consumption_first_no_surplus_valued(self):
        """Only self-consumed kWh are valued — surplus injection yields nothing."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(
            5.0, 50000, 80000,
            tarif_kwh_override=1.75,
            autoconso_sans=0.60,
            autoconso_avec=0.85,
        )
        prod = roi["prod_kwh"]   # 5 kWc × 1240 × 0,86 (QRES54, pertes 14 %)
        # Option 1 savings = production × autoconso_sans × tarif
        self.assertEqual(roi["eco_s_ann"], round(prod * 0.60 * 1.75))
        # Option 2 savings = production × autoconso_avec × tarif
        self.assertEqual(roi["eco_a_ann"], round(prod * 0.85 * 1.75))
        # Savings < production × tarif (surplus not valued)
        self.assertLess(roi["eco_s_ann"], round(prod * 1.75))
        self.assertLess(roi["eco_a_ann"], round(prod * 1.75))

    def test_onee_tranche_weighted_price_increases_with_consumption(self):
        """Higher consumption → higher average ONEE tariff (progressive tranches)."""
        from apps.ventes.quote_engine.pricing import _weighted_kwh_price, ONEE_TRANCHES
        price_low = _weighted_kwh_price(80, ONEE_TRANCHES)    # within first tranche
        price_mid = _weighted_kwh_price(250, ONEE_TRANCHES)   # crosses first two
        price_high = _weighted_kwh_price(600, ONEE_TRANCHES)  # crosses all
        self.assertLessEqual(price_low, price_mid)
        self.assertLessEqual(price_mid, price_high)
        # First-tranche cap (2026 TTC, TVA 20% — see pricing.py ONEE_TRANCHES)
        self.assertAlmostEqual(price_low, 0.916272, places=3)

    def test_utility_name_resolves_to_table(self):
        """Passing utility='onee' uses the ONEE tranche table, not the fallback."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi, _FALLBACK_KWH_PRICE
        roi_onee = calculate_savings_roi(
            5.0, 50000, 80000,
            utility="onee",
            conso_annuelle_kwh=3600,   # 300 kWh/mois
        )
        # Result is NOT the fallback flat price
        self.assertFalse(roi_onee["savings_estimated"])
        self.assertNotAlmostEqual(roi_onee["tarif_kwh"], _FALLBACK_KWH_PRICE, places=2)

    def test_utility_case_insensitive(self):
        """utility='ONEE' and utility='onee' produce identical results."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        r1 = calculate_savings_roi(5.0, 50000, 80000, utility="ONEE",
                                   conso_annuelle_kwh=3600)
        r2 = calculate_savings_roi(5.0, 50000, 80000, utility="onee",
                                   conso_annuelle_kwh=3600)
        self.assertEqual(r1["eco_s_ann"], r2["eco_s_ann"])

    def test_lydec_and_redal_tables_present(self):
        """Lydec and Redal tables are registered and return non-estimated results."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        for util in ("lydec", "redal"):
            roi = calculate_savings_roi(5.0, 50000, 80000, utility=util,
                                        conso_annuelle_kwh=3000)
            self.assertFalse(roi["savings_estimated"],
                             f"{util} should not trigger the fallback")

    def test_tranches_override_beats_utility_name(self):
        """Caller-supplied tranches_override takes precedence over utility name."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        custom = [[100, 2.00], [None, 3.00]]
        roi_custom = calculate_savings_roi(
            5.0, 50000, 80000,
            utility="onee",
            tranches_override=custom,
            conso_annuelle_kwh=1200,
        )
        roi_onee = calculate_savings_roi(
            5.0, 50000, 80000,
            utility="onee",
            conso_annuelle_kwh=1200,
        )
        # Custom has higher prices → custom savings > ONEE savings
        self.assertGreater(roi_custom["eco_s_ann"], roi_onee["eco_s_ann"])
        self.assertFalse(roi_custom["savings_estimated"])

    def test_explicit_tarif_kwh_override_beats_all(self):
        """tarif_kwh_override wins over utility name and tranches."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(
            5.0, 50000, 80000,
            tarif_kwh_override=2.50,
            utility="onee",
            conso_annuelle_kwh=3600,
        )
        self.assertAlmostEqual(roi["tarif_kwh"], 2.50, places=4)
        self.assertFalse(roi["savings_estimated"])
        prod = roi["prod_kwh"]
        self.assertEqual(roi["eco_s_ann"], round(prod * 0.60 * 2.50))

    def test_roi_computed_from_totals(self):
        """QX39 — le payback n'est plus un ratio année-1 (total / éco annuelle)
        mais le croisement à zéro du cumul de cashflow 25 ans (dégradation
        panneau, escalade tarifaire, batterie/onduleur). On vérifie donc que
        ``roi_s``/``roi_a`` DÉLÈGUENT bien à ``compute_cashflow_payback`` avec
        le total de l'option et son économie annuelle — le vrai contrat."""
        from apps.ventes.quote_engine.pricing import (
            calculate_savings_roi, compute_cashflow_payback)
        roi = calculate_savings_roi(
            5.0, 50000, 80000,
            tarif_kwh_override=1.75,
        )
        expected_roi_s = compute_cashflow_payback(
            50000, roi["eco_s_ann"])["payback_years"]
        expected_roi_a = compute_cashflow_payback(
            80000, roi["eco_a_ann"], battery=True)["payback_years"]
        self.assertAlmostEqual(roi["roi_s"], expected_roi_s, places=1)
        self.assertAlmostEqual(roi["roi_a"], expected_roi_a, places=1)

    def test_monthly_seasonal_factors_sum_to_production(self):
        """The 12 monthly savings values sum to approximately the annual savings."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(10.0, 100000, 150000, tarif_kwh_override=1.40)
        # Sum of monthly ≈ annual (within ±12 MAD due to rounding per month)
        self.assertAlmostEqual(sum(roi["eco_s_monthly"]), roi["eco_s_ann"], delta=12)
        self.assertAlmostEqual(sum(roi["eco_a_monthly"]), roi["eco_a_ann"], delta=12)
        self.assertEqual(len(roi["eco_s_monthly"]), 12)
        self.assertEqual(len(roi["eco_a_monthly"]), 12)

    def test_tranche_table_zero_consumption_returns_first_tranche_price(self):
        """With zero consumption, return the first-tranche price (conservative floor)."""
        from apps.ventes.quote_engine.pricing import _weighted_kwh_price, ONEE_TRANCHES
        price = _weighted_kwh_price(0, ONEE_TRANCHES)
        self.assertAlmostEqual(price, ONEE_TRANCHES[0][1], places=4)

    def test_tranche_table_large_consumption_approaches_last_tranche(self):
        """Very large consumption is dominated by the last (most expensive) band."""
        from apps.ventes.quote_engine.pricing import _weighted_kwh_price, ONEE_TRANCHES
        # 10 000 kWh/mois — the last tranche dominates the weighted average, so
        # the result must be close to (but not exceed) the last tranche price.
        price_huge = _weighted_kwh_price(10000, ONEE_TRANCHES)
        last_tranche_price = ONEE_TRANCHES[-1][1]
        self.assertGreater(price_huge, 1.35)
        self.assertLessEqual(price_huge, last_tranche_price)


class TestNoInventedNumberGuard(TestCase):
    """QJ13 — No-invented-number guard: when tariff/consumption data is absent,
    savings degrade honestly (flagged as estimate) rather than fabricating a
    precise number.
    """

    def test_no_tariff_data_flags_savings_as_estimated(self):
        """Without any tariff override or utility name, savings_estimated is True."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(5.0, 50000, 80000)
        self.assertTrue(roi["savings_estimated"],
                        "savings must be flagged as an estimate when no tariff data")

    def test_no_tariff_data_uses_fallback_price_not_zero(self):
        """Fallback still produces a non-zero savings figure (honest estimate, not
        a blank/zero that would confuse the user)."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(5.0, 50000, 80000)
        self.assertGreater(roi["eco_s_ann"], 0)
        self.assertGreater(roi["eco_a_ann"], 0)

    def test_tarif_kwh_override_zero_keeps_estimated_flag_false(self):
        """tarif_kwh_override=0 is treated as absent → fallback fires."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi_zero = calculate_savings_roi(5.0, 50000, 80000, tarif_kwh_override=0)
        self.assertTrue(roi_zero["savings_estimated"])

    def test_with_tariff_data_flag_is_false(self):
        """Providing a real tariff override disables the estimated flag."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(5.0, 50000, 80000, tarif_kwh_override=1.40)
        self.assertFalse(roi["savings_estimated"])

    def test_builder_exposes_savings_estimated_key(self):
        """build_quote_data forwards savings_estimated into the data dict."""
        company = make_company()
        user = make_user(company)
        client_obj = make_client(company)
        devis = make_devis(company, user, client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ], reference='DEV-QJ13-EST')
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis)
        # No etude_params → no tariff data → must be estimated
        self.assertIn("savings_estimated", data)
        self.assertTrue(data["savings_estimated"])
        self.assertIn("tarif_kwh", data)

    def test_builder_with_etude_params_tarif_kwh_not_estimated(self):
        """When etude_params carries tarif_kwh, savings are not estimated."""
        company = make_company()
        user = make_user(company)
        client_obj = make_client(company)
        devis = make_devis(company, user, client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ], reference='DEV-QJ13-KWH')
        devis.etude_params = {"tarif_kwh": 1.50}
        devis.save(update_fields=["etude_params"])
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis)
        self.assertFalse(data["savings_estimated"])
        self.assertAlmostEqual(data["tarif_kwh"], 1.50, places=2)

    def test_builder_with_distributeur_onee_not_estimated(self):
        """etude_params distributeur='onee' → ONEE tranche table, not estimated."""
        company = make_company()
        user = make_user(company)
        client_obj = make_client(company)
        devis = make_devis(company, user, client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-QJ13-ONEE')
        devis.etude_params = {"distributeur": "onee", "conso_annuelle": 18000}
        devis.save(update_fields=["etude_params"])
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis)
        self.assertFalse(data["savings_estimated"])

    def test_builder_uses_company_tariff_override_when_set(self):
        """ORDRE FONDATEUR (19/08/2026) — quand le fondateur a ÉDITÉ le barème
        ONEE de sa société (Paramètres → Tarification & ROI, apps/parametres
        ``TariffSettings``), le moteur de devis doit l'UTILISER (via
        ``apps.parametres.selectors.residential_tranches_for``), pas les
        défauts codés en dur dans pricing.py."""
        from apps.parametres.models_tariff import TariffSettings
        company = make_company()
        user = make_user(company)
        client_obj = make_client(company)
        # Barème custom : la tranche haute (> 500 kWh) vaut 9.000000 MAD/kWh —
        # une valeur qui ne peut PAS venir des défauts 2026 (1.622856).
        ts = TariffSettings.get(company=company)
        ts.residential_tiers = [
            {"max_kwh": 100, "prix_kwh_ttc": "0.916272"},
            {"max_kwh": 150, "prix_kwh_ttc": "1.091388"},
            {"max_kwh": 210, "prix_kwh_ttc": "1.091388"},
            {"max_kwh": 310, "prix_kwh_ttc": "1.187388"},
            {"max_kwh": 510, "prix_kwh_ttc": "1.405116"},
            {"max_kwh": None, "prix_kwh_ttc": "9.000000"},
        ]
        ts.save()
        devis = make_devis(company, user, client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-QF-TARIF2026-OVERRIDE')
        # 18 000 kWh/an = 1 500 kWh/mois : bien au-dessus de 500 → tranche haute.
        devis.etude_params = {"distributeur": "onee", "conso_annuelle": 18000}
        devis.save(update_fields=["etude_params"])
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis)
        self.assertFalse(data["savings_estimated"])
        self.assertAlmostEqual(data["tarif_kwh"], 9.0, places=2)

    def test_builder_falls_back_to_2026_defaults_without_company_override(self):
        """Société SANS barème édité → le moteur de devis garde les défauts
        2026 codés en dur dans pricing.ONEE_TRANCHES (aucune régression)."""
        from apps.ventes.quote_engine.pricing import ONEE_TRANCHES
        company = make_company()
        user = make_user(company)
        client_obj = make_client(company)
        devis = make_devis(company, user, client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-QF-TARIF2026-DEFAULT')
        devis.etude_params = {"distributeur": "onee", "conso_annuelle": 18000}
        devis.save(update_fields=["etude_params"])
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis)
        self.assertFalse(data["savings_estimated"])
        self.assertAlmostEqual(data["tarif_kwh"], ONEE_TRANCHES[-1][1], places=4)

    def test_surplus_injection_not_in_savings(self):
        """Savings must NEVER exceed production × autoconso × price.

        The self-consumption ratio caps savings; there is no surplus-injection bonus.
        """
        from apps.ventes.quote_engine.pricing import (
            calculate_savings_roi, AUTOCONSO_AVEC)
        kwc = 10.0
        roi = calculate_savings_roi(kwc, 100000, 150000, tarif_kwh_override=1.75)
        prod = roi["prod_kwh"]
        # Savings must not exceed 100% autoconsumption (no injection bonus)
        max_possible = round(prod * 1.0 * 1.75)
        self.assertLessEqual(roi["eco_s_ann"], max_possible)
        self.assertLessEqual(roi["eco_a_ann"], max_possible)
        # And they should reflect only the self-consumed share
        self.assertEqual(roi["eco_a_ann"], round(prod * AUTOCONSO_AVEC * 1.75))


# ── PV11 : la fiche technique prime sur la regex pour le wattage panneau ──────
class TestPanelWattFromFicheTechnique(TestCase):
    """PV11 — ordre de résolution : fiche technique (Pmax réel) > regex
    désignation/nom > repli catalogue.

    RÈGLE #4 : le moteur ne fait que RENDRE. Les tests ci-dessous vérifient donc
    aussi que rien d'autre ne bouge — nombre de pages et totaux identiques avec
    et sans fiche.
    """

    LINES = [
        ('Panneau Canadien Solar 710W', '10', '1400'),
        ('Onduleur réseau 8kW', '1', '14000'),
    ]

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, reference):
        return make_devis(self.company, self.user, self.client_obj,
                          self.LINES, reference=reference)

    def _panneau(self, devis):
        return devis.lignes.get(
            designation='Panneau Canadien Solar 710W').produit

    def _fiche(self, produit, **kwargs):
        from apps.stock.models import FicheTechnique
        return FicheTechnique.objects.create(
            company=self.company, produit=produit, **kwargs)

    # ── Fiche présente : sa puissance EXACTE est utilisée ──
    def test_fiche_pmax_wins_over_designation_regex(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.stock.models import FicheTechnique
        devis = self._devis('DEV-PV11-FICHE')
        # La désignation dit 710 W, la fiche constructeur dit 705 Wc : c'est la
        # FICHE qui fait foi.
        self._fiche(self._panneau(devis),
                    type_fiche=FicheTechnique.TypeFiche.MODULE,
                    pmax_wc=Decimal('705.00'))
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 705)
        self.assertEqual(data['nb_panneaux'], 10)
        self.assertEqual(data['puissance_kwc'], 7.05)

    def test_fiche_pmax_used_when_designation_has_no_wattage(self):
        """Désignation illisible + fiche → la vraie puissance, pas le repli."""
        from apps.ventes.quote_engine import build_quote_data
        from apps.ventes.quote_engine.builder import _DEFAULT_WATT
        from apps.stock.models import FicheTechnique
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau photovoltaïque monocristallin', '12', '1400'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-PV11-NOWATT')
        produit = devis.lignes.get(
            designation='Panneau photovoltaïque monocristallin').produit
        self._fiche(produit, type_fiche=FicheTechnique.TypeFiche.MODULE,
                    pmax_wc=Decimal('580.00'))
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 580)
        self.assertNotEqual(data['watt_par_panneau'], _DEFAULT_WATT)

    def test_legacy_fiche_without_type_still_counts(self):
        """Une fiche ANTÉRIEURE à PV5 (``type_fiche`` vide) porte déjà un Pmax
        de panneau : elle reste exploitée."""
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis('DEV-PV11-LEGACY')
        self._fiche(self._panneau(devis), pmax_wc=Decimal('665.00'))
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 665)

    # ── Fiche absente / inexploitable : chemin regex STRICTEMENT inchangé ──
    def test_without_fiche_regex_path_is_unchanged(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis('DEV-PV11-SANS')
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 710)  # lu dans « 710W »
        self.assertEqual(data['puissance_kwc'], 7.1)

    def test_fiche_without_pmax_falls_back_to_regex(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.stock.models import FicheTechnique
        devis = self._devis('DEV-PV11-NOPMAX')
        self._fiche(self._panneau(devis),
                    type_fiche=FicheTechnique.TypeFiche.MODULE,
                    voc_v=Decimal('48.00'))  # aucun pmax_wc
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 710)

    def test_non_module_fiche_is_ignored(self):
        """Un Pmax saisi par erreur sur une fiche onduleur/batterie ne dicte
        JAMAIS la puissance d'un panneau."""
        from apps.ventes.quote_engine import build_quote_data
        from apps.stock.models import FicheTechnique
        devis = self._devis('DEV-PV11-ONDFICHE')
        self._fiche(self._panneau(devis),
                    type_fiche=FicheTechnique.TypeFiche.ONDULEUR,
                    pmax_wc=Decimal('12000.00'))
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 710)

    def test_zero_pmax_falls_back_to_regex(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.stock.models import FicheTechnique
        devis = self._devis('DEV-PV11-ZERO')
        self._fiche(self._panneau(devis),
                    type_fiche=FicheTechnique.TypeFiche.MODULE,
                    pmax_wc=Decimal('0.00'))
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 710)

    # ── RÈGLE #4 : ni les totaux ni le nombre de pages ne bougent ──
    def test_totals_identical_with_and_without_fiche(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.stock.models import FicheTechnique
        sans = build_quote_data(self._devis('DEV-PV11-T1'))
        devis = self._devis('DEV-PV11-T2')
        self._fiche(self._panneau(devis),
                    type_fiche=FicheTechnique.TypeFiche.MODULE,
                    pmax_wc=Decimal('705.00'))
        avec = build_quote_data(devis)
        for key in ('totaux_sans', 'totaux_avec', 'totaux_all'):
            self.assertEqual(avec[key], sans[key], key)
        # Seule la puissance change — c'est bien le seul effet de PV11.
        self.assertNotEqual(avec['watt_par_panneau'],
                            sans['watt_par_panneau'])

    def test_page_counts_unchanged_with_fiche(self):
        from weasyprint import HTML
        from apps.stock.models import FicheTechnique
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.tests.test_quote_engine_formats import TestPdfFormats

        # MÊME fixture golden que les garde-fous de pagination existants.
        devis = make_devis(self.company, self.user, self.client_obj,
                           TestPdfFormats.FULL_LINES, reference='DEV-PV11-PDF')
        produit = devis.lignes.get(designation='Panneau mono 550W').produit
        FicheTechnique.objects.create(
            company=self.company, produit=produit,
            type_fiche=FicheTechnique.TypeFiche.MODULE,
            pmax_wc=Decimal('545.00'))

        def _render(pdf_options=None):
            data = build_quote_data(devis, pdf_options)
            cap = {}
            orig = G._render_pdf_weasyprint
            G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
            try:
                G.generate_premium_pdf(data, '/tmp/_pv11_test.pdf')
            finally:
                G._render_pdf_weasyprint = orig
            return data, HTML(string=cap['html']).render()

        data, doc = _render()
        self.assertEqual(len(doc.pages), 3)
        self.assertEqual(data['watt_par_panneau'], 545)
        _, doc_one = _render({'pdf_mode': 'onepage'})
        self.assertEqual(len(doc_one.pages), 1)
