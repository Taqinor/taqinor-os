"""ADOC77 — « Équipements posés » du dossier de remise = matériel EN SERVICE.

Constat C-ADOC-041 (S3) : ``_equipements_poses`` lisait TOUT le parc du
chantier — après un remplacement sous garantie, l'ancien numéro de série
(statut « remplacé »), le matériel hors service et le matériel mis au rebut
étaient imprimés avec leurs anciennes garanties.

Rendu WeasyPrint réel via la vraie route, texte extrait par fitz.

Run :
    python manage.py test apps.documents.tests.test_adoc_equipements_en_service -v2
"""
from decimal import Decimal

import fitz
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()


class EquipementsEnServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            slug='adoc77-co', nom='ADOC77 Co')
        self.user = User.objects.create_user(
            username='adoc77-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Fassi', prenom='Leila',
            telephone='+212600000077')
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-ADOC77-1', client=client,
            statut=Installation.Statut.INSTALLE)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur réseau 5kW', sku='ADOC77-OND',
            prix_vente=Decimal('9000.00'), prix_achat=Decimal('4000.00'),
            quantite_stock=3, marque='Huawei')

    def _equipement(self, serie, fin_garantie, **kw):
        return Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.chantier, numero_serie=serie,
            date_pose='2026-05-01', date_fin_garantie=fin_garantie, **kw)

    def test_dossier_remise_n_imprime_que_le_materiel_en_service(self):
        self._equipement('J6-OLD-0001', '2031-05-01',
                         statut=Equipement.Statut.REMPLACE)
        self._equipement('J6-NEW-0002', '2036-07-01',
                         statut=Equipement.Statut.EN_SERVICE)
        self._equipement('J6-HS-0003', '2032-05-01',
                         statut=Equipement.Statut.HORS_SERVICE)
        self._equipement('J6-REBUT-0004', '2033-05-01',
                         statut=Equipement.Statut.EN_SERVICE,
                         mis_au_rebut=True)

        r = self.api.get(
            f'/api/django/documents/chantiers/{self.chantier.pk}'
            '/dossier-remise/')
        self.assertEqual(r.status_code, 200)
        doc = fitz.open(stream=r.content, filetype='pdf')
        try:
            texte = '\n'.join(page.get_text() for page in doc)
        finally:
            doc.close()

        self.assertIn('Équipements posés', texte)
        self.assertIn('J6-NEW-0002', texte)
        self.assertIn('01/07/2036', texte)
        for ancien, garantie in (('J6-OLD-0001', '01/05/2031'),
                                 ('J6-HS-0003', '01/05/2032'),
                                 ('J6-REBUT-0004', '01/05/2033')):
            self.assertNotIn(ancien, texte)
            self.assertNotIn(garantie, texte)
