"""AFAC8 (C-AFAC-010) — le reliquat d'un encaissement groupé à répartition
EXPLICITE n'est plus perdu : Σ parts < montant encaissé ⇒ le reste devient
une avance XFAC1, renvoyée dans la réponse (comme la branche FIFO).

Rejoue la sonde FENC-3 (« [explicite partielle] paiements=[('A','3000.00')]
avances=[] somme_creee=3000.00 »). Endpoint et service réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_groupe_reliquat"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
URL = '/api/django/ventes/factures/encaissement-groupe/'
AVANCES_URL = '/api/django/ventes/paiements/avances-non-affectees/'


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class GroupeReliquatTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC8 Co', slug=f'afac8-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac8_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Groupe', prenom='AFAC8',
            email=f'afac8-{_nxt()}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.a = self._facture(Decimal('12000'))
        self.b = self._facture(Decimal('12000'))

    def _facture(self, ttc):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC8-{_nxt():04d}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc)

    def _post(self, montant, repartition):
        return self.api.post(URL, {
            'client': self.client_obj.id, 'montant': montant,
            'mode': 'virement', 'date': '2026-10-08',
            'factures': [self.a.id, self.b.id],
            'repartition': repartition}, format='json')

    def test_repartition_partielle_cree_une_avance(self):
        from apps.ventes.models import Paiement
        r = self._post('10000', {str(self.a.id): '3000'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data), 2, r.data)
        sur_a = [p for p in r.data if p['facture'] == self.a.id]
        avances = [p for p in r.data if p['facture'] is None]
        self.assertEqual(Decimal(sur_a[0]['montant']), Decimal('3000'))
        self.assertEqual(Decimal(avances[0]['montant']), Decimal('7000'))
        # CLAUSE PERSISTANCE : l'avance est relisible et Σ créé = encaissé.
        lues = self.api.get(AVANCES_URL, {'client': self.client_obj.id})
        self.assertEqual(lues.status_code, 200, lues.data)
        self.assertEqual([Decimal(p['montant']) for p in lues.data],
                         [Decimal('7000')])
        total = sum(Paiement.objects.filter(
            company=self.company).values_list('montant', flat=True))
        self.assertEqual(total, Decimal('10000'))

    def test_somme_parts_superieure_refusee(self):
        from apps.ventes.models import Paiement
        r = self._post('5000', {str(self.a.id): '3000', str(self.b.id): '4000'})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(Paiement.objects.filter(company=self.company).exists())

    def test_reliquat_centime_ignore(self):
        from apps.ventes.models import Paiement
        r = self._post('3000.01', {str(self.a.id): '3000'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data), 1, r.data)
        self.assertFalse(Paiement.objects.filter(
            company=self.company, facture__isnull=True).exists())
