"""AGNR40 (C-AGNR-028) — ``POST /ventes/devis/atomic/`` (le VRAI chemin de
création du générateur) respecte ``Idempotency-Key`` :

  * deux POST identiques avec la MÊME clé (le 2ᵉ après une coupure côté
    client survenue APRÈS le commit) -> UN seul devis, la 2ᵉ réponse rend le
    premier ;
  * même clé, corps différent -> 409 ``idempotency_conflict`` ;
  * une clé neuve (nouvelle session de création) -> un nouveau devis ;
  * la clé de ``/atomic/`` ne rejoue jamais une création de ``POST /devis/`` ;
  * un refus (400) n'est pas mémorisé : corrigé, la même clé crée.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agnr40_atomic_idempotent"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
URL = '/api/django/ventes/devis/atomic/'


class AtomicIdempotentTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='agnr40-co', defaults={'nom': 'agnr40-co'})
        self.user = User.objects.create_user(
            username='agnr40_user', password='x', role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AGNR40', telephone='+212600000040')
        self.produit = Produit.objects.create(
            company=self.company, nom='Smart Meter', prix_vente=Decimal('1200'),
            prix_achat=Decimal('800'), quantite_stock=10, tva=Decimal('20.00'))

    def _corps(self, quantite='1'):
        return {
            'client': self.client_obj.id, 'statut': 'brouillon', 'taux_tva': '20.00',
            'lignes': [{'produit': self.produit.id, 'designation': 'Smart Meter',
                        'quantite': quantite, 'prix_unitaire': '1200.00', 'taux_tva': '20'}],
        }

    def _nb(self):
        return Devis.objects.filter(company=self.company).count()

    def test_meme_cle_un_seul_devis(self):
        cle = {'HTTP_IDEMPOTENCY_KEY': 'agnr40-session-1'}
        premier = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertIn(premier.status_code, (200, 201), premier.content)
        second = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertEqual(second.status_code, premier.status_code)
        self.assertEqual(second.json()['id'], premier.json()['id'])
        self.assertEqual(self._nb(), 1)

    def test_meme_cle_corps_different_409(self):
        cle = {'HTTP_IDEMPOTENCY_KEY': 'agnr40-session-2'}
        premier = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertIn(premier.status_code, (200, 201), premier.content)
        autre = self.api.post(URL, self._corps(quantite='2'), format='json', **cle)
        self.assertEqual(autre.status_code, 409)
        self.assertEqual(self._nb(), 1)

    def test_cle_neuve_nouveau_devis_et_sans_cle_inchange(self):
        a = self.api.post(URL, self._corps(), format='json', HTTP_IDEMPOTENCY_KEY='s-a')
        b = self.api.post(URL, self._corps(), format='json', HTTP_IDEMPOTENCY_KEY='s-b')
        c = self.api.post(URL, self._corps(), format='json')
        for r in (a, b, c):
            self.assertIn(r.status_code, (200, 201), r.content)
        self.assertEqual(self._nb(), 3)

    def test_espace_de_cles_distinct_de_create(self):
        cle = {'HTTP_IDEMPOTENCY_KEY': 'agnr40-partagee'}
        cree = self.api.post('/api/django/ventes/devis/',
                             {'client': self.client_obj.id, 'taux_tva': '20.00'},
                             format='json', **cle)
        self.assertIn(cree.status_code, (200, 201), cree.content)
        atomique = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertIn(atomique.status_code, (200, 201), atomique.content)
        self.assertNotEqual(atomique.json()['id'], cree.json()['id'])

    def test_refus_non_memorise(self):
        cle = {'HTTP_IDEMPOTENCY_KEY': 'agnr40-session-3'}
        vide = dict(self._corps(), lignes=[])
        refus = self.api.post(URL, vide, format='json', **cle)
        self.assertEqual(refus.status_code, 400)
        ok = self.api.post(URL, self._corps(), format='json', **cle)
        self.assertIn(ok.status_code, (200, 201), ok.content)
        self.assertEqual(self._nb(), 1)
