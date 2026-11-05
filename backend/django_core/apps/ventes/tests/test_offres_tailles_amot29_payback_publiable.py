"""AMOT29 (C-AMOT-030) — UN payback publié (le cashflow 25 ans du document,
avec « jamais remboursé ») pour les cartes Éco/Max, l'échelle de paliers
batterie et le repli de la carte Recommandé : ``pricing.payback_publiable``.
Le ratio simple ``coût ÷ économie`` ne sert plus qu'au tri interne.

Moteur réel (``compute_cashflow_payback``), aucun mock. Test-du-test :
remettre ``return round(cout / economie, 2)`` comme valeur publiée
(``offres_tailles._payback_publie``) ⇒ ``test_carte_eco_max_definition_pdf``
échoue (13,85 au lieu de 16,8).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes import offres_tailles as ot
from apps.ventes.domain.dimensionnement_devis import _payback_publie_palier
from apps.ventes.quote_engine.pricing import (
    compute_cashflow_payback, payback_publiable,
)


class PaybackPubliableTests(SimpleTestCase):
    def test_definition_du_document(self):
        attendu = compute_cashflow_payback(
            90000, 6500, inverter_replace_cost=15000)['payback_years']
        res = payback_publiable(90000, 6500, cout_onduleur_ttc=15000)
        self.assertEqual(res['payback_years'], round(attendu, 2))
        self.assertFalse(res['jamais_rembourse'])
        self.assertNotAlmostEqual(res['payback_years'], 90000 / 6500,
                                  delta=0.5)

    def test_jamais_rembourse_publie_comme_tel(self):
        res = payback_publiable(120000, 4000)
        self.assertTrue(res['jamais_rembourse'])
        self.assertIsNone(res['payback_years'])

    def test_non_chiffrable(self):
        for prix, eco in ((0, 100), (100, 0), (None, None)):
            self.assertIsNone(payback_publiable(prix, eco)['payback_years'])

    def test_carte_eco_max_definition_pdf(self):
        publie = ot._payback_publie(90000.0, 6500.0, cout_onduleur_ttc=15000)
        self.assertEqual(publie, payback_publiable(
            90000, 6500, cout_onduleur_ttc=15000)['payback_years'])
        self.assertNotEqual(publie, round(90000 / 6500, 2))
        self.assertIsNone(ot._payback_publie(120000.0, 4000.0))

    def test_carte_recommande_repli(self):
        """Sans ``roi_*`` servi, la carte Recommandé publie la définition du
        document, jamais le ratio simple."""
        from apps.ventes.tests.test_offres_tailles import _contexte_factice
        data = {'nb_panneaux_sans': 22, 'puissance_kwc_sans': 12.1,
                'totaux_sans': {'ttc': 90000.0}, 'eco_s_ann': 6500.0}
        contexte = _contexte_factice(SimpleNamespace(
            etude_params={}, reference='DEV-AMOT29'))
        carte = ot._carte_du_devis(contexte, data, 'sans')
        self.assertEqual(carte['payback_annees'], payback_publiable(
            90000, 6500)['payback_years'])
        self.assertNotEqual(carte['payback_annees'], round(90000 / 6500, 2))

    def test_carte_recommande_repli_avec_stockage(self):
        """AMOT107 (C-AMOT-VER-006) — sans ``roi_a`` servi, la carte « avec »
        de repli d'un devis au niveau 7 publie avec les arguments de
        ``_carte_moteur`` (stockage, part stockée 0, provision d'onduleur) ;
        au niveau 6 : le repli d'hier. Test-du-test : remettre
        ``_payback_publie(prix, economie)`` ⇒ échec."""
        from apps.ventes.tests.test_offres_tailles import _contexte_factice
        data = {'nb_panneaux_avec': 22, 'puissance_kwc_avec': 12.1,
                'totaux_avec': {'ttc': 90000.0}, 'eco_a_ann': 6500.0}
        ligne = SimpleNamespace(
            designation='Onduleur hybride Deye 5kW', quantite=1,
            prix_unitaire=12500.0, produit=None, variante='avec',
            compte_dans_totaux=True)
        devis = SimpleNamespace(
            etude_params={}, reference='DEV-AMOT107', regles_calcul=7,
            taux_tva=20, lignes=SimpleNamespace(all=lambda: [ligne]))
        carte = ot._carte_du_devis(_contexte_factice(devis), data, 'avec')
        self.assertEqual(carte['payback_annees'], payback_publiable(
            90000, 6500, stockage=True, part_batterie=0.0,
            cout_onduleur_ttc=15000)['payback_years'])
        self.assertEqual(carte['payback_annees'], 16.8)
        devis.regles_calcul = 6
        carte = ot._carte_du_devis(_contexte_factice(devis), data, 'avec')
        self.assertEqual(carte['payback_annees'], payback_publiable(
            90000, 6500)['payback_years'])

    def test_provision_non_remisee_niveau_2(self):
        """AMOT108 (C-AMOT-VER-007) — devis remisé de 10 %, onduleur 24 000
        TTC : au niveau 2 la carte chiffre la provision NON remisée que son
        PDF a imprimée (``_cout_onduleur_paye``) ; au niveau ≥ 3, 21 600.
        Test-du-test : retirer la garde de niveau ⇒ 21 600 au niveau 2."""
        from decimal import Decimal
        from unittest import mock

        from apps.ventes.tests.test_offres_tailles import _contexte_factice
        nom = 'Onduleur hybride Deye 10kW'
        lignes = type('Compo', (list,), {})([SimpleNamespace(
            produit=None, designation=nom, quantite=1, prix_unitaire=20000)])
        lignes.roles = ['onduleur_hybride']
        vus = {}
        for niveau, attendu in ((2, 24000.0), (3, 21600.0)):
            contexte = _contexte_factice(SimpleNamespace(
                taux_tva=Decimal('20'), regles_calcul=niveau), remise=0.9)
            contexte.composer = (lambda nb, avec_batterie=False, cible_kwh=None:
                                 None if avec_batterie else lignes)
            with mock.patch('apps.ventes.etude_horaire.calculer_etude_horaire',
                            return_value=None), \
                    mock.patch.object(ot, '_payback_publie',
                                      return_value=None) as publie:
                ot._carte_moteur(contexte, 10, avec_servable=False)
            vus[niveau] = publie.call_args.kwargs['cout_onduleur_ttc']
            self.assertEqual(vus[niveau], attendu)

    def test_err_rhor8_carte_recommande_jamais_rembourse_omise(self):
        """ERR-RHOR8-TAILLES-JAMAIS-RENTABILISE (devis 2300) — ``roi_*`` servi
        à la sentinelle 25,0 avec ``roi_*_jamais`` : la carte Recommandé OMET
        ``payback_annees`` (comme les cartes Éco/Max et le bandeau RHOR5),
        jamais « Rentabilisé en 25 ans » ; sans le drapeau, 21,7 reste 21,7.
        Test-du-test : retirer la lecture de ``_jamais`` ⇒ 25.0 publié, rouge."""
        from apps.ventes.tests.test_offres_tailles import _contexte_factice
        contexte = _contexte_factice(SimpleNamespace(
            etude_params={}, reference='DEV-RHOR8'))
        base = {'nb_panneaux_sans': 8, 'puissance_kwc_sans': 5.68,
                'nb_panneaux_avec': 8, 'puissance_kwc_avec': 5.68,
                'totaux_sans': {'ttc': 120000.0}, 'eco_s_ann': 4000.0,
                'totaux_avec': {'ttc': 160000.0}, 'eco_a_ann': 4500.0}
        for variante, cle in (('sans', 'roi_s'), ('avec', 'roi_a')):
            with self.subTest(variante=variante):
                data = dict(base, **{cle: 25.0, cle + '_jamais': True})
                carte = ot._carte_du_devis(contexte, data, variante)
                self.assertNotIn('payback_annees', carte)
                carte = ot._carte_du_devis(
                    contexte, dict(base, **{cle: 21.7, cle + '_jamais': False}), variante)
                self.assertEqual(carte['payback_annees'], 21.7)

    def test_echelle_paliers(self):
        lignes = [{'role': 'onduleur_hybride', 'quantite': 1,
                   'prix_unitaire_ht': 12500.0},
                  {'role': 'batterie', 'quantite': 1,
                   'prix_unitaire_ht': 20000.0}]
        publie = _payback_publie_palier(90000.0, 6500.0, lignes, 0.9)
        attendu = compute_cashflow_payback(
            90000.0, 6500.0, battery=True,
            inverter_replace_cost=round(12500 * 1.2 * 0.9, 2))
        self.assertEqual(publie, round(attendu['payback_years'], 2))
        self.assertIsNone(_payback_publie_palier(120000.0, 4000.0, [], 1.0))

    def test_echelle_palier_definition_roi_a(self):
        """AMOT102 (C-AMOT-VER-003, sonde 90 000 / 6 500 / onduleur 12 500 HT)
        — niveau 7 : la définition de ``roi_a`` (part stockée 0, TVA de la
        ligne) : 16,8, jamais 18,8. Un devis au niveau 6 garde 18,8.
        Test-du-test : remettre ``part_batterie=None`` ⇒ échec."""
        lignes = [{'role': 'onduleur_hybride', 'quantite': 1,
                   'prix_unitaire_ht': 12500.0, 'designation': 'Onduleur hybride'}]
        devis = SimpleNamespace(regles_calcul=7, company=None)
        self.assertEqual(_payback_publie_palier(
            90000.0, 6500.0, lignes, 1.0, devis=devis, taux_tva=20), 16.8)
        self.assertEqual(_payback_publie_palier(
            90000.0, 6500.0, lignes, 1.0, devis=SimpleNamespace(regles_calcul=6),
            taux_tva=20), 18.8)

    def test_provision_onduleur_offgrid_niveau_12(self):
        """AMOT120 (C-AMOT-VER4-010) — onduleur hors réseau 15 000 HT (TVA 20) :
        au niveau 12 la carte provisionne 18 000 et le palier 90 000 / 6 500
        publie le payback de l'hybride = ``roi_a`` (≥ 12 a) ; niveau 11 : les
        chiffres d'hier (aucune provision off-grid). Test-du-test : ôter
        ``onduleur_offgrid`` des rôles provisionnés ⇒ échec."""
        des = 'Onduleur hors-réseau Deye 6kW'
        ligne = SimpleNamespace(quantite=1, prix_unitaire=15000, produit=None, designation=des)
        n12, n11 = SimpleNamespace(regles_calcul=12, company=None), SimpleNamespace(regles_calcul=11, company=None)
        self.assertEqual(ot._cout_onduleur_ttc([ligne], ['onduleur_offgrid'], 1.0, 20, None, n12), 18000.0)
        self.assertEqual(ot._cout_onduleur_ttc([ligne], ['onduleur_offgrid'], 1.0, 20, None), 18000.0)
        self.assertIsNone(ot._cout_onduleur_ttc([ligne], ['onduleur_offgrid'], 1.0, 20, None, n11))

        def palier(role, devis):
            return _payback_publie_palier(90000.0, 6500.0, [{
                'role': role, 'quantite': 1, 'prix_unitaire_ht': 15000.0, 'designation': des}],
                1.0, devis=devis, taux_tva=20)
        roi_a = round(compute_cashflow_payback(
            90000.0, 6500.0, battery=True, battery_share=0.0,
            inverter_replace_cost=18000.0)['payback_years'], 2)
        self.assertEqual(palier('onduleur_offgrid', n12), roi_a)
        self.assertEqual(palier('onduleur_hybride', n12), roi_a)
        self.assertGreaterEqual(roi_a, 12)
        self.assertLess(palier('onduleur_offgrid', n11), palier('onduleur_hybride', n11))


class ArrondiAffichageCartesTests(SimpleTestCase):
    """D-ENF-ARRONDI-PDF (fondateur 30/10/2026) — les cartes de tailles
    arrondissent COMME le moteur de rendu : moitié vers le haut au niveau 6,
    ``round`` d'hier pour un devis envoyé avant (la carte et le PDF ne
    divergent jamais d'une unité)."""

    def setUp(self):
        from apps.ventes.quote_engine.montants import poser_regles_origine
        poser_regles_origine(False)
        self.addCleanup(poser_regles_origine, False)

    def test_cas_moitie(self):
        self.assertEqual(ot._payback(1.0, 8.0), 0.13)              # round : 0.12
        self.assertEqual(ot._prix_par_kwc(30100.0, 8.0), 3763.0)    # round : 3762
        data = {'cashflow_sans': [-100000.0, -99999.875]}
        self.assertEqual(ot._cumul_servi(data, 'sans', 100000.0), 0.13)  # round : 0.12

    def test_hors_moitie_inchange(self):
        self.assertEqual(ot._payback(90000.0, 6500.0), round(90000 / 6500, 2))
        self.assertEqual(ot._prix_par_kwc(34400.0, 7.1), float(round(34400 / 7.1)))

    def test_devis_envoye_garde_round(self):
        from apps.ventes.quote_engine.montants import poser_regles_origine
        poser_regles_origine(False, arrondi_historique=True)
        self.assertEqual(ot._payback(1.0, 8.0), 0.12)
        self.assertEqual(ot._prix_par_kwc(30100.0, 8.0), 3762.0)
