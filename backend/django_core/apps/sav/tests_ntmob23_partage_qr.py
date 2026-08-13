"""NTMOB23 — partage rapide d'une fiche équipement par QR.

Vérifie que l'endpoint renvoie le lien de partage TOKENISÉ DÉJÀ EXISTANT
(`/e/<public_token>`, le même que les étiquettes imprimées XSAV19), qu'il est
idempotent (le jeton n'est pas régénéré à chaque appel) et qu'il reste scopé à
la société.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser

from apps.stock.models import Produit

from .models import Equipement


class Ntmob23PartageQrTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTMOB23',
                                              slug='taqinor-ntmob23')
        self.autre = Company.objects.create(nom='Autre NTMOB23',
                                            slug='autre-ntmob23')
        self.user = CustomUser.objects.create_user(
            username='tech-ntmob23', password='x', company=self.company,
            role_legacy=CustomUser.ROLE_ADMIN)
        # `Equipement.produit` est obligatoire (NOT NULL en base).
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur NTMOB23')
        self.equipement = Equipement.objects.create(
            company=self.company, produit=self.produit,
            numero_serie='SN-NTMOB23')
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _url(self, eq):
        return f'/api/django/sav/equipements/{eq.pk}/partage-qr/'

    def test_renvoie_le_lien_tokenise_existant(self):
        resp = self.api.get(self._url(self.equipement))
        self.assertEqual(resp.status_code, 200)
        self.equipement.refresh_from_db()
        self.assertTrue(self.equipement.public_token)
        self.assertIn(f'/e/{self.equipement.public_token}', resp.data['url'])

    def test_jeton_stable_entre_deux_appels(self):
        premier = self.api.get(self._url(self.equipement)).data['url']
        second = self.api.get(self._url(self.equipement)).data['url']
        self.assertEqual(premier, second)

    def test_equipement_d_une_autre_societe_invisible(self):
        produit_autre = Produit.objects.create(
            company=self.autre, nom='Onduleur autre')
        etranger = Equipement.objects.create(
            company=self.autre, produit=produit_autre,
            numero_serie='SN-ETRANGER')
        self.assertEqual(self.api.get(self._url(etranger)).status_code, 404)

    def test_anonyme_refuse(self):
        anon = APIClient()
        self.assertIn(anon.get(self._url(self.equipement)).status_code,
                      (401, 403))
