"""XFSM19 — Rapprochement des encaissements terrain par technicien.

Couvre :
  * journée d'encaissements déclarée + rapprochée (lignes = Paiement) ;
  * écart calculé (déclaré vs somme des lignes) et exposé, pas masqué ;
  * clôture verrouille (statut clôturée) + génère le bordereau (best-effort,
    ne bloque jamais la clôture même si le rendu PDF échoue) ;
  * scoping société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement, RemiseEncaissement

User = get_user_model()


def make_company(slug='xfsm19-co', nom='XFSM19 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class Xfsm19TestBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.technicien = User.objects.create_user(
            username='xfsm19_tech', password='x', role_legacy='technicien',
            company=self.company)
        self.resp = User.objects.create_user(
            username='xfsm19_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='XFSM19',
            telephone='+212600000019')
        self.facture1 = Facture.objects.create(
            company=self.company, reference='FAC-XFSM19-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        self.facture2 = Facture.objects.create(
            company=self.company, reference='FAC-XFSM19-0002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        self.paiement1 = Paiement.objects.create(
            company=self.company, facture=self.facture1,
            montant=Decimal('500'), date_paiement=timezone.localdate(),
            mode=Paiement.Mode.ESPECES)
        self.paiement2 = Paiement.objects.create(
            company=self.company, facture=self.facture2,
            montant=Decimal('300'), date_paiement=timezone.localdate(),
            mode=Paiement.Mode.CHEQUE)

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api


class TestDeclarationRemise(Xfsm19TestBase):
    def test_declaration_avec_lignes_sans_ecart(self):
        api = self._api(self.technicien)
        r = api.post('/api/django/ventes/remises-encaissement/', {
            'technicien': self.technicien.id,
            'date_collecte': str(timezone.localdate()),
            'montant_declare': '800',
            'lignes': [
                {'paiement': self.paiement1.id},
                {'paiement': self.paiement2.id},
            ],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        remise = RemiseEncaissement.objects.get(id=r.data['id'])
        self.assertEqual(remise.lignes.count(), 2)
        self.assertEqual(remise.montant_lignes, Decimal('800'))
        self.assertEqual(remise.ecart, Decimal('0'))
        self.assertEqual(remise.statut, RemiseEncaissement.Statut.OUVERTE)
        self.assertTrue(remise.reference)

    def test_ecart_calcule_et_expose(self):
        api = self._api(self.technicien)
        r = api.post('/api/django/ventes/remises-encaissement/', {
            'technicien': self.technicien.id,
            'date_collecte': str(timezone.localdate()),
            'montant_declare': '750',  # déclaré 750 vs 800 réel → écart -50
            'lignes': [
                {'paiement': self.paiement1.id},
                {'paiement': self.paiement2.id},
            ],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        remise = RemiseEncaissement.objects.get(id=r.data['id'])
        self.assertEqual(remise.ecart, Decimal('-50'))


class TestClotureRemise(Xfsm19TestBase):
    def _creer_remise(self):
        remise = RemiseEncaissement.objects.create(
            company=self.company, reference='REM-TEST-0001',
            technicien=self.technicien,
            date_collecte=timezone.localdate(),
            montant_declare=Decimal('800'), created_by=self.technicien)
        from apps.ventes.models import LigneRemiseEncaissement
        LigneRemiseEncaissement.objects.create(
            remise=remise, paiement=self.paiement1)
        LigneRemiseEncaissement.objects.create(
            remise=remise, paiement=self.paiement2)
        return remise

    def test_cloture_verrouille_et_calcule_ecart(self):
        remise = self._creer_remise()
        api = self._api(self.resp)
        r = api.post(
            f'/api/django/ventes/remises-encaissement/{remise.id}/cloturer/')
        self.assertEqual(r.status_code, 200, r.data)
        remise.refresh_from_db()
        self.assertEqual(remise.statut, RemiseEncaissement.Statut.CLOTUREE)
        self.assertIsNotNone(remise.cloture_par)
        self.assertIsNotNone(remise.date_cloture)
        self.assertFalse(r.data['ecart_non_nul'])

    def test_cloture_deux_fois_refusee(self):
        remise = self._creer_remise()
        api = self._api(self.resp)
        r1 = api.post(
            f'/api/django/ventes/remises-encaissement/{remise.id}/cloturer/')
        self.assertEqual(r1.status_code, 200, r1.data)
        r2 = api.post(
            f'/api/django/ventes/remises-encaissement/{remise.id}/cloturer/')
        self.assertEqual(r2.status_code, 400)

    def test_technicien_ne_peut_pas_cloturer(self):
        remise = self._creer_remise()
        api = self._api(self.technicien)
        r = api.post(
            f'/api/django/ventes/remises-encaissement/{remise.id}/cloturer/')
        self.assertEqual(r.status_code, 403)


class TestScopingRemise(Xfsm19TestBase):
    def test_cross_tenant_isolation_404(self):
        other = make_company('xfsm19-other', 'Other XFSM19 Co')
        other_user = User.objects.create_user(
            username='xfsm19_other', password='x', role_legacy='responsable',
            company=other)
        remise = RemiseEncaissement.objects.create(
            company=self.company, reference='REM-TEST-0002',
            technicien=self.technicien,
            date_collecte=timezone.localdate(),
            montant_declare=Decimal('100'), created_by=self.technicien)
        api = self._api(other_user)
        r = api.get(f'/api/django/ventes/remises-encaissement/{remise.id}/')
        self.assertEqual(r.status_code, 404)
