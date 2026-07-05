"""ZMFG2 — Catégories d'équipement (Configuration > Equipment Categories) +
regroupement/filtre du parc.

Couvre :
  * CRUD catégorie scopé société ;
  * équipement filtrable/groupable par catégorie (`?categorie=`) ;
  * compteur d'équipements par catégorie exact ;
  * isolation multi-tenant.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zmfg2 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.installations.models import Installation
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.sav.models import CategorieEquipement, Equipement

User = get_user_model()


def make_company(slug='sav-zmfg2', nom='Sav Co ZMFG2'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZMFG2CategorieEquipementTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zmfg2_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.other_company = make_company(
            slug='sav-zmfg2-other', nom='Sav Co ZMFG2 Other')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X', sku='OND-ZMFG2',
            marque='Huawei', prix_vente=1000)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZMFG2',
            email='zmfg2-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZMFG2', client=self.client_obj)

    def test_crud_scoped_to_company(self):
        r = self.api.post('/api/django/sav/categories-equipement/', {
            'nom': 'Onduleurs', 'commentaire': 'Parc onduleurs',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        cat = CategorieEquipement.objects.get(pk=r.data['id'])
        self.assertEqual(cat.company_id, self.company.id)

    def test_equipement_filtrable_par_categorie(self):
        cat = CategorieEquipement.objects.create(
            company=self.company, nom='Onduleurs')
        eq_avec = Equipement.objects.create(
            company=self.company, produit=self.produit, categorie=cat,
            installation=self.inst)
        Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst)

        r = self.api.get('/api/django/sav/equipements/', {'categorie': cat.id})
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        ids = [row['id'] for row in rows]
        self.assertEqual(ids, [eq_avec.id])

    def test_compteur_equipements_par_categorie_exact(self):
        cat = CategorieEquipement.objects.create(
            company=self.company, nom='Pompes')
        Equipement.objects.create(
            company=self.company, produit=self.produit, categorie=cat,
            installation=self.inst)
        Equipement.objects.create(
            company=self.company, produit=self.produit, categorie=cat,
            installation=self.inst)

        r = self.api.get(f'/api/django/sav/categories-equipement/{cat.id}/')
        self.assertEqual(r.data['nb_equipements'], 2)

    def test_equipement_categorie_autre_societe_rejetee(self):
        cat_etrangere = CategorieEquipement.objects.create(
            company=self.other_company, nom='Étrangère')
        r = self.api.post('/api/django/sav/equipements/', {
            'produit': self.produit.id, 'installation': self.inst.id,
            'categorie': cat_etrangere.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_company_isolation(self):
        CategorieEquipement.objects.create(
            company=self.other_company, nom='Batteries étrangères')
        r = self.api.get('/api/django/sav/categories-equipement/')
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        noms = [row['nom'] for row in rows]
        self.assertNotIn('Batteries étrangères', noms)
