"""QF2 — Two-bills real-savings model (facture sans vs avec solaire, par tranche).

Covers the pure ``two_bills_savings`` math, its integration in
``calculate_savings_roi`` (economies become facture_sans − facture_avec when
real consumption + a tariff table exist), the builder exposure
(``facture_sans_solaire`` / ``facture_avec_solaire_*`` / ``savings_model``)
and the honest degrade path (no data → old estimate, flagged).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qf2_two_bills -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine import bareme
from apps.ventes.quote_engine.pricing import (
    ONEE_TRANCHES,
    calculate_savings_roi,
    two_bills_savings,
)

User = get_user_model()


def _onee_annual_bill(kwh_month):
    """La facture annuelle TTC COMPLÈTE, telle que la tarife le moteur.

    QJR157 (30/08/2026) — ``two_bills_savings`` ne modélise plus la seule
    ÉNERGIE : les deux factures passent par ``bareme.facture_mad``, lignes
    fixes (location + entretien) et TPPAN comprises, parce que le chemin
    ``savings_model='horaire'`` servait déjà cette vignette charges comprises
    et que le même client voyait donc deux « factures actuelles » différentes
    selon qu'un bloc horaire existait ou non.

    Ce témoin suit donc la MÊME chaîne que le code testé, au lieu de figer des
    nombres : il reste une DÉRIVATION (barème → charges → TPPAN), et il bougera
    tout seul le jour où le barème bouge. Sur 300 kWh/mois : énergie 4 274,60
    + fixes 479,23 + TPPAN 540,00 = 5 293,83 → 5 294 MAD/an. Le modèle d'AVANT
    QJR157 était l'énergie seule, ``_weighted_kwh_price × kWh × 12``.
    """
    return bareme.facture_mad(
        kwh_month, tranches=ONEE_TRANCHES)['total_mad'] * 12


class TestTwoBillsSavingsPure(SimpleTestCase):
    """two_bills_savings — pure per-tranche math."""

    def test_math_correct_per_tranche_partial_coverage(self):
        """conso 3600 kWh/an, prod 6200, ratio 0.30 → residual valued per tranche."""
        out = two_bills_savings(6200, 3600, 0.30, utility="onee")
        self.assertIsNotNone(out)
        facture_sans = _onee_annual_bill(300)          # 300 kWh/mois
        autoconso = 6200 * 0.30                        # 1860 < 3600 → cap not hit
        residual_m = (3600 - autoconso) / 12           # 145 kWh/mois
        facture_avec = _onee_annual_bill(residual_m)
        self.assertEqual(out["facture_sans"], round(facture_sans))
        self.assertEqual(out["facture_avec"], round(facture_avec))
        # chain is exact on the ROUNDED bills (internally consistent display)
        self.assertEqual(out["economie"],
                         round(facture_sans) - round(facture_avec))
        self.assertEqual(out["autoconso_kwh"], round(autoconso))
        self.assertFalse(out["approximatif"])

    def test_self_consumption_capped_at_consumption(self):
        """Production above consumption: savings cap at the bill MINUS the
        subscription — the surplus injected to the grid is never valued
        (loi 82-21), and the meter rental stays due either way.

        QJR157 — le résiduel tombe bien à 0 kWh, mais la facture ne tombe PAS
        à 0 MAD : ``bareme.facture_mad`` documente que « les charges fixes
        RESTENT dues (c'est la réalité d'un abonnement) ». Un client qui
        autoconsomme 100 % de sa consommation paie encore sa location de
        compteur — 479,23 MAD/an. C'est le plafond VRAI des économies, et le
        dire ici évite de promettre au client une facture nulle.
        """
        out = two_bills_savings(6200, 3600, 0.60, utility="onee")
        # 6200 × 0.60 = 3720 > 3600 → autoconso capped at conso, residual 0.
        self.assertEqual(out["autoconso_kwh"], 3600)
        # Énergie 0 + TPPAN 0 + charges fixes 479,23 → 479 MAD/an.
        charges_fixes = round(
            bareme.charges_fixes_ttc(bareme.MILLESIME_COURANT) * 12)
        self.assertEqual(out["facture_avec"], charges_fixes)
        self.assertEqual(out["economie"],
                         out["facture_sans"] - charges_fixes)
        # NEVER above the full bill (no injection bonus).
        self.assertLessEqual(out["economie"], round(_onee_annual_bill(300)) + 1)
        # …et STRICTEMENT en dessous : l'abonnement n'est jamais économisé.
        self.assertLess(out["economie"], out["facture_sans"])

    def test_lydec_lit_la_grille_nationale_et_n_est_plus_approximatif(self):
        """Q7 (décision fondateur du 20/08/2026) — les grilles « approximatives »
        Lydec/Redal sont supprimées : trois paliers ronds jamais vérifiés, qui
        faisaient diverger la facture d'un MÊME client selon un champ de
        formulaire, puis un drapeau qui avouait le problème sans le corriger.
        Les trois distributeurs lisent la grille nationale ; le nom n'est plus
        qu'un libellé."""
        ref = two_bills_savings(6200, 3600, 0.30, utility="onee")
        for utility in ("lydec", "redal"):
            out = two_bills_savings(6200, 3600, 0.30, utility=utility)
            self.assertFalse(out["approximatif"], utility)
            self.assertAlmostEqual(out["economie"], ref["economie"],
                                   places=6, msg=utility)

    def test_returns_none_without_table_or_data(self):
        self.assertIsNone(two_bills_savings(6200, 3600, 0.30))         # no table
        self.assertIsNone(two_bills_savings(6200, 0, 0.30, utility="onee"))
        self.assertIsNone(two_bills_savings(0, 3600, 0.30, utility="onee"))
        self.assertIsNone(two_bills_savings(6200, 3600, 0, utility="onee"))
        self.assertIsNone(two_bills_savings("x", "y", 0.3, utility="onee"))


