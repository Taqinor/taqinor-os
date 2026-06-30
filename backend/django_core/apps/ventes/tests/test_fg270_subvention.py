"""FG270 — tests de l'éligibilité & du suivi des subventions/incitations.

Couvre : création (company forcée depuis le devis), isolation société, filtres
programme/statut, suivi des montants et des pièces (JSON).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg270_subvention -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis, SubventionDossier
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_devis(company, user, ref='DEV-FG270-1'):
    client = Client.objects.create(
        company=company, nom='Alaoui', prenom='Yassine',
        email=f'y_{company.slug}@example.com', telephone='+212622222222')
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='brouillon', created_by=user)


class SubventionDossierApiTest(TestCase):
    def setUp(self):
        self.company = make_company('subv-acme')
        self.other = make_company('subv-other')
        self.user = make_user(self.company, 'subv_user')
        self.devis = make_devis(self.company, self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/subventions/'

    def test_create_forces_company_and_tracks_montant(self):
        resp = self.api.post(self.url, {
            'devis': self.devis.id, 'programme': 'iresen',
            'statut': 'eligible', 'montant_demande': '25000.00',
            'pieces': [{'code': 'rc', 'label': 'RC', 'fourni': False}],
            'company': self.other.id,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        subv = SubventionDossier.objects.get(id=resp.data['id'])
        self.assertEqual(subv.company_id, self.company.id)
        self.assertEqual(subv.montant_demande, Decimal('25000.00'))
        self.assertEqual(len(subv.pieces), 1)

    def test_devis_of_other_company_refused(self):
        other_user = make_user(self.other, 'subv_o')
        other_devis = make_devis(self.other, other_user, ref='DEV-OTHER-SUB')
        resp = self.api.post(self.url, {
            'devis': other_devis.id, 'programme': 'masen',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_filter_by_programme_and_statut(self):
        SubventionDossier.objects.create(
            company=self.company, devis=self.devis, programme='masen',
            statut='accorde')
        SubventionDossier.objects.create(
            company=self.company, devis=self.devis, programme='tatwir',
            statut='depose')
        resp = self.api.get(self.url, {'programme': 'masen'})
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['programme'], 'masen')

    def test_list_scoped_to_company(self):
        SubventionDossier.objects.create(
            company=self.company, devis=self.devis, programme='iresen')
        other_user = make_user(self.other, 'subv_o2')
        other_devis = make_devis(self.other, other_user, ref='DEV-OTHER-SUB2')
        SubventionDossier.objects.create(
            company=self.other, devis=other_devis, programme='iresen')
        resp = self.api.get(self.url)
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        for r in rows:
            self.assertEqual(
                SubventionDossier.objects.get(id=r['id']).company_id,
                self.company.id)
