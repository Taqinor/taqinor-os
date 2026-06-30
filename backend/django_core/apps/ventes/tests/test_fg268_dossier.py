"""FG268 — tests du dossier réglementaire + checklist par étape.

Couvre : création (company forcée depuis le devis), isolation société,
génération idempotente de la checklist par régime, filtres, et le fait que la
chaîne de statut DEVIS reste intacte (couche séparée).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg268_dossier -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.models import (
    Devis, RegulatoryDossier, DossierChecklistItem)
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_client_obj(company):
    return Client.objects.create(
        company=company, nom='Bennani', prenom='Sara',
        email=f's_{company.slug}@example.com', telephone='+212600000000')


def make_devis(company, user, ref='DEV-FG268-1'):
    client = make_client_obj(company)
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='brouillon', created_by=user)


class RegulatoryDossierApiTest(TestCase):
    def setUp(self):
        self.company = make_company('reg-acme')
        self.other = make_company('reg-other')
        self.user = make_user(self.company, 'reg_user')
        self.devis = make_devis(self.company, self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/dossiers-reglementaires/'

    def test_create_forces_company_ignores_body(self):
        resp = self.api.post(self.url, {
            'devis': self.devis.id,
            'regime_8221': 'accord_raccordement',
            'company': self.other.id,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        dossier = RegulatoryDossier.objects.get(id=resp.data['id'])
        self.assertEqual(dossier.company_id, self.company.id)
        # Le devis n'a pas changé de statut (couche séparée).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')

    def test_devis_of_other_company_refused(self):
        other_user = make_user(self.other, 'reg_other_user')
        other_devis = make_devis(self.other, other_user, ref='DEV-OTHER-1')
        resp = self.api.post(self.url, {
            'devis': other_devis.id,
            'regime_8221': 'declaration_bt',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_list_scoped_to_company(self):
        RegulatoryDossier.objects.create(
            company=self.company, devis=self.devis,
            regime_8221='declaration_bt')
        other_user = make_user(self.other, 'reg_o2')
        other_devis = make_devis(self.other, other_user, ref='DEV-OTHER-2')
        RegulatoryDossier.objects.create(
            company=self.other, devis=other_devis,
            regime_8221='declaration_bt')
        resp = self.api.get(self.url)
        self.assertEqual(resp.status_code, 200)
        ids = {d['id'] for d in resp.data['results']} if isinstance(
            resp.data, dict) and 'results' in resp.data else {
            d['id'] for d in resp.data}
        for did in ids:
            self.assertEqual(
                RegulatoryDossier.objects.get(id=did).company_id,
                self.company.id)

    def test_generer_checklist_is_idempotent(self):
        dossier = RegulatoryDossier.objects.create(
            company=self.company, devis=self.devis,
            regime_8221='accord_raccordement')
        url = f'{self.url}{dossier.id}/generer-checklist/'
        resp1 = self.api.post(url, {}, format='json')
        self.assertEqual(resp1.status_code, 200, resp1.content)
        created1 = resp1.data['created']
        self.assertGreater(created1, 0)
        # 2e appel : rien de neuf (idempotent).
        resp2 = self.api.post(url, {}, format='json')
        self.assertEqual(resp2.data['created'], 0)
        self.assertEqual(
            DossierChecklistItem.objects.filter(dossier=dossier).count(),
            created1)

    def test_checklist_item_scoped_and_step_filtered(self):
        dossier = RegulatoryDossier.objects.create(
            company=self.company, devis=self.devis,
            regime_8221='declaration_bt')
        item_url = '/api/django/ventes/dossiers-checklist/'
        resp = self.api.post(item_url, {
            'dossier': dossier.id, 'code': 'plan_situation',
            'libelle': 'Plan de situation', 'etape': 'depot',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        item = DossierChecklistItem.objects.get(id=resp.data['id'])
        self.assertEqual(item.company_id, self.company.id)
