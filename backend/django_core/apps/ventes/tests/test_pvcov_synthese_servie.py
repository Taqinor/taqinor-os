"""PVCOV (fondateur, 18/08/2026) — le « −N % », l'avant/après annuel et la
donut de couverture de la proposition EN LIGNE viennent du MÊME calcul que la
page 1 du PDF : ``residential/renderer.synthese_economies`` est LA source, la
vue publique la sert telle quelle, la page web ne recalcule rien.

Deux étages :
  - tests PURS (dict → dict, aucune BD) : la fonction extraite reproduit
    exactement les champs que ``_augment`` pose pour la couverture du PDF, et
    dégrade en ``None`` (jamais un chiffre inventé) hors forme résidentielle ;
  - test API : ``proposal_data`` sert les cinq clés, égales au calcul du PDF.
"""
from django.test import TestCase

from apps.ventes.quote_engine.residential import sample_data
from apps.ventes.quote_engine.residential.renderer import (
    _augment, synthese_economies,
)

CLES = ("pct_cut", "annual_before", "annual_after",
        "coverage_pct", "coverage_estimated")


class SyntheseEconomiesPureTests(TestCase):
    """Étage pur — aucune fixture, aucune BD."""

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
        quote = resp.json().get('quote') or resp.json()

        from apps.ventes.quote_engine.builder import build_quote_data
        attendu = synthese_economies(
            build_quote_data(devis, {'pdf_mode': 'full'}))
        if attendu is None:
            # Forme non résidentielle : les clés existent et valent None.
            for k in CLES:
                self.assertIn(k, quote)
                self.assertIsNone(quote[k])
        else:
            for k in CLES:
                self.assertEqual(quote[k], attendu[k], k)
