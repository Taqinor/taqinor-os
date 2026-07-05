"""Tests YLEDG6 — auto-lettrage à l'encaissement (une facture soldée lettre
son 3421 d'un même code), délettrage automatique au rejet d'un paiement
(YLEDG5) et endpoint manuel ``lettrage/delettrer``/``lettrage/lettrer``."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta.models import EcritureComptable, LigneEcriture
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from core.events import paiement_enregistre, paiement_rejete

from apps.compta import receivers  # noqa: F401  (câblage ready())

User = get_user_model()


def make_company(slug='yledg6-co', nom='YLEDG6 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L6',
            email='yledg6@example.com', telephone='+212600000061')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YLEDG6',
            prix_vente=Decimal('1000'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG6-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))


class TestAutoLettrageSoldee(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_solde_complet_lettre_les_lignes_3421(self):
        from core.events import facture_emise
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-01',
            mode=Paiement.Mode.VIREMENT)
        self.facture.refresh_from_db()
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)

        lignes = LigneEcriture.objects.filter(
            company=self.company, compte__numero='3421')
        self.assertEqual(lignes.count(), 2)
        codes = set(lignes.values_list('lettrage', flat=True))
        self.assertEqual(len(codes), 1)
        self.assertNotIn('', codes)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_paiement_partiel_ne_lettre_rien(self):
        from core.events import facture_emise
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('500'), date_paiement='2026-07-01',
            mode=Paiement.Mode.VIREMENT)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)
        lignes = LigneEcriture.objects.filter(
            company=self.company, compte__numero='3421')
        self.assertTrue(all(not ln.lettrage for ln in lignes))


class TestDelettrageAutoRejet(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_rejet_paiement_delettre_le_lot(self):
        from core.events import facture_emise
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-01',
            mode=Paiement.Mode.VIREMENT)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)
        lignes_avant = LigneEcriture.objects.filter(
            company=self.company, compte__numero='3421')
        self.assertTrue(all(ln.lettrage for ln in lignes_avant))

        paiement_rejete.send(
            sender=Paiement, paiement=paiement, facture=self.facture,
            montant=paiement.montant, company=self.company)
        lignes_apres = LigneEcriture.objects.filter(
            company=self.company, compte__numero='3421')
        self.assertTrue(all(not ln.lettrage for ln in lignes_apres))


class TestLettrageEndpoint(_Base):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='yledg6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_delettrer_endpoint_reopens_lot(self):
        from core.events import facture_emise
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-01',
            mode=Paiement.Mode.VIREMENT)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)
        ligne = LigneEcriture.objects.filter(
            company=self.company, compte__numero='3421').first()
        code = ligne.lettrage
        self.assertTrue(code)

        resp = self.api.post(
            '/api/django/compta/lettrage/delettrer/',
            {'code': code}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['lignes_delettrees'], 2)
        lignes = LigneEcriture.objects.filter(
            company=self.company, compte__numero='3421')
        self.assertTrue(all(not ln.lettrage for ln in lignes))

    def test_lettrer_endpoint_rejects_unbalanced(self):
        from apps.compta import services as compta_services
        compta_services.seed_plan_comptable(self.company)
        compta_services.seed_journaux(self.company)
        compte3421 = compta_services.get_compte(self.company, '3421')
        journal = compta_services._journal(
            self.company, compta_services.Journal.Type.VENTE)
        ecriture = EcritureComptable.objects.create(
            company=self.company, journal=journal, date_ecriture='2026-07-01',
            libelle='OD test', reference='OD-YLEDG6',
            statut=EcritureComptable.Statut.VALIDEE)
        l1 = LigneEcriture.objects.create(
            company=self.company, ecriture=ecriture, compte=compte3421,
            debit=Decimal('100'), credit=Decimal('0'))
        l2 = LigneEcriture.objects.create(
            company=self.company, ecriture=ecriture, compte=compte3421,
            debit=Decimal('0'), credit=Decimal('50'))
        resp = self.api.post(
            '/api/django/compta/lettrage/lettrer/',
            {'ligne_ids': [l1.id, l2.id], 'code': 'ZZ'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
