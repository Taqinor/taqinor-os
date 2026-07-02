"""
FG308 — Évaluation de performance des sous-traitants chantier.

Couvre :
  * création via l'API avec société + ``evalue_par`` posés CÔTÉ SERVEUR ;
  * l'injection de ``company`` est ignorée ;
  * un ``sous_traitant`` d'une autre société est rejeté ;
  * la validation des notes (1–5) ;
  * `note_globale` (moyenne des trois axes) ;
  * l'action `scorecard` (moyenne cumulée par axe) ;
  * le scope société et la barrière de rôle (écriture responsable/admin).

Run :
    python manage.py test apps.installations.tests_fg308_evaluation_soustraitant -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import EvaluationSousTraitant
from apps.stock.services import create_sous_traitant

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg308-co-{n}', defaults={'nom': nom or f'FG308 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg308-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_sous_traitant(company, raison='BTP Sud'):
    # DC34 — un sous-traitant est un stock.Fournisseur(type='service').
    return create_sous_traitant(
        company=company, nom=raison, metier='genie_civil')


class TestEvaluationCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def test_create_server_side(self):
        r = self.api.post(f'{BASE}/evaluations-sous-traitant/', {
            'sous_traitant': self.st.id,
            'note_qualite': 4, 'note_delai': 3, 'note_securite': 5,
        })
        self.assertEqual(r.status_code, 201, r.data)
        ev = EvaluationSousTraitant.objects.get(id=r.data['id'])
        self.assertEqual(ev.company_id, self.company.id)
        self.assertEqual(ev.evalue_par_id, self.user.id)
        # note_globale = (4+3+5)/3 = 4.0
        self.assertEqual(float(r.data['note_globale']), 4.0)

    def test_injected_company_ignored(self):
        autre = make_company()
        r = self.api.post(f'{BASE}/evaluations-sous-traitant/', {
            'company': autre.id, 'sous_traitant': self.st.id,
            'note_qualite': 5, 'note_delai': 5, 'note_securite': 5,
        })
        self.assertEqual(r.status_code, 201, r.data)
        ev = EvaluationSousTraitant.objects.get(id=r.data['id'])
        self.assertEqual(ev.company_id, self.company.id)

    def test_note_out_of_range_rejected(self):
        r = self.api.post(f'{BASE}/evaluations-sous-traitant/', {
            'sous_traitant': self.st.id,
            'note_qualite': 6, 'note_delai': 3, 'note_securite': 5,
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_foreign_sous_traitant_rejected(self):
        autre = make_company()
        st_o = make_sous_traitant(autre)
        r = self.api.post(f'{BASE}/evaluations-sous-traitant/', {
            'sous_traitant': st_o.id,
            'note_qualite': 4, 'note_delai': 4, 'note_securite': 4,
        })
        self.assertEqual(r.status_code, 400, r.data)


class TestScorecard(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def test_empty_scorecard(self):
        r = self.api.get(
            f'{BASE}/evaluations-sous-traitant/scorecard/',
            {'sous_traitant': self.st.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['nb_evaluations'], 0)
        self.assertIsNone(r.data['note_globale'])

    def test_cumulative_averages(self):
        EvaluationSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st,
            note_qualite=4, note_delai=2, note_securite=4)
        EvaluationSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st,
            note_qualite=2, note_delai=4, note_securite=4)
        r = self.api.get(
            f'{BASE}/evaluations-sous-traitant/scorecard/',
            {'sous_traitant': self.st.id})
        self.assertEqual(r.data['nb_evaluations'], 2)
        self.assertEqual(float(r.data['note_qualite']), 3.0)
        self.assertEqual(float(r.data['note_delai']), 3.0)
        self.assertEqual(float(r.data['note_securite']), 4.0)

    def test_scorecard_missing_param(self):
        r = self.api.get(f'{BASE}/evaluations-sous-traitant/scorecard/')
        self.assertEqual(r.status_code, 400, r.data)


class TestScopeAndRole(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def test_write_requires_role(self):
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.post(f'{BASE}/evaluations-sous-traitant/', {
            'sous_traitant': self.st.id,
            'note_qualite': 4, 'note_delai': 4, 'note_securite': 4,
        })
        self.assertEqual(r.status_code, 403, r.data)

    def test_scope_isolation(self):
        other = make_company()
        st_o = make_sous_traitant(other)
        EvaluationSousTraitant.objects.create(
            company=other, sous_traitant=st_o,
            note_qualite=1, note_delai=1, note_securite=1)
        EvaluationSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st,
            note_qualite=5, note_delai=5, note_securite=5)
        r = self.api.get(f'{BASE}/evaluations-sous-traitant/')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)
