"""QJR667 — le rattachement d'une ligne à un lot multi-sites survit à
l'enregistrement de l'Édition complète (replace-lines recrée les lignes) ;
un lot qui n'appartient pas à CE devis n'est jamais accepté.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr667_lot_aller_retour"
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import LotDevis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)


class LotAllerRetourTests(TestCase):

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = ProduitFactory(company=self.company)
        self.devis = DevisFactory(company=self.company)
        self.lot = LotDevis.objects.create(
            company=self.company, devis=self.devis, nom_lot='Site A')

    def _replace(self, lot):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': [{'produit': self.produit.id, 'quantite': '2',
                         'prix_unitaire': '1000', 'lot': lot}]},
            format='json')

    def test_le_lot_du_devis_survit(self):
        r = self._replace(self.lot.id)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.devis.lignes.get().lot_id, self.lot.id)

    def test_un_lot_d_un_autre_devis_est_ignore(self):
        autre = DevisFactory(company=self.company)
        lot_autre = LotDevis.objects.create(
            company=self.company, devis=autre, nom_lot='Ailleurs')
        r = self._replace(lot_autre.id)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(self.devis.lignes.get().lot_id)

    def test_un_lot_illisible_vaut_hors_lot(self):
        r = self._replace('abc')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(self.devis.lignes.get().lot_id)
