"""NTRET11 — carte de fidélité dématérialisée (QR) + endpoint public tokenisé.

Le rattachement automatique du client au panier caisse après scan
(``frontend/src/features/pos/``) est HORS PÉRIMÈTRE de cette lane (frontend
n'appartient pas aux 2 apps possédées ici) : ce lot livre le champ
``code_qr`` + l'endpoint public lecture seule, prêt à être scanné."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.fidelite.models import CompteFidelite
from apps.fidelite.services import crediter_points_pour_vente
from authentication.models import Company


def _company(nom='Société QR'):
    return Company.objects.create(nom=nom)


def _client(company, nom='Zora', prenom='Client'):
    return Client.objects.create(company=company, nom=nom, prenom=prenom)


class CarteQrModelTests(TestCase):
    def test_code_qr_genere_automatiquement_et_non_sequentiel(self):
        company = _company()
        client_crm = _client(company)
        crediter_points_pour_vente(
            company=company, client=client_crm,
            montant_ttc=Decimal('100.00'), source_type='vente_comptoir')

        compte = CompteFidelite.objects.get(company=company, client=client_crm)
        self.assertTrue(compte.code_qr)
        self.assertGreaterEqual(len(compte.code_qr), 24)
        # Jamais l'id de la ligne (le token n'est pas une simple string de l'id).
        self.assertNotEqual(compte.code_qr, str(compte.id))

    def test_deux_comptes_ont_des_codes_qr_distincts(self):
        company = _company()
        c1 = _client(company, nom='Un')
        c2 = _client(company, nom='Deux')
        crediter_points_pour_vente(
            company=company, client=c1, montant_ttc=Decimal('50.00'),
            source_type='facture')
        crediter_points_pour_vente(
            company=company, client=c2, montant_ttc=Decimal('50.00'),
            source_type='facture')

        compte1 = CompteFidelite.objects.get(company=company, client=c1)
        compte2 = CompteFidelite.objects.get(company=company, client=c2)
        self.assertNotEqual(compte1.code_qr, compte2.code_qr)


class CartePubliqueEndpointTests(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.company = _company()
        self.client_crm = _client(self.company, nom='Bennani', prenom='Yassine')
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('200.00'), source_type='vente_comptoir')
        self.compte = CompteFidelite.objects.get(
            company=self.company, client=self.client_crm)

    def test_scan_du_qr_renvoie_les_infos_sans_authentification(self):
        resp = self.client_api.get(
            f'/api/django/fidelite/carte/{self.compte.code_qr}/')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['compte_id'], self.compte.id)
        self.assertEqual(data['client_id'], self.client_crm.id)
        self.assertEqual(data['solde_points'], 200)
        self.assertIn('Bennani', data['nom'])

    def test_reponse_ne_fuit_jamais_de_donnee_sensible(self):
        resp = self.client_api.get(
            f'/api/django/fidelite/carte/{self.compte.code_qr}/')

        data = resp.json()
        payload_str = str(data).lower()
        for champ_sensible in ('email', 'telephone', 'adresse', 'cin'):
            self.assertNotIn(champ_sensible, payload_str)

    def test_jeton_inconnu_renvoie_404(self):
        resp = self.client_api.get(
            '/api/django/fidelite/carte/jeton-inexistant-xyz/')
        self.assertEqual(resp.status_code, 404)

    def test_jeton_dune_autre_societe_reste_isole(self):
        autre_company = _company('Autre Société QR')
        autre_client = _client(autre_company, nom='Autre')
        crediter_points_pour_vente(
            company=autre_company, client=autre_client,
            montant_ttc=Decimal('300.00'), source_type='facture')
        autre_compte = CompteFidelite.objects.get(
            company=autre_company, client=autre_client)

        # Le jeton de l'AUTRE société résout SON PROPRE compte, jamais celui
        # de `self.company` (code_qr est globalement unique — un jeton ne
        # peut structurellement pas être "réutilisé" pour un autre tenant).
        resp = self.client_api.get(
            f'/api/django/fidelite/carte/{autre_compte.code_qr}/')
        data = resp.json()
        self.assertEqual(data['client_id'], autre_client.id)
        self.assertNotEqual(data['client_id'], self.client_crm.id)
