"""FG274 — tests du protocole d'essais de mise en service IEC 62446.

Couvre : calcul pur du résultat global, création (company forcée), résultat
dérivé serveur (jamais du corps), isolation société, filtre, ne change aucun
statut de devis.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg274_commissioning -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis, CommissioningTest
from apps.ventes.commissioning import compute_commissioning_result
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_devis(company, user, ref='DEV-FG274-1'):
    client = Client.objects.create(
        company=company, nom='Berrada', prenom='Salma',
        email=f's_{ref}@example.com', telephone='+212666666666')
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='accepte', created_by=user)


class ComputeResultTest(SimpleTestCase):
    def test_any_false_is_non_conforme(self):
        self.assertEqual(
            compute_commissioning_result(
                isolement_ok=True, polarite_ok=False),
            'non_conforme')

    def test_all_true_no_defect_is_conforme(self):
        self.assertEqual(
            compute_commissioning_result(
                isolement_ok=True, polarite_ok=True,
                continuite_terre_ok=True, controle_onduleur_ok=True),
            'conforme')

    def test_defective_iv_forces_non_conforme(self):
        self.assertEqual(
            compute_commissioning_result(
                isolement_ok=True, polarite_ok=True,
                continuite_terre_ok=True, controle_onduleur_ok=True,
                has_defective_iv=True),
            'non_conforme')

    def test_partial_is_en_cours(self):
        self.assertEqual(
            compute_commissioning_result(isolement_ok=True),
            'en_cours')


class CommissioningApiTest(TestCase):
    def setUp(self):
        self.company = make_company('mes-acme')
        self.other = make_company('mes-other')
        self.user = make_user(self.company, 'mes_user')
        self.devis = make_devis(self.company, self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/recettes-mes/'

    def test_result_derived_server_side(self):
        # Le corps tente d'imposer resultat=conforme ; serveur l'ignore et
        # dérive non_conforme car polarite_ok=False.
        resp = self.api.post(self.url, {
            'devis': self.devis.id, 'isolement_ok': True,
            'polarite_ok': False, 'continuite_terre_ok': True,
            'controle_onduleur_ok': True, 'isolement_mohm': '5.50',
            'resultat': 'conforme',  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        rec = CommissioningTest.objects.get(id=resp.data['id'])
        self.assertEqual(rec.resultat, 'non_conforme')
        self.assertEqual(rec.company_id, self.company.id)
        # Le statut du devis ne change pas (RULE #4).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'accepte')

    def test_all_pass_is_conforme(self):
        resp = self.api.post(self.url, {
            'devis': self.devis.id, 'isolement_ok': True,
            'polarite_ok': True, 'continuite_terre_ok': True,
            'controle_onduleur_ok': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['resultat'], 'conforme')

    def test_devis_of_other_company_refused(self):
        other_user = make_user(self.other, 'mes_o')
        other_devis = make_devis(self.other, other_user, ref='DEV-OTHER-MES')
        resp = self.api.post(self.url, {
            'devis': other_devis.id, 'isolement_ok': True,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_list_scoped_and_filter_resultat(self):
        CommissioningTest.objects.create(
            company=self.company, devis=self.devis, resultat='conforme')
        CommissioningTest.objects.create(
            company=self.company, devis=self.devis, resultat='non_conforme')
        resp = self.api.get(self.url, {'resultat': 'conforme'})
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['resultat'], 'conforme')
