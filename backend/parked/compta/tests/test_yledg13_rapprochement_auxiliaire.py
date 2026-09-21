"""Tests YLEDG13 — rapprochement auxiliaire ↔ GL (tie-out AR/AP) : sur un jeu
sain écart global = 0 ; une facture émise non comptabilisée (toggle OFF)
apparaît en écart avec sa référence ; une OD manuelle sur 3421 est signalée ;
cross-company isolé."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors, services as compta_services
from apps.crm.models import Client
from apps.stock.models import FactureFournisseur, Fournisseur, Produit
from apps.ventes.models import Facture, LigneFacture
from core.events import facture_emise, facture_fournisseur_creee

from apps.compta import receivers  # noqa: F401  (câblage ready())

User = get_user_model()


def make_company(slug='yledg13-co', nom='YLEDG13 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestRapprochementClients(TestCase):
    def setUp(self):
        self.company = make_company()
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L13',
            email='yledg13@example.com', telephone='+212600000131')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YLEDG13',
            prix_vente=Decimal('1000'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG13-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_jeu_sain_ecart_global_zero(self):
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        rapport = selectors.rapprochement_auxiliaire_clients(self.company)
        self.assertEqual(rapport['ecart_total'], Decimal('0'))
        self.assertEqual(rapport['lignes'], [])

    def test_facture_non_comptabilisee_apparait_en_ecart(self):
        # Toggle OFF (défaut) : facture_emise n'a rien comptabilisé.
        rapport = selectors.rapprochement_auxiliaire_clients(self.company)
        self.assertEqual(len(rapport['lignes']), 1)
        ligne = rapport['lignes'][0]
        self.assertEqual(ligne['solde_gl'], Decimal('0'))
        self.assertGreater(ligne['encours_documentaire'], Decimal('0'))
        self.assertIn(self.facture.reference, ligne['references'])
        self.assertNotEqual(rapport['ecart_total'], Decimal('0'))

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_od_manuelle_sur_3421_signalee(self):
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        compte_clients = compta_services.get_compte(self.company, '3421')
        journal = compta_services._journal(
            self.company, compta_services.Journal.Type.OPERATIONS_DIVERSES)
        compta_services.creer_ecriture_od(
            self.company, '2026-07-01', 'OD manuelle test', [
                {'compte': compte_clients, 'debit': Decimal('500'),
                 'credit': Decimal('0'), 'tiers_type': 'client',
                 'tiers_id': self.cl.id},
                {'compte': compta_services.get_compte(self.company, '7121'),
                 'debit': Decimal('0'), 'credit': Decimal('500')},
            ], journal=journal)
        rapport = selectors.rapprochement_auxiliaire_clients(self.company)
        self.assertEqual(len(rapport['lignes']), 1)
        ligne = rapport['lignes'][0]
        # Le GL porte 500 de plus que le documentaire (OD sans document).
        self.assertEqual(ligne['ecart'], Decimal('-500'))

    def test_cross_company_isole(self):
        autre = make_company(slug='yledg13-co2', nom='YLEDG13 Co2')
        rapport = selectors.rapprochement_auxiliaire_clients(autre)
        self.assertEqual(rapport['lignes'], [])
        self.assertEqual(rapport['ecart_total'], Decimal('0'))


class TestRapprochementFournisseurs(TestCase):
    def setUp(self):
        self.company = make_company(slug='yledg13-ap-co', nom='YLEDG13 AP Co')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YLEDG13')
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-YLEDG13-0001',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'), date_facture='2026-07-01')

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_jeu_sain_ecart_global_zero(self):
        facture_fournisseur_creee.send(
            sender=FactureFournisseur, instance=self.facture,
            company=self.company)
        rapport = selectors.rapprochement_auxiliaire_fournisseurs(
            self.company)
        self.assertEqual(rapport['ecart_total'], Decimal('0'))
        self.assertEqual(rapport['lignes'], [])

    def test_facture_non_comptabilisee_apparait_en_ecart(self):
        rapport = selectors.rapprochement_auxiliaire_fournisseurs(
            self.company)
        self.assertEqual(len(rapport['lignes']), 1)
        ligne = rapport['lignes'][0]
        self.assertEqual(ligne['solde_gl'], Decimal('0'))
        self.assertGreater(ligne['encours_documentaire'], Decimal('0'))
        self.assertIn(self.facture.reference, ligne['references'])


class TestRapprochementEndpoint(TestCase):
    def setUp(self):
        self.company = make_company(
            slug='yledg13-ep-co', nom='YLEDG13 Endpoint Co')
        self.user = User.objects.create_user(
            username='yledg13_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)

    def test_endpoint_returns_json(self):
        resp = self.api.get('/api/django/compta/etats/rapprochement-clients/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('lignes', resp.data)
        self.assertIn('ecart_total', resp.data)

    def test_endpoint_csv_export(self):
        resp = self.api.get(
            '/api/django/compta/etats/rapprochement-fournisseurs/'
            '?export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
