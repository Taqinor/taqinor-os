"""XMFG5 — Cout de revient du kit : roll-up + structure + stock potentiel.

Couvre (cote stock — l'ecran kit + le miroir installations.Kit ne sont pas
dans ce lot) :
  * `structure_kit` rend la nomenclature indentee avec quantite, disponibilite
    et cout unitaire/total roll-up ;
  * `disponibilite_potentielle` = min(dispo composant / quantite requise) ;
  * marge = somme prix_vente composants - cout roll-up ;
  * l'endpoint `kits/{id}/structure/` retire cout/marge pour un role sans
    acces responsable/admin (jamais client-facing) mais garde disponibilite ;
  * un role responsable/admin voit le cout complet.

Run:
    python manage.py test apps.stock.test_xmfg5_kit_structure -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import KitComposant, KitProduit, Produit
from apps.stock.services import structure_kit

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, role_legacy='responsable', permissions=None):
    # Un Role fin n'est créé QUE si des permissions explicites sont passées
    # (comme test_xpur1_conformite_fournisseur.py) : sinon `is_responsable`
    # retomberait sur `_role_grants_write([])` → False, cassant le repli
    # historique par `role_legacy` (ERR4, authentication/models.py).
    role = None
    if permissions is not None:
        role = Role.objects.create(
            company=company, nom=f'r-{username}', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xmfg5Base(TestCase):
    def setUp(self):
        self.company = _company('xmfg5-co')
        self.responsable = _user(self.company, 'xmfg5-resp')
        self.api_resp = _api(self.responsable)
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-XMFG5',
            prix_vente=Decimal('900'), prix_achat=Decimal('600'),
            quantite_stock=20)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND-XMFG5',
            prix_vente=Decimal('5000'), prix_achat=Decimal('3500'),
            quantite_stock=3)
        self.kit = KitProduit.objects.create(
            company=self.company, nom='Kit résidentiel 5kWc', sku='KIT-XMFG5')
        KitComposant.objects.create(
            kit=self.kit, produit=self.panneau, quantite=Decimal('10'))
        KitComposant.objects.create(
            kit=self.kit, produit=self.onduleur, quantite=Decimal('1'))


class StructureKitServiceTests(Xmfg5Base):
    def test_structure_roll_up(self):
        data = structure_kit(self.kit)
        self.assertEqual(len(data['composants']), 2)
        # 10 panneaux @ 600 + 1 onduleur @ 3500 = 6000 + 3500 = 9500
        self.assertEqual(data['cout_total_roll_up'], Decimal('9500.00'))
        # 10 panneaux @ 900 + 1 onduleur @ 5000 = 9000 + 5000 = 14000
        self.assertEqual(data['prix_vente_total'], Decimal('14000.00'))
        self.assertEqual(data['marge'], Decimal('4500.00'))

    def test_disponibilite_potentielle_min_ratio(self):
        # 20 panneaux dispo / 10 requis = 2 kits ; 3 onduleurs / 1 requis = 3.
        # -> min(2, 3) = 2 kits assemblables.
        data = structure_kit(self.kit)
        self.assertEqual(data['disponibilite_potentielle'], 2)

    def test_disponibilite_potentielle_zero_si_composant_manquant(self):
        self.onduleur.quantite_stock = 0
        self.onduleur.save(update_fields=['quantite_stock'])
        data = structure_kit(self.kit)
        self.assertEqual(data['disponibilite_potentielle'], 0)


class StructureKitEndpointTests(Xmfg5Base):
    def test_endpoint_responsable_voit_le_cout(self):
        resp = self.api_resp.get(
            f'/api/django/stock/kits/{self.kit.pk}/structure/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['cout_total_roll_up'], '9500.00')
        self.assertIn('marge', data)

    def test_endpoint_role_limite_ne_voit_pas_le_cout(self):
        limite = _user(
            self.company, 'xmfg5-limite', role_legacy='commercial',
            permissions=['stock_voir'])
        api = _api(limite)
        resp = api.get(f'/api/django/stock/kits/{self.kit.pk}/structure/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertNotIn('cout_total_roll_up', data)
        self.assertNotIn('marge', data)
        for ligne in data['composants']:
            self.assertNotIn('cout_unitaire', ligne)
            self.assertNotIn('cout_total', ligne)
        # La disponibilité reste visible pour tous les rôles.
        self.assertIn('quantite_disponible', data['composants'][0])
        self.assertEqual(data['disponibilite_potentielle'], 2)
