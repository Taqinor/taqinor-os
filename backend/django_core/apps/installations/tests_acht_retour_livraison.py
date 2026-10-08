"""ACHT21 (C-ACHT-019) — les retours d'une livraison sont plafonnés au cumul
livré (brouillon + validés, une seule fonction
`quantite_retournable_livraison`), et valider un retour est un TRANSFERT de
la destination de la livraison vers son dépôt, jamais une entrée.

Rejoue CKIT-6 : deux retours de 4 validés pour 4 livrées → stock global +8
(un seul retour gonflait déjà de 4).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_retour_livraison"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.models import Installation, Livraison, LivraisonLigne
from apps.stock.models import EmplacementStock, Produit
from apps.stock.services import stock_breakdown, transfer_stock

User = get_user_model()
BASE = '/api/django/installations'


class RetourLivraisonTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht21', defaults={'nom': 'Co ACHT21'})
        self.user = User.objects.create_user(
            username='resp-acht21', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Client ACHT21',
            email='client-acht21@example.invalid')
        inst = Installation.objects.create(
            company=self.company, client=client, reference='CH-ACHT21')
        self.depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.camion = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette', is_principal=False,
            ordre=10)
        self.a = Produit.objects.create(
            company=self.company, nom='A', prix_vente=10, quantite_stock=20)
        self.liv = Livraison.objects.create(
            company=self.company, installation=inst, depot=self.depot,
            reference='LIV-ACHT21')
        LivraisonLigne.objects.create(livraison=self.liv, produit=self.a,
                                      designation='A', quantite=4)
        for action in ('expedier', 'livrer'):
            r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/{action}/')
            self.assertEqual(r.status_code, 200, r.data)

    def _sur(self, emplacement):
        self.a.refresh_from_db()
        for ligne in stock_breakdown(self.a):
            if ligne.get('emplacement_id') == emplacement.id:
                return ligne['quantite']
        return 0

    def _retour(self):
        r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/generer-retour/')
        return r

    def _patch(self, ligne_id, qte):
        return self.api.patch(f'{BASE}/retour-livraison-lignes/{ligne_id}/',
                              {'quantite_retournee': qte}, format='json')

    def test_cumul_plafonne(self):
        r1 = self._retour()
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self._retour()
        self.assertEqual(r2.status_code, 201, r2.data)
        l1 = r1.data['lignes'][0]['id']
        l2 = r2.data['lignes'][0]['id']
        self.assertEqual(self._patch(l1, 4).status_code, 200)
        r = self._patch(l2, 4)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('quantite_retournee', r.data)
        # Un troisième retour n'a plus rien à reprendre.
        r3 = self._retour()
        self.assertEqual(r3.status_code, 400, r3.data)
        self.assertIn('Rien à retourner', str(r3.data))
        r = self.api.post(
            f'{BASE}/retours-livraison/{r1.data["id"]}/valider/')
        self.assertEqual(r.status_code, 200, r.data)
        self.a.refresh_from_db()
        self.assertEqual(self.a.quantite_stock, 20)

    def test_retour_est_un_transfert(self):
        self.assertEqual(self._sur(self.camion), 4)
        r1 = self._retour()
        l1 = r1.data['lignes'][0]['id']
        self.assertEqual(self._patch(l1, 4).status_code, 200)
        r = self.api.post(
            f'{BASE}/retours-livraison/{r1.data["id"]}/valider/')
        self.assertEqual(r.status_code, 200, r.data)
        self.a.refresh_from_db()
        self.assertEqual(self.a.quantite_stock, 20)  # global +0
        self.assertEqual(self._sur(self.camion), 0)
        self.assertEqual(self._sur(self.depot), 20)

    def test_destination_vide_refuse(self):
        # Le chantier a consommé ce qui était sur la camionnette.
        autre = EmplacementStock.objects.create(
            company=self.company, nom='Site', is_principal=False, ordre=50)
        transfer_stock(company=self.company, user=self.user,
                       produit_id=self.a.id, source_id=self.camion.id,
                       destination_id=autre.id, quantite=4,
                       note='consommé sur site')
        r1 = self._retour()
        l1 = r1.data['lignes'][0]['id']
        self.assertEqual(self._patch(l1, 4).status_code, 200)
        r = self.api.post(
            f'{BASE}/retours-livraison/{r1.data["id"]}/valider/')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Retour impossible', str(r.data))
        self.assertEqual(self._sur(self.depot), 16)
