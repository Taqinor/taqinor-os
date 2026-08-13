"""NTEXT17 — vue par DÉFAUT d'une liste (perso > rôle > société).

``GET core/vues/?cible=crm.lead&defaut=1`` résout LA vue applicable au
demandeur : sa vue perso si elle existe, sinon le défaut de son palier de rôle,
sinon le défaut de la société. Une seule vue défaut par (cible, portée) :
marquer une nouvelle défaut démarque la précédente de la MÊME portée.
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import VuePersonnalisee

User = get_user_model()

URL = '/api/django/core/vues/'
CIBLE = 'crm.lead'

_seq = itertools.count(1)


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT17 Co {next(_seq)}')


def make_user(company, username=None, role='normal'):
    return User.objects.create_user(
        username=username or f'ntext17-u{next(_seq)}', password='x',
        role_legacy=role, company=company)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _vue(company, **kwargs):
    kwargs.setdefault('cible', CIBLE)
    kwargs.setdefault('nom', f'Vue {next(_seq)}')
    kwargs.setdefault('partage', VuePersonnalisee.Partage.SOCIETE)
    return VuePersonnalisee.objects.create(company=company, **kwargs)


class ResolutionVueDefautTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT17 Scope')
        self.autre = make_company('NTEXT17 Autre')
        self.user = make_user(self.company, 'ntext17-commercial')
        self.api = _auth(self.user)

    def test_role_default_is_loaded_when_no_personal_view(self):
        societe = _vue(self.company, nom='Défaut société', est_defaut=True)
        role = _vue(self.company, nom='Mes leads chauds', est_defaut=True,
                    role_tier='normal')
        res = self.api.get(f'{URL}?cible={CIBLE}&defaut=1')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['vue']['id'], role.id)
        self.assertNotEqual(res.data['vue']['id'], societe.id)

    def test_personal_default_wins_over_role_and_company(self):
        _vue(self.company, nom='Défaut société', est_defaut=True)
        _vue(self.company, nom='Défaut rôle', est_defaut=True,
             role_tier='normal')
        perso = _vue(self.company, nom='Ma vue', est_defaut=True,
                     owner=self.user,
                     partage=VuePersonnalisee.Partage.PRIVE)
        res = self.api.get(f'{URL}?cible={CIBLE}&defaut=1')
        self.assertEqual(res.data['vue']['id'], perso.id)

    def test_company_default_when_no_role_default(self):
        societe = _vue(self.company, nom='Défaut société', est_defaut=True)
        res = self.api.get(f'{URL}?cible={CIBLE}&defaut=1')
        self.assertEqual(res.data['vue']['id'], societe.id)

    def test_no_default_returns_null(self):
        _vue(self.company, nom='Vue normale')
        res = self.api.get(f'{URL}?cible={CIBLE}&defaut=1')
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data['vue'])

    def test_other_role_tier_default_is_ignored(self):
        _vue(self.company, nom='Défaut directeur', est_defaut=True,
             role_tier='admin')
        res = self.api.get(f'{URL}?cible={CIBLE}&defaut=1')
        self.assertIsNone(res.data['vue'])

    def test_other_target_default_is_ignored(self):
        _vue(self.company, cible='ventes.devis', nom='Défaut devis',
             est_defaut=True)
        res = self.api.get(f'{URL}?cible={CIBLE}&defaut=1')
        self.assertIsNone(res.data['vue'])

    def test_other_company_default_never_resolved(self):
        _vue(self.autre, nom='Défaut étranger', est_defaut=True)
        res = self.api.get(f'{URL}?cible={CIBLE}&defaut=1')
        self.assertIsNone(res.data['vue'])

    def test_cible_is_required_with_defaut(self):
        res = self.api.get(f'{URL}?defaut=1')
        self.assertEqual(res.status_code, 400)

    def test_list_without_defaut_is_unchanged(self):
        _vue(self.company, nom='A', est_defaut=True)
        _vue(self.company, nom='B')
        res = self.api.get(f'{URL}?cible={CIBLE}')
        self.assertEqual(res.status_code, 200)
        donnees = res.data
        resultats = donnees['results'] if 'results' in donnees else donnees
        self.assertEqual(len(resultats), 2)


class UniciteDuDefautTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT17 Unicité')
        self.user = make_user(self.company, 'ntext17-owner',
                              role='responsable')
        self.api = _auth(self.user)

    def test_new_company_default_unmarks_previous_one(self):
        ancienne = _vue(self.company, nom='Ancienne', est_defaut=True)
        res = self.api.post(URL, {
            'cible': CIBLE, 'nom': 'Nouvelle', 'config': {},
            'partage': 'societe', 'est_defaut': True,
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        ancienne.refresh_from_db()
        self.assertFalse(ancienne.est_defaut)
        self.assertTrue(
            VuePersonnalisee.objects.get(id=res.data['id']).est_defaut)

    def test_role_default_does_not_unmark_company_default(self):
        societe = _vue(self.company, nom='Société', est_defaut=True)
        res = self.api.post(URL, {
            'cible': CIBLE, 'nom': 'Rôle', 'config': {},
            'partage': 'societe', 'est_defaut': True,
            'role_tier': 'responsable',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        societe.refresh_from_db()
        self.assertTrue(societe.est_defaut)

    def test_unknown_role_tier_is_refused(self):
        res = self.api.post(URL, {
            'cible': CIBLE, 'nom': 'Palier inconnu', 'config': {},
            'partage': 'societe', 'est_defaut': True,
            'role_tier': 'super-boss',
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('role_tier', res.data)
