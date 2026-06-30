"""
FG307 — Attestations & assurances obligatoires des sous-traitants chantier.

Couvre :
  * création via l'API avec société + ``created_by`` posés CÔTÉ SERVEUR ;
  * l'injection de ``company`` est ignorée ;
  * un ``sous_traitant`` d'une autre société est rejeté ;
  * `est_valide` (pièce expirée vs valide vs sans échéance) ;
  * l'action `affectabilite` : bloque si une pièce obligatoire est expirée,
    si le sous-traitant est archivé ; passe sinon ;
  * le scope société et la barrière de rôle (écriture responsable/admin).

Run :
    python manage.py test apps.installations.tests_fg307_attestation_soustraitant -v2
"""
import itertools
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import AttestationSousTraitant, SousTraitant

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg307-co-{n}', defaults={'nom': nom or f'FG307 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg307-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_sous_traitant(company, raison='Elec Pro', actif=True):
    return SousTraitant.objects.create(
        company=company, raison_sociale=raison, metier='electricite',
        actif=actif)


class TestAttestationCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def test_create_server_side_company(self):
        r = self.api.post(f'{BASE}/attestations-sous-traitant/', {
            'sous_traitant': self.st.id,
            'type_piece': 'cnss',
            'date_expiration': (date.today() + timedelta(days=30)).isoformat(),
        })
        self.assertEqual(r.status_code, 201, r.data)
        att = AttestationSousTraitant.objects.get(id=r.data['id'])
        self.assertEqual(att.company_id, self.company.id)
        self.assertEqual(att.created_by_id, self.user.id)
        self.assertTrue(r.data['est_valide'])

    def test_injected_company_ignored(self):
        autre = make_company()
        r = self.api.post(f'{BASE}/attestations-sous-traitant/', {
            'company': autre.id,
            'sous_traitant': self.st.id,
            'type_piece': 'agrement',
        })
        self.assertEqual(r.status_code, 201, r.data)
        att = AttestationSousTraitant.objects.get(id=r.data['id'])
        self.assertEqual(att.company_id, self.company.id)

    def test_foreign_sous_traitant_rejected(self):
        autre = make_company()
        st_o = make_sous_traitant(autre)
        r = self.api.post(f'{BASE}/attestations-sous-traitant/', {
            'sous_traitant': st_o.id, 'type_piece': 'cnss',
        })
        self.assertEqual(r.status_code, 400, r.data)


class TestEstValide(TestCase):
    def setUp(self):
        self.company = make_company()
        self.st = make_sous_traitant(self.company)

    def test_expired_invalid(self):
        att = AttestationSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st, type_piece='cnss',
            date_expiration=date.today() - timedelta(days=1))
        self.assertFalse(att.est_valide())

    def test_future_valid(self):
        att = AttestationSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st, type_piece='cnss',
            date_expiration=date.today() + timedelta(days=10))
        self.assertTrue(att.est_valide())

    def test_no_expiration_valid(self):
        att = AttestationSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st, type_piece='agrement',
            date_expiration=None)
        self.assertTrue(att.est_valide())


class TestAffectabilite(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def test_blocked_when_obligatory_expired(self):
        AttestationSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st, type_piece='cnss',
            obligatoire=True,
            date_expiration=date.today() - timedelta(days=1))
        r = self.api.get(
            f'{BASE}/attestations-sous-traitant/affectabilite/',
            {'sous_traitant': self.st.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['affectable'])
        self.assertEqual(len(r.data['pieces_expirees']), 1)

    def test_optional_expired_does_not_block(self):
        AttestationSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st, type_piece='autre',
            obligatoire=False,
            date_expiration=date.today() - timedelta(days=1))
        r = self.api.get(
            f'{BASE}/attestations-sous-traitant/affectabilite/',
            {'sous_traitant': self.st.id})
        self.assertTrue(r.data['affectable'])

    def test_archived_blocks(self):
        self.st.actif = False
        self.st.save(update_fields=['actif'])
        r = self.api.get(
            f'{BASE}/attestations-sous-traitant/affectabilite/',
            {'sous_traitant': self.st.id})
        self.assertFalse(r.data['affectable'])

    def test_all_valid_affectable(self):
        AttestationSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st, type_piece='cnss',
            obligatoire=True,
            date_expiration=date.today() + timedelta(days=60))
        r = self.api.get(
            f'{BASE}/attestations-sous-traitant/affectabilite/',
            {'sous_traitant': self.st.id})
        self.assertTrue(r.data['affectable'])

    def test_missing_param(self):
        r = self.api.get(f'{BASE}/attestations-sous-traitant/affectabilite/')
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
        r = api.post(f'{BASE}/attestations-sous-traitant/', {
            'sous_traitant': self.st.id, 'type_piece': 'cnss',
        })
        self.assertEqual(r.status_code, 403, r.data)

    def test_scope_isolation(self):
        other = make_company()
        st_o = make_sous_traitant(other)
        AttestationSousTraitant.objects.create(
            company=other, sous_traitant=st_o, type_piece='cnss')
        AttestationSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st, type_piece='cnss')
        r = self.api.get(f'{BASE}/attestations-sous-traitant/')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)
