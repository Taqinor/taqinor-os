"""ASEC35 — ``creer-devis`` du ticket SAV : les ``lignes[].produit_id`` reçus
sont résolus dans la société du ticket AVANT d'atteindre le domaine ventes.

Constat C-ASEC-006 site SAV : un produit d'une autre société (ou un id
inexistant) passait jusqu'au devis. Attendu : 400 sur ``lignes[i].produit_id``
et aucun devis créé ; un produit de la société → 201 inchangé.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.sav.models import Ticket
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()


class CreerDevisProduitsTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='ASEC35 A', slug='asec35-a')
        self.b = Company.objects.create(nom='ASEC35 B', slug='asec35-b')
        self.user = User.objects.create_user(
            username='asec35_admin', password='x', role_legacy='admin',
            company=self.a)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_a = Client.objects.create(
            company=self.a, nom='Client', prenom='A',
            email='asec35-client@example.invalid')
        self.produit_a = Produit.objects.create(
            company=self.a, nom='Onduleur A', sku='ASEC35-A',
            prix_vente=Decimal('900'))
        self.produit_b = Produit.objects.create(
            company=self.b, nom='Onduleur B', sku='ASEC35-B',
            prix_vente=Decimal('100'))
        self.ticket = Ticket.objects.create(
            company=self.a, reference='SAV-ASEC35-1', client=self.client_a,
            type=Ticket.Type.CORRECTIF,
            sous_garantie=Ticket.SousGarantie.NON, created_by=self.user)
        self.url = f'/api/django/sav/tickets/{self.ticket.pk}/creer-devis/'

    def _post(self, produit_id):
        return self.api.post(self.url, {'lignes': [
            {'designation': 'Main-d’œuvre', 'quantite': 1,
             'prix_unitaire': '50'},
            {'produit_id': produit_id, 'designation': 'Pièce',
             'quantite': 1, 'prix_unitaire': '900'},
        ]}, format='json')

    def _assert_refus(self, produit_id):
        avant = Devis.objects.count()
        resp = self._post(produit_id)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('lignes', resp.data)
        self.assertIn('1', {str(k) for k in resp.data['lignes']})
        self.assertIn('produit_id', resp.data['lignes'][1])
        self.assertEqual(Devis.objects.count(), avant)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.devis_id_ext)

    def test_produit_etranger_400(self):
        self._assert_refus(self.produit_b.id)

    def test_produit_inexistant_400_pas_500(self):
        self._assert_refus(999999)

    def test_produit_societe_ok(self):
        resp = self._post(self.produit_a.id)
        self.assertEqual(resp.status_code, 201, resp.content)
        devis = Devis.objects.get(pk=resp.data['devis_id'])
        self.assertEqual(devis.company_id, self.a.id)
        produits = set(LigneDevis.objects.filter(devis=devis)
                       .exclude(produit=None)
                       .values_list('produit_id', flat=True))
        self.assertEqual(produits, {self.produit_a.id})