class TestCalculateSavingsRoiTwoBills(SimpleTestCase):
    """calculate_savings_roi switches to the two-bills model when real data exists."""

    def test_two_bills_model_used_with_utility_and_conso(self):
        roi = calculate_savings_roi(
            5.0, 50000, 80000, utility="onee", conso_annuelle_kwh=6000)
        self.assertEqual(roi["savings_model"], "factures")
        self.assertIsNotNone(roi["facture_sans"])
        self.assertIsNotNone(roi["facture_avec_s"])
        self.assertIsNotNone(roi["facture_avec_a"])
        # economies = facture_sans − facture_avec per option
        self.assertEqual(roi["eco_s_ann"],
                         roi["facture_sans"] - roi["facture_avec_s"])
        self.assertEqual(roi["eco_a_ann"],
                         roi["facture_sans"] - roi["facture_avec_a"])
        # option 2 self-consumes more → lower residual bill, higher savings
        self.assertGreaterEqual(roi["eco_a_ann"], roi["eco_s_ann"])
        self.assertFalse(roi["savings_estimated"])

    def test_monthly_series_follow_two_bills_totals(self):
        roi = calculate_savings_roi(
            5.0, 50000, 80000, utility="onee", conso_annuelle_kwh=6000)
        self.assertAlmostEqual(sum(roi["eco_s_monthly"]), roi["eco_s_ann"],
                               delta=12)
        self.assertAlmostEqual(sum(roi["eco_a_monthly"]), roi["eco_a_ann"],
                               delta=12)

    def test_no_consumption_degrades_to_flagged_estimate(self):
        """Without real consumption, the OLD estimate applies and is labelled."""
        roi = calculate_savings_roi(5.0, 50000, 80000, utility="onee")
        self.assertEqual(roi["savings_model"], "estimation")
        self.assertIsNone(roi["facture_sans"])
        # old formula: production × autoconso × prix
        self.assertEqual(roi["eco_s_ann"],
                         round(roi["prod_kwh"] * roi["autoconso_sans"]
                               * roi["tarif_kwh"]))

    def test_seller_flat_tarif_override_keeps_old_model(self):
        roi = calculate_savings_roi(
            5.0, 50000, 80000, tarif_kwh_override=1.75,
            utility="onee", conso_annuelle_kwh=6000)
        self.assertEqual(roi["savings_model"], "estimation")
        self.assertEqual(roi["eco_s_ann"],
                         round(roi["prod_kwh"] * roi["autoconso_sans"] * 1.75))

    def test_no_data_at_all_still_flagged_estimated(self):
        roi = calculate_savings_roi(5.0, 50000, 80000)
        self.assertEqual(roi["savings_model"], "estimation")
        self.assertTrue(roi["savings_estimated"])
        self.assertGreater(roi["eco_s_ann"], 0)   # honest estimate, never blank


