"""F6 (revue Fable, 18/08/2026) puis QJR630 — aucun bloc ``financing`` : ni
calculé par le builder, ni servi sur le lien public tokenisé.

Contexte : le fondateur a retiré le crédit de toute surface client à quatre
reprises (PV80 — plus aucune mention de mensualité/banque sur la page
``/proposition``). F6 avait arrêté la REPUBLICATION du bloc ; QJR630 supprime
son PRODUCTEUR (``builder.compute_financing_block`` et sa table de taux
bancaires « milieu de fourchette » codés en dur), qu'aucun rendu ne lisait.

Ce test reste comme GARDE :
  1. le builder n'expose plus ``compute_financing_block`` et ne pose plus
     ``data['financing']`` ;
  2. la vue publique ne sert ``financing`` ni à la racine, ni sous ``quote``.
"""
from decimal import Decimal

from django.test import TestCase


class FinancingNotServedPubliclyTests(TestCase):
    """Le builder ne produit plus ``financing`` ; ``proposal_data`` non plus."""

    def _make_devis(self, slug):
        from django.contrib.auth import get_user_model
        from authentication.models import Company
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis, ShareLink

        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': 'F6 Financing Co'})[0]
        get_user_model().objects.get_or_create(
            username=f'{slug}-user', defaults={'password': 'x', 'company': company})
        client_obj = Client.objects.get_or_create(
            company=company, nom='Client F6', defaults={})[0]
        devis = Devis.objects.get_or_create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            defaults={'client': client_obj, 'taux_tva': Decimal('20'),
                      'statut': 'envoye'})[0]
        lignes = (
            ('Panneau Canadien Solar 710W', '14', '1166.67'),
            ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
        )
        for nom, qte, pu in lignes:
            produit = Produit.objects.create(
                company=company, nom=nom, prix_vente=pu, quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        link = ShareLink.objects.create(company=company, devis=devis)
        return devis, link

    def test_le_producteur_a_disparu(self):
        """QJR630 — plus de chaîne de financement à taux inventés."""
        from apps.ventes.quote_engine import builder
        from apps.ventes.quote_engine.builder import build_quote_data

        self.assertFalse(hasattr(builder, 'compute_financing_block'))
        self.assertFalse(hasattr(builder, '_FINANCING_PROGRAMS'))
        devis, _link = self._make_devis('f6-builder')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertNotIn('financing', data)
        # Le total reste calculé : l'absence n'est pas un devis vide.
        self.assertGreater(data['display_total'], 0)

    def test_proposal_data_ne_sert_aucune_cle_financing(self):
        """La charge utile publique ne porte pas ``financing`` — ni à la
        racine, ni imbriquée sous ``quote``."""
        from rest_framework.test import APIClient

        _devis, link = self._make_devis('f6-endpoint')
        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertNotIn('financing', payload)
        self.assertIn('quote', payload)
        self.assertNotIn('financing', payload['quote'])

    def test_la_formule_d_annuite_vit_dans_economie(self):
        """Son seul appelant restant (``tableau_pret``) la trouve à côté."""
        from apps.ventes import economie
        self.assertEqual(economie._monthly_loan_payment(12_000, 0.0, 12),
                         1000.0)
        self.assertEqual(economie._monthly_loan_payment(0, 0.06, 120), 0.0)
