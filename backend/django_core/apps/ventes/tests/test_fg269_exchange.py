"""FG269 — tests du journal de la navette opérateur (échanges ONEE).

Couvre : journalisation (envoi/accusé/complément/refus), company forcée depuis
le dossier, isolation société, filtre par type d'échange.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg269_exchange -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis, RegulatoryDossier, DossierExchange
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_dossier(company, user, ref='DEV-FG269-1'):
    client = Client.objects.create(
        company=company, nom='Idrissi', prenom='Nora',
        email=f'n_{company.slug}@example.com', telephone='+212611111111')
    devis = Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='brouillon', created_by=user)
    return RegulatoryDossier.objects.create(
        company=company, devis=devis, regime_8221='accord_raccordement')


class DossierExchangeApiTest(TestCase):
    def setUp(self):
        self.company = make_company('exc-acme')
        self.other = make_company('exc-other')
        self.user = make_user(self.company, 'exc_user')
        self.dossier = make_dossier(self.company, self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/dossiers-echanges/'

    def test_log_exchange_forces_company(self):
        resp = self.api.post(self.url, {
            'dossier': self.dossier.id, 'sens': 'envoi',
            'type_echange': 'depot', 'date_echange': '2026-06-01',
            'objet': 'Dépôt du dossier',
            'company': self.other.id,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        exc = DossierExchange.objects.get(id=resp.data['id'])
        self.assertEqual(exc.company_id, self.company.id)
        self.assertEqual(exc.created_by_id, self.user.id)

    def test_dossier_of_other_company_refused(self):
        other_user = make_user(self.other, 'exc_o')
        other_dossier = make_dossier(self.other, other_user,
                                     ref='DEV-OTHER-EXC')
        resp = self.api.post(self.url, {
            'dossier': other_dossier.id, 'sens': 'recu',
            'type_echange': 'accuse', 'date_echange': '2026-06-02',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_filter_by_type_echange(self):
        DossierExchange.objects.create(
            company=self.company, dossier=self.dossier, sens='recu',
            type_echange='complement', date_echange='2026-06-03')
        DossierExchange.objects.create(
            company=self.company, dossier=self.dossier, sens='recu',
            type_echange='refus', date_echange='2026-06-04')
        resp = self.api.get(self.url, {'type_echange': 'complement'})
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        self.assertTrue(all(r['type_echange'] == 'complement' for r in rows))
        self.assertEqual(len(rows), 1)

    def test_list_scoped_to_company(self):
        DossierExchange.objects.create(
            company=self.company, dossier=self.dossier, sens='envoi',
            type_echange='depot', date_echange='2026-06-01')
        other_user = make_user(self.other, 'exc_o2')
        other_dossier = make_dossier(self.other, other_user,
                                     ref='DEV-OTHER-EXC2')
        DossierExchange.objects.create(
            company=self.other, dossier=other_dossier, sens='envoi',
            type_echange='depot', date_echange='2026-06-01')
        resp = self.api.get(self.url)
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        for r in rows:
            self.assertEqual(
                DossierExchange.objects.get(id=r['id']).company_id,
                self.company.id)
