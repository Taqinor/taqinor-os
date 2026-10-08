"""AFAC16 (C-AFAC-012) — `RemiseEncaissement.statut` en lecture seule (seule
l'action `cloturer` le change), DELETE réservé au responsable/admin et refusé
hors remise OUVERTE, création atomique.

Rejoue la sonde FENC-5 (PATCH statut=validee par le technicien → 200 ; POST
cloturee+lignes → 500 et une remise clôturée orpheline ; DELETE d'une remise
clôturée → 204, remise et lignes supprimées). Endpoints réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_remise_statut"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
URL = '/api/django/ventes/remises-encaissement/'
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RemiseStatutTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC16 Co', slug=f'afac16-co-{_nxt()}')
        self.tech = User.objects.create_user(
            username=f'afac16_tech_{_nxt()}', password='x',
            role_legacy='normal', company=self.company)
        self.resp = User.objects.create_user(
            username=f'afac16_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        client = Client.objects.create(
            company=self.company, nom='Remise', prenom='AFAC16',
            email=f'afac16-{_nxt()}@example.invalid')
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC16-{_nxt()}',
            client=client, statut='emise', taux_tva=Decimal('20.00'),
            montant_ht=Decimal('50000.00'))
        self.api_tech = _api(self.tech)
        self.api_resp = _api(self.resp)

    def _paiement(self, montant='1500.00'):
        from apps.ventes.models import Paiement
        return Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal(montant), mode='especes',
            date_paiement=date.today(), created_by=self.tech)

    def _corps(self, **extra):
        corps = {'technicien': self.tech.id,
                 'date_collecte': date.today().isoformat(),
                 'montant_declare': '1500.00'}
        corps.update(extra)
        return corps

    def _remise_ouverte(self):
        r = self.api_tech.post(URL, self._corps(), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']

    def test_patch_statut_ignore(self):
        from apps.ventes.models import RemiseEncaissement
        rid = self._remise_ouverte()
        r = self.api_tech.patch(f'{URL}{rid}/', {'statut': 'validee'},
                                format='json')
        self.assertIn(r.status_code, (200, 400), r.data)
        remise = RemiseEncaissement.objects.get(pk=rid)
        self.assertEqual(remise.statut, 'ouverte')
        self.assertIsNone(remise.cloture_par)

    def test_creation_statut_ignore(self):
        from apps.ventes.models import RemiseEncaissement
        r = self.api_tech.post(URL, self._corps(statut='validee'),
                               format='json')
        self.assertEqual(r.status_code, 201, r.data)
        remise = RemiseEncaissement.objects.get(pk=r.data['id'])
        self.assertEqual(remise.statut, 'ouverte')
        self.assertIsNone(remise.cloture_par)

    def test_creation_atomique(self):
        from apps.ventes.models import LigneRemiseEncaissement, RemiseEncaissement
        paiement = self._paiement()
        r = self.api_tech.post(URL, self._corps(
            statut='cloturee', lignes=[{'paiement': paiement.id}]),
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        remise = RemiseEncaissement.objects.get(pk=r.data['id'])
        self.assertEqual(remise.statut, 'ouverte')
        self.assertEqual(RemiseEncaissement.objects.filter(
            company=self.company).count(), 1)
        self.assertTrue(LigneRemiseEncaissement.objects.filter(
            remise=remise, paiement=paiement).exists())

    def test_delete_technicien_refuse(self):
        from apps.ventes.models import RemiseEncaissement
        rid = self._remise_ouverte()
        r = self.api_tech.delete(f'{URL}{rid}/')
        self.assertEqual(r.status_code, 403, getattr(r, 'data', None))
        self.assertTrue(RemiseEncaissement.objects.filter(pk=rid).exists())

    def test_delete_cloturee_refuse(self):
        from apps.ventes.models import LigneRemiseEncaissement, RemiseEncaissement
        paiement = self._paiement()
        r = self.api_tech.post(URL, self._corps(
            lignes=[{'paiement': paiement.id}]), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        rid = r.data['id']
        r = self.api_resp.post(f'{URL}{rid}/cloturer/')
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api_resp.delete(f'{URL}{rid}/')
        self.assertEqual(r.status_code, 400, getattr(r, 'data', None))
        self.assertTrue(RemiseEncaissement.objects.filter(pk=rid).exists())
        self.assertTrue(LigneRemiseEncaissement.objects.filter(
            remise_id=rid).exists())
        # Une remise OUVERTE, elle, se supprime par le responsable.
        ouverte = self._remise_ouverte()
        r = self.api_resp.delete(f'{URL}{ouverte}/')
        self.assertEqual(r.status_code, 204, getattr(r, 'data', None))
