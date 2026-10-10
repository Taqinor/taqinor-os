"""AFAC69 (C-AFAC-059) — bornes d'argent de la facture et de l'avoir
validées au SÉRIALISEUR : ``remise_globale`` / ``remise`` de ligne hors
0-100, ``prix_unitaire`` ou ``quantite`` négatifs ⇒ 400 nommé par champ,
jamais un 500 ``CheckViolation`` ; aucune écriture ; les valeurs valides
restent acceptées.

Rejoue la sonde FUI-8 (chaque cas donnait 500 ``server_error``). Endpoints,
sérialiseurs et modèles réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_bornes_facture"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _texte(data):
    return str(data)


class BornesFactureTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import Facture, LigneFacture
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC69 Co', slug=f'afac69-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac69_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        client = Client.objects.create(
            company=self.company, nom='Bornes', prenom='AFAC69',
            email=f'afac69-{_nxt()}@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku=f'AFAC69-{_nxt()}',
            prix_vente=Decimal('1000'), quantite_stock=10)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC69-{_nxt()}',
            client=client, statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'))
        self.ligne = LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _poster_ligne(self, **surcharge):
        corps = {
            'facture': self.facture.id, 'produit': self.produit.id,
            'designation': 'Panneau', 'quantite': '2',
            'prix_unitaire': '500', 'remise': '0', 'taux_tva': '20',
        }
        corps.update(surcharge)
        return self.api.post(
            '/api/django/ventes/factures-lignes/', corps, format='json')

    def _assert_lignes_intactes(self):
        self.assertEqual(self.facture.lignes.count(), 1)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.remise, Decimal('0'))
        self.assertEqual(self.ligne.prix_unitaire, Decimal('1000'))
        self.assertEqual(self.ligne.quantite, Decimal('1'))

    def test_remise_globale_150_400(self):
        r = self.api.patch(
            f'/api/django/ventes/factures/{self.facture.id}/',
            {'remise_globale': '150'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('remise_globale', _texte(r.data))
        self.assertIn('entre 0 et 100', _texte(r.data))
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.remise_globale, Decimal('0'))

    def test_remise_globale_valide_acceptee(self):
        r = self.api.patch(
            f'/api/django/ventes/factures/{self.facture.id}/',
            {'remise_globale': '10'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.remise_globale, Decimal('10'))

    def test_ligne_remise_150_400(self):
        r = self._poster_ligne(remise='150')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('remise', _texte(r.data))
        self.assertIn('entre 0 et 100', _texte(r.data))
        self._assert_lignes_intactes()

    def test_prix_negatif_400(self):
        r = self._poster_ligne(prix_unitaire='-10')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('prix_unitaire', _texte(r.data))
        self.assertIn('ne peut pas être négatif', _texte(r.data))
        self._assert_lignes_intactes()

    def test_quantite_negative_400(self):
        r = self._poster_ligne(quantite='-1')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('quantite', _texte(r.data))
        self.assertIn('négative', _texte(r.data))
        self._assert_lignes_intactes()

    def test_patch_ligne_remise_150_400(self):
        r = self.api.patch(
            f'/api/django/ventes/factures-lignes/{self.ligne.id}/',
            {'remise': '150'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self._assert_lignes_intactes()

    def test_ligne_valide_acceptee(self):
        r = self._poster_ligne(remise='10')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.facture.lignes.count(), 2)
