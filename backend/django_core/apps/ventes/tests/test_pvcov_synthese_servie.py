"""PVCOV (fondateur, 18/08/2026) — le « −N % », l'avant/après annuel et la
donut de couverture de la proposition EN LIGNE viennent du MÊME calcul que la
page 1 du PDF : ``residential/renderer.synthese_economies`` est LA source, la
vue publique la sert telle quelle, la page web ne recalcule rien.

Deux étages :
  - tests PURS (dict → dict, aucune BD) : la fonction extraite reproduit
    exactement les champs que ``_augment`` pose pour la couverture du PDF, et
    dégrade en ``None`` (jamais un chiffre inventé) hors forme résidentielle ;
  - test API : ``proposal_data`` sert les cinq clés, égales au calcul du PDF —
    et à ``None`` pour un devis non-résidentiel (F5, revue Fable pré-merge
    18/08/2026) : le builder produit un ``eco_a_monthly``/``factures_mensuelles``
    PROXY pour TOUT mode, donc ``synthese_economies(data)`` seul est non-None
    même sur un industriel/commercial — la vue le gate désormais avec
    ``residential/renderer.is_residential`` avant de servir ces cinq clés.
"""
from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine.residential import sample_data
from apps.ventes.quote_engine.residential.renderer import (
    _augment, synthese_economies,
)

CLES = ("pct_cut", "annual_before", "annual_after",
        "coverage_pct", "coverage_estimated")


class SyntheseEconomiesPureTests(SimpleTestCase):
    """Étage pur — aucune fixture, aucune BD (SimpleTestCase : exécutable
    sur l'hôte sans Postgres, comme les drift-locks du barème)."""

    def test_miroir_exact_de_augment(self):
        data = sample_data.build("deux")
        synth = synthese_economies(data)
        self.assertIsNotNone(synth)
        d = _augment(data)
        for k in ("bills_before", "bills_after") + CLES:
            self.assertEqual(d[k], synth[k], k)

    def test_pct_cut_formule_de_la_couverture(self):
        synth = synthese_economies(sample_data.build("deux"))
        self.assertEqual(
            synth["pct_cut"],
            round((1 - synth["annual_after"] / max(1, synth["annual_before"])) * 100),
        )

    def test_degrade_en_none_jamais_un_chiffre_invente(self):
        data = sample_data.build("deux")
        self.assertIsNone(synthese_economies({}))
        self.assertIsNone(synthese_economies({**data, "factures_mensuelles": [100] * 11}))
        self.assertIsNone(synthese_economies({**data, "prod_kwh": 0}))
        self.assertIsNone(synthese_economies({**data, "factures_mensuelles": [0] * 12}))

    def test_conso_reelle_prime_et_le_drapeau_estimation_tombe(self):
        data = sample_data.build("deux")
        reel = synthese_economies({**data, "conso_annuelle_kwh": 15000})
        self.assertFalse(reel["coverage_estimated"])
        derive = synthese_economies({**data, "conso_annuelle_kwh": None})
        self.assertTrue(derive["coverage_estimated"])
        self.assertLessEqual(reel["coverage_pct"], 100)
        self.assertGreaterEqual(reel["coverage_pct"], 1)