class TestBuilderTwoBillsExposure(TestCase):
    """build_quote_data exposes both bills + model, and persists them into the
    rendered etude params. No-data path stays honest."""

    def setUp(self):
        from authentication.models import Company
        from apps.crm.models import Client
        self.company, _ = Company.objects.get_or_create(
            slug='test-qf2-co', defaults={'nom': 'Test QF2 Co'})
        self.user = User.objects.create_user(
            username='qf2user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Farsi', prenom='Nora',
            email='n@example.com', telephone='+212600000001')

    def _devis(self, etude_params=None, reference='DEV-QF2-0001'):
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            etude_params=etude_params,
        )
        for desig, qty, pu in [
            ('Panneau mono 550W', '10', '1400'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ]:
            produit = Produit.objects.create(
                company=self.company, nom=desig,
                sku=f'{reference[-6:]}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=10)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def test_bills_exposed_and_persisted_into_etude(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(
            etude_params={'distributeur': 'onee', 'conso_annuelle': 6000})
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'factures')
        self.assertIsNotNone(data['facture_sans_solaire'])
        self.assertIsNotNone(data['facture_avec_solaire_s'])
        self.assertIsNotNone(data['facture_avec_solaire_a'])
        # economies shown = difference of the two bills (option 1)
        self.assertEqual(
            data['eco_s_ann'],
            data['facture_sans_solaire'] - data['facture_avec_solaire_s'])
        # persisted into the RENDERED etude params (same figures everywhere)
        self.assertEqual(data['etude']['facture_annuelle_sans_solaire'],
                         data['facture_sans_solaire'])
        self.assertEqual(data['etude']['facture_annuelle_avec_solaire_opt1'],
                         data['facture_avec_solaire_s'])
        self.assertEqual(data['etude']['economie_reelle_opt1'],
                         data['eco_s_ann'])
        self.assertFalse(data['factures_approximatif'])

    def test_lydec_n_est_plus_publie_comme_approximatif(self):
        """Q7 — un devis Lydec est chiffré sur la grille NATIONALE : le modèle
        « factures » reste actif (barème réel par tranches) et plus aucun
        drapeau « approximatif » ne franchit la frontière du rendu."""
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(
            etude_params={'distributeur': 'lydec', 'conso_annuelle': 6000},
            reference='DEV-QF2-0002')
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'factures')
        self.assertFalse(data['factures_approximatif'])

    def test_no_data_path_is_honest(self):
        """No bill/consumption → old estimate, flagged, no fabricated bills."""
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(reference='DEV-QF2-0003')
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'estimation')
        self.assertIsNone(data['facture_sans_solaire'])
        self.assertIsNone(data['facture_avec_solaire_s'])
        self.assertTrue(data['savings_estimated'])
        self.assertNotIn('facture_annuelle_sans_solaire', data['etude'])

    def test_stored_etude_economies_take_precedence(self):
        """An industrial study with stored economies stays canonical (model 'etude')."""
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(
            etude_params={
                'distributeur': 'onee', 'conso_annuelle': 120000,
                'production_annuelle': 12000, 'economies_annuelles': 21000,
            },
            reference='DEV-QF2-0004')
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'etude')
        self.assertEqual(data['eco_s_ann'], 21000)


