"""XPOS9 — Capture des n° de série à la vente → garantie SAV automatique.

Couvre :
  * `sav.services.creer_equipement_depuis_vente_pos` crée un `Equipement`
    SAV garanti (sans chantier, `client_vente` posé), garantie calculée
    depuis `date_vente` + `Produit.garantie_mois` ;
  * un n° de série en doublon (déjà au parc de la société) est refusé
    (`SerieDejaEnregistreeError`).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xpos9 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Equipement
from apps.sav.services import (
    SerieDejaEnregistreeError, creer_equipement_depuis_vente_pos,
)
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug='sav-xpos9', nom='Sav Co XPOS9'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class XPOS9ServiceTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xpos9_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xpos9-client@example.invalid')
        categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs XPOS9')
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur Sérialisé', sku='OND-XPOS9',
            prix_achat=3000, prix_vente=6000, quantite_stock=5,
            categorie=categorie, suivi_serie=True, garantie_mois=24)

    def test_cree_equipement_garanti_sans_chantier(self):
        from datetime import date
        equip = creer_equipement_depuis_vente_pos(
            company=self.company, produit=self.onduleur,
            client=self.client_obj, numero_serie='SN-XPOS9-1',
            date_vente=date(2026, 1, 10), created_by=self.admin)
        self.assertIsNone(equip.installation_id)
        self.assertEqual(equip.client_vente_id, self.client_obj.id)
        self.assertEqual(equip.numero_serie, 'SN-XPOS9-1')
        self.assertEqual(equip.date_fin_garantie, date(2028, 1, 10))

    def test_doublon_serie_refuse(self):
        from datetime import date
        Equipement.objects.create(
            company=self.company, produit=self.onduleur,
            numero_serie='SN-XPOS9-DUP', client_vente=self.client_obj,
            created_by=self.admin)
        with self.assertRaises(SerieDejaEnregistreeError):
            creer_equipement_depuis_vente_pos(
                company=self.company, produit=self.onduleur,
                client=self.client_obj, numero_serie='SN-XPOS9-DUP',
                date_vente=date(2026, 1, 10), created_by=self.admin)

    def test_serie_vide_leve_valueerror(self):
        from datetime import date
        with self.assertRaises(ValueError):
            creer_equipement_depuis_vente_pos(
                company=self.company, produit=self.onduleur,
                client=self.client_obj, numero_serie='',
                date_vente=date(2026, 1, 10), created_by=self.admin)
