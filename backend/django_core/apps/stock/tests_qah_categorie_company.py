"""Régression ERR-QAH-STOCK-CATEGORIE-CREATION-400-COMPANY.

`POST /api/django/stock/categories/` répondait 400
`{"company": ["Ce champ est obligatoire."]}` car `CategorieSerializer` était
en `fields = '__all__'` sans `read_only_fields`, et DRF force `company`
`required=True` (dérivé de `unique_together = [('company', 'nom')]`) —
violant la règle multi-tenant : `company` doit être force-assigné côté
serveur (`perform_create`), jamais accepté du corps de la requête.

Run:
    python manage.py test apps.stock.tests_qah_categorie_company -v 2
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Categorie

User = get_user_model()


def make_company(slug='qah-cat-co', nom='QAH Cat Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def make_admin(company, username='admin_qah_cat'):
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={'company': company, 'role_legacy': 'admin'},
    )
    return user


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class TestCategorieCreationSansCompanyDansLeCorps(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_admin(self.company)
        self.client = auth_client(self.admin)

    def test_creation_sans_company_dans_le_corps_reussit(self):
        """Reproduction EXACTE du QA-explorer : corps sans `company`."""
        r = self.client.post('/api/django/stock/categories/', {
            'nom': 'QAH-TEST',
            'type_equipement': None,
            'ordre': 100,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['nom'], 'QAH-TEST')
        cat = Categorie.objects.get(pk=r.data['id'])
        self.assertEqual(cat.company_id, self.company.id)

    def test_company_du_corps_est_ignore(self):
        """Un `company` étranger dans le corps ne doit JAMAIS être pris en
        compte — la société vient toujours de `request.user.company`
        (perform_create), jamais du corps de la requête."""
        autre_company = make_company(slug='qah-cat-autre-co', nom='Autre Co')
        r = self.client.post('/api/django/stock/categories/', {
            'nom': 'QAH-TEST-2',
            'company': autre_company.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        cat = Categorie.objects.get(pk=r.data['id'])
        self.assertEqual(cat.company_id, self.company.id)
        self.assertNotEqual(cat.company_id, autre_company.id)

    def test_meme_nom_dans_une_autre_societe_nest_pas_un_doublon(self):
        """Le contrôle d'unicité (company, nom) reste scopé société : deux
        sociétés différentes peuvent chacune avoir une catégorie « Panneaux »
        — ce n'est PAS un doublon."""
        autre_company = make_company(
            slug='qah-cat-autre-co-2', nom='Autre Co 2')
        Categorie.objects.create(company=autre_company, nom='Panneaux')
        r = self.client.post('/api/django/stock/categories/', {
            'nom': 'Panneaux',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)

    def test_meme_nom_dans_la_meme_societe_est_refuse(self):
        Categorie.objects.create(company=self.company, nom='Panneaux')
        r = self.client.post('/api/django/stock/categories/', {
            'nom': 'Panneaux',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('nom', r.data)