class TestFacturesReellesContract(TestCase):
    """PACT10/QF-REAL (19/08/2026) — quand etude_params porte les 12 VRAIES
    factures mensuelles du client (contrat semé par le devis auto résidentiel
    — autoQuote.js S1), elles deviennent la série « avant ».

    M1 (audit adversarial, 20/08/2026) — CE QUI A CHANGÉ : l'absence de la clé
    ne retombe PLUS sur le proxy circulaire ``économie / taux
    d'autoconsommation``. Ce repli reconstruisait la facture à partir de
    l'économie supposée, elle-même dérivée du même taux : le « −85 % » de la
    page 1 n'était que le taux forfaitaire redéguisé. Absence ⇒ ``None`` ⇒ la
    page 1 n'est pas rendue. Les tests ci-dessous épinglent donc désormais
    l'OMISSION là où ils épinglaient le proxy."""

    def setUp(self):
        from authentication.models import Company
        from apps.crm.models import Client
        self.company, _ = Company.objects.get_or_create(
            slug='test-qfreal-co', defaults={'nom': 'Test QF-REAL Co'})
        self.user = User.objects.create_user(
            username='qfrealuser', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Benali', prenom='Yassine',
            email='y@example.com', telephone='+212600000002')

    def _devis(self, etude_params=None, reference='DEV-QFREAL-0001'):
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            etude_params=etude_params,
        )
        # 10 × 550W ≈ 5,5 kWc — production annuelle < 9000 kWh de conso, donc
        # la couverture (S3) est vérifiable < 100 % (jamais un plafond
        # artificiel à 100 %).
        for desig, qty, pu in [
            ('Panneau mono 550W', '10', '1400'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ]:
            produit = Produit.objects.create(
                company=self.company, nom=desig,
                sku=f'{reference[-6:]}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=10)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    BILLS = [1200, 1200, 1300, 1400, 1600, 1800,
             1900, 1900, 1700, 1500, 1300, 1200]

    def test_real_bills_drive_before_series_and_honest_coverage(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.ventes.quote_engine.residential.renderer import (
            synthese_economies,
        )
        devis = self._devis(
            etude_params={
                'distributeur': 'onee', 'conso_annuelle': 9000,
                'factures_mensuelles_reelles': self.BILLS,
            })
        data = build_quote_data(devis)
        # La série « avant » EST la facture réelle du client, telle quelle.
        self.assertEqual(data['factures_mensuelles'], self.BILLS)
        # Conso + distributeur connus → modèle « deux factures » (barème réel).
        self.assertEqual(data['savings_model'], 'factures')
        synth = synthese_economies(data)
        self.assertIsNotNone(synth)
        self.assertEqual(synth['bills_before'], self.BILLS)
        # La couverture n'est plus dérivée en dernier repli de la facture —
        # elle vient de la VRAIE conso, jamais la circularité dénoncée (audit
        # 19/08) où la couverture valait toujours ≈ 100 %.
        self.assertFalse(synth['coverage_estimated'])
        self.assertLess(synth['coverage_pct'], 100)
        self.assertGreater(synth['coverage_pct'], 0)

    # Le contrat de S2 : une clé absente ou malformée rend EXACTEMENT ce que
    # rend le build sans la clé — on compare deux builds construits dans le
    # MÊME test (même catalogue). Depuis M1, ce « ce que rend le build sans la
    # clé » est ``None`` : plus rien à re-dériver à la main.
    def _factures_rendues(self, etude_params, reference):
        from apps.ventes.quote_engine import build_quote_data
        return build_quote_data(
            self._devis(etude_params=etude_params, reference=reference),
        )['factures_mensuelles']

    _ETUDE_SANS_CLE = {'distributeur': 'onee', 'conso_annuelle': 6000}

    def _assert_repli_identique(self, valeur_malformee, reference):
        sans = self._factures_rendues(dict(self._ETUDE_SANS_CLE),
                                      reference + 'A')
        avec = self._factures_rendues(
            {**self._ETUDE_SANS_CLE,
             'factures_mensuelles_reelles': valeur_malformee},
            reference + 'B')
        self.assertEqual(avec, sans)
        return sans

    def test_absence_de_factures_reelles_donne_none_jamais_un_proxy(self):
        """M1 — sans factures_mensuelles_reelles, la série « avant » vaut
        ``None`` : plus aucun proxy éco/autoconso, et une clé ``None`` est
        traitée comme une clé absente."""
        sans = self._assert_repli_identique(None, 'DEV-QFREAL-0002')
        self.assertIsNone(sans)

    def test_wrong_length_est_traitee_comme_une_absence(self):
        self.assertIsNone(
            self._assert_repli_identique([1200] * 11, 'DEV-QFREAL-0003'))

    def test_non_numeric_values_est_traitee_comme_une_absence(self):
        self.assertIsNone(
            self._assert_repli_identique(['x'] * 12, 'DEV-QFREAL-0004'))

    def test_non_positive_values_est_traitee_comme_une_absence(self):
        self.assertIsNone(
            self._assert_repli_identique([0] * 12, 'DEV-QFREAL-0005'))

    # ── ERR-RHOR8-SANS-LOCALISATION-ECRAN-PDF — devis sans localisation ─────
    _HIVER_ETE = {'factures_hiver_ete': {'hiver_mad': 1000, 'ete_mad': None,
                                         'ete_differente': False}}

    def test_rhor8_hiver_ete_sans_conso_tarife_par_tranche_niveau5(self):
        """Factures hiver/été saisies, ni conso ni distributeur ni bloc
        horaire : le PDF tarife par tranche (grille nationale), comme l'écran,
        et ne se dit plus « estimation »."""
        from apps.ventes.quote_engine import build_quote_data
        data = build_quote_data(self._devis(
            etude_params=dict(self._HIVER_ETE), reference='DEV-RHOR8-0005'))
        self.assertEqual(data['savings_model'], 'factures')
        self.assertFalse(data['savings_estimated'])
        self.assertGreater(data['conso_annuelle_kwh'], 0)
        self.assertIn('Tarif électricité : barème national par tranche',
                      data['hypotheses']['items'])

    def test_rhor8_niveau4_garde_son_estimation(self):
        """Nouveaux rendus seulement : un devis de niveau 4 garde son PDF."""
        from apps.ventes.models import Devis
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(etude_params=dict(self._HIVER_ETE),
                            reference='DEV-RHOR8-0004')
        Devis.objects.filter(pk=devis.pk).update(regles_calcul=4)
        devis.refresh_from_db()
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'estimation')
        self.assertTrue(data['savings_estimated'])

    # ── ERR-RHOR8-CONSO-SAISIE-SANS-DISTRIBUTEUR — kWh saisis, sans distributeur
    def test_rhor8_conso_saisie_sans_distributeur_tarife_par_tranche(self):
        """Conso saisie stockée (kWh), aucun distributeur : niveau 5 ⇒ barème
        national par tranche (l'écran tarife sur l'ONEE par défaut)."""
        from apps.ventes.quote_engine import build_quote_data
        data = build_quote_data(self._devis(
            etude_params={'conso_annuelle': 6000},
            reference='DEV-RHOR8-KWH5'))
        self.assertEqual(data['savings_model'], 'factures')
        self.assertFalse(data['savings_estimated'])
        self.assertIn('Tarif électricité : barème national par tranche',
                      data['hypotheses']['items'])

    def test_rhor8_conso_saisie_niveau4_garde_son_estimation(self):
        from apps.ventes.models import Devis
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(etude_params={'conso_annuelle': 6000},
                            reference='DEV-RHOR8-KWH4')
        Devis.objects.filter(pk=devis.pk).update(regles_calcul=4)
        devis.refresh_from_db()
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'estimation')
        self.assertTrue(data['savings_estimated'])


