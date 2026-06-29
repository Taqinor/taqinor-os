"""FG254 / DC35 — tests de la bibliothèque de fiches techniques.

Couvre :
  - create force la société depuis le produit, ignore company du corps
  - isolation société : un produit d'une autre société est refusé / invisible
  - unicité (company, produit) — une seule fiche normalisée par produit/société
  - la fiche ne porte que les params normalisés (jamais de prix en sortie)
  - filtres ?produit= et ?type_fiche=
  - retrieve/update/destroy scopés société

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fiche_technique -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.models import FicheTechnique
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_produit(company, nom='Panneau 550W'):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=Decimal('1000'))


class FicheTechniqueModelTest(TestCase):
    def test_unique_per_company_produit(self):
        co = make_company('ft-uniq')
        prod = make_produit(co)
        FicheTechnique.objects.create(
            company=co, produit=prod, type_fiche='panneau', pmax_w=550)
        with self.assertRaises(IntegrityError):
            FicheTechnique.objects.create(
                company=co, produit=prod, type_fiche='panneau', pmax_w=560)


class FicheTechniqueApiTest(TestCase):
    def setUp(self):
        self.company = make_company('ft-acme')
        self.other = make_company('ft-other')
        self.user = make_user(self.company, 'ft_user')
        self.prod = make_produit(self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/fiches-techniques/'

    def test_create_forces_company_from_produit(self):
        resp = self.api.post(self.url, {
            'produit': self.prod.id,
            'type_fiche': 'panneau',
            'pmax_w': '550.00', 'voc_v': '49.50', 'isc_a': '13.80',
            'coef_temp_voc': '-0.2700',
            # tentative d'injecter une autre société : doit être ignorée
            'company': self.other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        fiche = FicheTechnique.objects.get(id=resp.data['id'])
        self.assertEqual(fiche.company_id, self.company.id)
        self.assertEqual(fiche.created_by_id, self.user.id)

    def test_create_rejects_produit_of_other_company(self):
        other_prod = make_produit(self.other, nom='Onduleur autre')
        resp = self.api.post(self.url, {
            'produit': other_prod.id, 'type_fiche': 'onduleur',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_list_is_company_scoped(self):
        FicheTechnique.objects.create(
            company=self.company, produit=self.prod, pmax_w=550)
        other_prod = make_produit(self.other, nom='X')
        FicheTechnique.objects.create(
            company=self.other, produit=other_prod, pmax_w=400)
        resp = self.api.get(self.url)
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        ids = {r['produit'] for r in results}
        self.assertIn(self.prod.id, ids)
        self.assertNotIn(other_prod.id, ids)

    def test_filter_by_type(self):
        prod2 = make_produit(self.company, nom='Onduleur 10kW')
        FicheTechnique.objects.create(
            company=self.company, produit=self.prod, type_fiche='panneau')
        FicheTechnique.objects.create(
            company=self.company, produit=prod2, type_fiche='onduleur')
        resp = self.api.get(self.url + '?type_fiche=onduleur')
        results = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['type_fiche'], 'onduleur')

    def test_response_carries_no_price(self):
        FicheTechnique.objects.create(
            company=self.company, produit=self.prod, pmax_w=550)
        resp = self.api.get(self.url)
        body = str(resp.data)
        self.assertNotIn('prix', body.lower())

    def test_retrieve_other_company_404(self):
        other_prod = make_produit(self.other, nom='X')
        fiche = FicheTechnique.objects.create(
            company=self.other, produit=other_prod, pmax_w=400)
        resp = self.api.get(f'{self.url}{fiche.id}/')
        self.assertEqual(resp.status_code, 404)
