"""ACHT20 (C-ACHT-018) — expédition d'une livraison atomique et exacte :
refus (400 nommant la ligne) si une ligne manque de stock au dépôt, statut
écrit après la ventilation dans la même transaction, lignes / dépôt / mode /
chantier figés dès `stock_mouvemente=True` ; l'annulation contre-transfère
exactement ce qui a été transféré.

Rejoue CKIT-4 (camionnette 3 après édition de ligne ; dépôt 2 recrédité de
5) et CKIT-5 (B : 2 en camionnette, expédition partielle acceptée).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_livraison_ventilation"
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.models import Installation, Livraison, LivraisonLigne
from apps.stock.models import EmplacementStock, Produit
from apps.stock.services import stock_breakdown

User = get_user_model()
BASE = '/api/django/installations'
FIGEE = 'Livraison expédiée : annulez-la puis recréez-la'


class LivraisonVentilationTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht20', defaults={'nom': 'Co ACHT20'})
        self.user = User.objects.create_user(
            username='resp-acht20', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Client ACHT20',
            email='client-acht20@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, client=client, reference='CH-ACHT20')
        self.depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.camion = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette', is_principal=False,
            ordre=10)
        self.depot2 = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt 2', is_principal=False,
            ordre=999)
        self.a = Produit.objects.create(
            company=self.company, nom='A', prix_vente=10, quantite_stock=20)
        self.b = Produit.objects.create(
            company=self.company, nom='B', prix_vente=10, quantite_stock=3)
        self._n = 0

    def _liv(self, lignes):
        self._n += 1
        liv = Livraison.objects.create(
            company=self.company, installation=self.inst, depot=self.depot,
            reference=f'LIV-ACHT20-{self._n}')
        for produit, qte in lignes:
            LivraisonLigne.objects.create(
                livraison=liv, produit=produit, designation=produit.nom,
                quantite=qte)
        return liv

    def _post(self, liv, action):
        return self.api.post(f'{BASE}/livraisons/{liv.id}/{action}/', {},
                             format='json')

    def _sur(self, produit, emplacement):
        produit.refresh_from_db()
        for ligne in stock_breakdown(produit):
            if ligne.get('emplacement_id') == emplacement.id:
                return ligne['quantite']
        return 0

    def test_ligne_figee_apres_expedition(self):
        liv = self._liv([(self.a, 4)])
        self.assertEqual(self._post(liv, 'expedier').status_code, 200)
        self.assertEqual(self._sur(self.a, self.camion), 4)
        ligne = liv.lignes.get()
        r = self.api.patch(f'{BASE}/livraison-lignes/{ligne.id}/',
                           {'quantite': 1}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(FIGEE, str(r.data))
        r = self.api.post(f'{BASE}/livraison-lignes/', {
            'livraison': liv.id, 'produit': self.a.id, 'quantite': 2},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        r = self.api.delete(f'{BASE}/livraison-lignes/{ligne.id}/')
        self.assertEqual(r.status_code, 400, r.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, 4)

    def test_depot_fige_apres_expedition(self):
        liv = self._liv([(self.a, 5)])
        self.assertEqual(self._post(liv, 'expedier').status_code, 200)
        r = self.api.patch(f'{BASE}/livraisons/{liv.id}/', {
            'depot': self.depot2.id, 'mode_acheminement': 'direct_site'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(FIGEE, str(r.data))
        liv.refresh_from_db()
        self.assertEqual(liv.depot_id, self.depot.id)

    def test_expedition_partielle_refusee(self):
        liv = self._liv([(self.a, 2), (self.b, 4)])
        mails = len(mail.outbox)
        r = self._post(liv, 'expedier')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Stock insuffisant pour B (3 < 4)', str(r.data))
        liv.refresh_from_db()
        self.assertEqual(liv.statut, Livraison.Statut.PLANIFIEE)
        self.assertFalse(liv.stock_mouvemente)
        self.assertIsNone(liv.notifie_transit_le)
        self.assertEqual(self._sur(self.a, self.camion), 0)
        self.assertEqual(self._sur(self.b, self.camion), 0)
        self.assertEqual(len(mail.outbox), mails)

    def test_annulation_exacte(self):
        liv = self._liv([(self.a, 4)])
        self.assertEqual(self._post(liv, 'expedier').status_code, 200)
        self.assertEqual(self._sur(self.a, self.depot), 16)
        self.assertEqual(self._post(liv, 'annuler').status_code, 200)
        self.assertEqual(self._sur(self.a, self.camion), 0)
        self.assertEqual(self._sur(self.a, self.depot), 20)