class Rhor8SansLocalisationParite(SimpleTestCase):
    """ERR-RHOR8 — parité écran / PDF du devis 2299 (5,68 kWc, facture
    d'hiver 1 000 MAD, batterie 5 kWh, 44 500 / 56 500 MAD TTC). Mêmes
    chiffres épinglés côté écran : ``calc/roi.test.mjs`` (ERR-RHOR8)."""

    ETUDE = {'factures_hiver_ete': {'hiver_mad': 1000, 'ete_mad': None,
                                    'ete_differente': False}}

    def _conso(self, niveau=5, mode='residentiel', **etude):
        from types import SimpleNamespace
        from apps.ventes.quote_engine.etude_chiffrage import (
            _conso_hiver_ete_niveau5)
        return _conso_hiver_ete_niveau5(
            SimpleNamespace(regles_calcul=niveau), mode,
            {**self.ETUDE, **etude}, None, None)

    def test_memes_chiffres_que_l_ecran(self):
        conso = self._conso()
        self.assertEqual(conso, 6419)   # = consoAnnuelleDepuisFactures(estimerMois(1000))
        roi = calculate_savings_roi(
            5.68, 44500, 56500, conso_annuelle_kwh=conso, battery_kwh=5,
            productible=1651, stockage_present=True, regles_2710=True,
            fallback_tarif_kwh=1.75, bareme_national_defaut=True)
        self.assertEqual(roi['savings_model'], 'factures')
        self.assertTrue(roi['bareme_national'])
        self.assertEqual((roi['eco_s_ann'], roi['eco_a_ann']), (10316, 11308))

    def test_avant_le_correctif_le_pdf_estimait(self):
        """Témoin : le chemin d'hier (9 159 / 12 034, « estimation »)."""
        roi = calculate_savings_roi(
            5.68, 44500, 56500, battery_kwh=5, productible=1651,
            stockage_present=True, regles_2710=True, fallback_tarif_kwh=1.75)
        self.assertEqual(roi['savings_model'], 'estimation')
        self.assertEqual((roi['eco_s_ann'], roi['eco_a_ann']), (9159, 12034))
        self.assertFalse(roi['bareme_national'])

    def test_hors_perimetre_rien_ne_change(self):
        self.assertIsNone(self._conso(niveau=4))
        self.assertIsNone(self._conso(mode='commercial'))
        self.assertIsNone(self._conso(conso_annuelle=6000))
        self.assertIsNone(self._conso(etude_horaire={'prod_kwh': 1}))

    # ── ERR-RHOR8-CONSO-SAISIE-SANS-DISTRIBUTEUR — 6 000 kWh/an saisis ──────
    def test_conso_saisie_memes_chiffres_que_l_ecran(self):
        """Même devis, conso SAISIE 6 000 kWh/an sans distributeur : serveur =
        écran (``calc/roi.test.mjs``, ERR-RHOR8-CONSO-SAISIE) 8 531 / 9 191,
        facture actuelle 9 789 ; hier le serveur estimait 9 159 / 10 366."""
        kwargs = dict(conso_annuelle_kwh=6000, battery_kwh=5,
                      productible=1651, stockage_present=True,
                      regles_2710=True, fallback_tarif_kwh=1.75)
        roi = calculate_savings_roi(5.68, 44500, 56500,
                                    bareme_national_defaut=True, **kwargs)
        self.assertEqual(roi['savings_model'], 'factures')
        self.assertTrue(roi['bareme_national'])
        self.assertEqual((roi['eco_s_ann'], roi['eco_a_ann'],
                          roi['facture_sans']), (8531, 9191, 9789))
        hier = calculate_savings_roi(5.68, 44500, 56500, **kwargs)
        self.assertEqual(hier['savings_model'], 'estimation')
        self.assertEqual((hier['eco_s_ann'], hier['eco_a_ann']), (9159, 10366))

    def test_perimetre_du_bareme_national(self):
        from types import SimpleNamespace
        from apps.ventes.quote_engine.etude_chiffrage import (
            _residentiel_niveau5_sans_horaire as perimetre)
        d5, d4 = SimpleNamespace(regles_calcul=5), SimpleNamespace(regles_calcul=4)
        self.assertTrue(perimetre(d5, '', {'conso_annuelle': 6000}))
        self.assertTrue(perimetre(d5, 'residentiel', {}))
        self.assertFalse(perimetre(d4, '', {'conso_annuelle': 6000}))
        self.assertFalse(perimetre(d5, 'commercial', {}))
        self.assertFalse(perimetre(d5, '', {'etude_horaire': {'prod_kwh': 1}}))
