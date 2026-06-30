"""FG271 — tests du workflow de régularisation Article 33 / 82-21.

Couvre : création (company forcée depuis le devis), génération de déclaration
(avance le statut vers declaration_generee, jamais un statut DEVIS), isolation
société, filtre statut.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg271_regularisation -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis, Regularisation8221
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_devis(company, user, ref='DEV-FG271-1'):
    client = Client.objects.create(
        company=company, nom='Tahiri', prenom='Khalid',
        email=f'k_{company.slug}@example.com', telephone='+212633333333')
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='accepte', created_by=user)


class Regularisation8221ApiTest(TestCase):
    def setUp(self):
        self.company = make_company('reg33-acme')
        self.other = make_company('reg33-other')
        self.user = make_user(self.company, 'reg33_user')
        self.devis = make_devis(self.company, self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/regularisations-8221/'

    def test_create_forces_company(self):
        resp = self.api.post(self.url, {
            'devis': self.devis.id, 'regime_8221': 'declaration_bt',
            'puissance_kwc': '8.50',
            'company': self.other.id,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        regul = Regularisation8221.objects.get(id=resp.data['id'])
        self.assertEqual(regul.company_id, self.company.id)
        self.assertEqual(regul.statut, 'a_regulariser')

    def test_generer_declaration_advances_status_not_devis(self):
        regul = Regularisation8221.objects.create(
            company=self.company, devis=self.devis,
            regime_8221='declaration_bt')
        url = f'{self.url}{regul.id}/generer-declaration/'
        resp = self.api.post(url, {
            'declaration_pdf': 'declarations/reg-1.pdf'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        regul.refresh_from_db()
        self.assertEqual(regul.statut, 'declaration_generee')
        self.assertEqual(regul.declaration_pdf, 'declarations/reg-1.pdf')
        # La chaîne de statut DEVIS reste intacte (couche séparée RULE #4).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'accepte')

    def test_generer_declaration_requires_pdf_path(self):
        regul = Regularisation8221.objects.create(
            company=self.company, devis=self.devis,
            regime_8221='declaration_bt')
        resp = self.api.post(
            f'{self.url}{regul.id}/generer-declaration/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_devis_of_other_company_refused(self):
        other_user = make_user(self.other, 'reg33_o')
        other_devis = make_devis(self.other, other_user, ref='DEV-OTHER-R33')
        resp = self.api.post(self.url, {
            'devis': other_devis.id, 'regime_8221': 'declaration_bt',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_filter_by_statut(self):
        Regularisation8221.objects.create(
            company=self.company, devis=self.devis,
            regime_8221='declaration_bt', statut='regularisee')
        Regularisation8221.objects.create(
            company=self.company, devis=self.devis,
            regime_8221='declaration_bt', statut='a_regulariser')
        resp = self.api.get(self.url, {'statut': 'regularisee'})
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['statut'], 'regularisee')
