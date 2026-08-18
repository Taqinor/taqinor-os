"""F6 (revue Fable, pré-merge 18/08/2026) — le bloc ``financing`` (QJ12,
``compute_financing_block``) reste un calcul INTERNE du builder ; il ne doit
plus être RE-PUBLIÉ sur le lien public tokenisé (``proposal_data``).

Contexte : le fondateur a retiré le crédit de toute surface client à quatre
reprises (PV80 — plus aucune mention de mensualité/banque sur la page
``/proposition`` ; ``financingComparison``/``backendFinancing`` gardées dans
``apps/web/src/lib/proposition.ts`` mais plus IMPORTÉES par la page). Rien ne
le RENDAIT plus nulle part, mais il restait SERVI en clair — à la racine de la
charge utile (``payload['financing']``) ET imbriqué sous ``payload['quote']``
(``'quote': data`` republie tel quel le dict issu de ``build_quote_data``,
qui porte lui aussi une clé ``financing``) — un JSON récupérable au bout du
jeton contredisait donc la décision fondateur même sans qu'aucun écran ne
l'affiche.

Ce test prouve que :
  1. le builder CONTINUE de calculer ``financing`` en interne (data-level,
     inchangé — cf. ``test_qj12_financing.py``) ;
  2. la vue publique ne le republie plus, ni à la racine, ni sous ``quote``.
"""
from decimal import Decimal

from django.test import TestCase


class FinancingNotServedPubliclyTests(TestCase):
    """Étage API — ``proposal_data`` ne porte plus AUCUNE clé ``financing``."""

    def _make_devis_avec_financement(self, slug):
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

    def test_builder_calcule_toujours_financing_en_interne(self):
        """Le calcul interne (QJ12) n'est PAS touché par ce correctif : un
        devis normal continue de produire ``data['financing']`` — seule la
        republication publique s'arrête (assertion suivante)."""
        from apps.ventes.quote_engine.builder import build_quote_data

        devis, _link = self._make_devis_avec_financement('f6-builder')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertIn('financing', data)
        self.assertIsNotNone(data['financing'])
        self.assertTrue(data['financing'].get('indicatif'))

    def test_proposal_data_ne_sert_aucune_cle_financing(self):
        """La charge utile publique ne porte plus ``financing`` — ni à la
        racine, ni imbriquée sous ``quote`` (la copie que ``'quote': data``
        aurait sinon republiée telle quelle)."""
        from rest_framework.test import APIClient

        devis, link = self._make_devis_avec_financement('f6-endpoint')

        # Preuve que la fixture porte bien un financement calculable — sinon
        # l'absence de la clé ne prouverait rien (elle serait absente de
        # toute façon, faute de total).
        from apps.ventes.quote_engine.builder import build_quote_data
        brut = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertIn('financing', brut)
        self.assertIsNotNone(brut['financing'])

        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertNotIn('financing', payload)
        self.assertIn('quote', payload)
        self.assertNotIn('financing', payload['quote'])