class ProposalDataServeSyntheseTests(TestCase):
    """Étage API — la vue publique sert les cinq clés, égales au PDF.

    Fixture calquée sur test_arc5_proposal_public_access / test_pv86 (champs
    RÉELS des modèles : reference obligatoire, prix_unitaire sur la ligne,
    URL publique /api/django/public/proposal/<token>/data/).
    """

    def test_proposal_data_sert_les_cinq_cles_du_pdf(self):
        from decimal import Decimal
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from authentication.models import Company
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis, ShareLink

        company = Company.objects.get_or_create(
            slug='pvcov-co', defaults={'nom': 'PVCOV Co'})[0]
        get_user_model().objects.get_or_create(
            username='pvcov', defaults={'password': 'x', 'company': company})
        client_obj = Client.objects.get_or_create(
            company=company, nom='Client PVCOV', defaults={})[0]
        devis = Devis.objects.get_or_create(
            company=company, reference='DEV-PVCOV-01',
            defaults={'client': client_obj, 'taux_tva': Decimal('20'),
                      'statut': 'envoye',
                      'etude_params': {
                          'factures_mensuelles': [1800] * 12,
                          'distributeur': 'onee',
                          'ville': 'casablanca'}})[0]
        lignes = (
            ('Panneau Canadien Solar 710W', '14', '1166.67'),
            ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
            ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
            ('Batterie Dyness 10 kWh', '1', '25000.00'),
        )
        for nom, qte, pu in lignes:
            produit = Produit.objects.create(
                company=company, nom=nom, prix_vente=pu, quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        link = ShareLink.objects.create(company=company, devis=devis)

        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        # Les cinq clés PVCOV sont posées à la RACINE de la charge utile
        # (``payload['pct_cut']``…), jamais imbriquées sous ``quote`` —
        # ``quote`` ne porte que la sortie brute de ``build_quote_data``.
        payload = resp.json()

        from apps.ventes.quote_engine.builder import build_quote_data
        attendu = synthese_economies(
            build_quote_data(devis, {'pdf_mode': 'full'}))
        if attendu is None:
            # Forme non résidentielle : les clés existent et valent None.
            for k in CLES:
                self.assertIn(k, payload)
                self.assertIsNone(payload[k])
        else:
            for k in CLES:
                self.assertEqual(payload[k], attendu[k], k)

    def test_proposal_data_omet_tout_sans_donnee_reelle(self):
        """Z2 (ORDRE FONDATEUR, 20/08/2026) — un devis résidentiel SANS aucune
        donnée réelle d'ancrage (ni 12 factures réelles, ni conso annuelle, ni
        distributeur/tarif) ne publie plus AUCUN chiffre d'économies sur le lien
        client : les cinq clés de synthèse valent None, et l'économie annuelle
        + le payback — que la page lit EN DIRECT dans ``quote`` — partent avec
        elles. Sans cela, la page web aurait continué d'afficher « Économie ≈ X
        MAD/an » et « Rentabilisé en Y ans » là où le PDF du même devis ne les
        montre plus : deux histoires d'argent pour un seul devis."""
        from decimal import Decimal
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from authentication.models import Company
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis, ShareLink

        company = Company.objects.get_or_create(
            slug='pvcov-z2-co', defaults={'nom': 'PVCOV Z2 Co'})[0]
        get_user_model().objects.get_or_create(
            username='pvcov-z2', defaults={'password': 'x', 'company': company})
        client_obj = Client.objects.get_or_create(
            company=company, nom='Client PVCOV Z2', defaults={})[0]
        devis = Devis.objects.get_or_create(
            company=company, reference='DEV-PVCOV-Z2-01',
            defaults={'client': client_obj, 'taux_tva': Decimal('20'),
                      'statut': 'envoye',
                      # AUCUN distributeur, AUCUNE conso, AUCUNE facture réelle
                      'etude_params': {'ville': 'casablanca'}})[0]
        lignes = (
            ('Panneau Canadien Solar 710W', '14', '1166.67'),
            ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
            ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
            ('Batterie Dyness 10 kWh', '1', '25000.00'),
        )
        for nom, qte, pu in lignes:
            produit = Produit.objects.create(
                company=company, nom=nom, prix_vente=pu, quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        link = ShareLink.objects.create(company=company, devis=devis)

        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        for k in CLES:
            self.assertIn(k, payload, k)
            self.assertIsNone(payload[k], k)
        quote = payload['quote']
        for k in ('eco_s_ann', 'eco_a_ann', 'eco_a_cumul', 'roi_s', 'roi_a'):
            self.assertIsNone(quote[k], k)
        # Ce qui reste servi est une donnée du devis, pas un calcul de repli.
        self.assertTrue(quote['total_sans'] or quote['total_avec'])
        self.assertTrue(quote['puissance_kwc'])

    def test_proposal_data_industriel_sert_cinq_none(self):
        """F5 (revue Fable, pré-merge 18/08/2026) — un devis INDUSTRIEL fait,
        lui aussi, tourner ``calculate_savings_roi`` (TOUT mode) : le builder
        produit donc un ``eco_a_monthly`` et un ``factures_mensuelles`` PROXY
        même sans étude — ``synthese_economies(data)`` seul renvoie alors une
        valeur non-None pour ce devis. Mais cette synthèse EST la page 1 du
        PDF RÉSIDENTIEL ; un devis industriel a SA propre étude (bloc
        ``mode_kpis``, testé ailleurs) et aucun document remis à ce client ne
        montre l'avant/après fabriqué. La vue publique doit donc servir les
        cinq clés à ``None`` pour ce mode — jamais la valeur calculée."""
        from decimal import Decimal
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from authentication.models import Company
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis, ShareLink

        company = Company.objects.get_or_create(
            slug='pvcov-ind-co', defaults={'nom': 'PVCOV Industriel Co'})[0]
        get_user_model().objects.get_or_create(
            username='pvcov-ind', defaults={'password': 'x', 'company': company})
        client_obj = Client.objects.get_or_create(
            company=company, nom='Client PVCOV Industriel', defaults={})[0]
        devis = Devis.objects.get_or_create(
            company=company, reference='DEV-PVCOV-IND-01',
            defaults={'client': client_obj, 'taux_tva': Decimal('20'),
                      'statut': 'envoye', 'mode_installation': 'industriel',
                      'etude_params': {
                          'factures_mensuelles': [1800] * 12,
                          'distributeur': 'onee',
                          'ville': 'casablanca'}})[0]
        lignes = (
            ('Panneau Canadien Solar 710W', '14', '1166.67'),
            ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
            ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
            ('Batterie Dyness 10 kWh', '1', '25000.00'),
        )
        for nom, qte, pu in lignes:
            produit = Produit.objects.create(
                company=company, nom=nom, prix_vente=pu, quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        link = ShareLink.objects.create(company=company, devis=devis)

        # Preuve que la fixture reproduit bien la fuite F5 côté données PURES
        # (sans la garde ``is_residential`` de la vue) — sinon ce test ne
        # prouverait rien : un devis dont ``synthese_economies`` serait déjà
        # None ne distinguerait pas « gardé » de « jamais produit ».
        from apps.ventes.quote_engine.builder import build_quote_data
        brut = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertIsNotNone(
            synthese_economies(brut),
            'fixture invalide : le builder ne produit pas de forme PROXY '
            'pour ce devis industriel — le test ne prouverait rien.')

        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        for k in CLES:
            self.assertIn(k, payload, k)
            self.assertIsNone(payload[k], k)
