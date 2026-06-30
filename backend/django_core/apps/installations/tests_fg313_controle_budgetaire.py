"""
FG313 — Contrôle budgétaire à la commande.

Endpoint consultatif (lecture, aucune écriture) qui répond, avant de valider un
BCF, si un montant d'achat tient dans le budget RESTANT du programme.

Couvre :
  * ok quand le montant tient dans le reste de la catégorie ;
  * dépassement quand il l'excède ;
  * non_configure quand aucun budget n'existe pour le programme (ou sans
    `projet`) — on ne bloque pas faute de référence ;
  * le scope société (le budget d'une autre société n'est pas lu) ;
  * la validation des paramètres (montant négatif / catégorie inconnue).

Run :
    python manage.py test apps.installations.tests_fg313_controle_budgetaire -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Projet, BudgetProjet

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg313-co-{n}', defaults={'nom': nom or f'FG313 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg313-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_projet_budget(company, materiel=100000):
    n = next(_seq)
    projet = Projet.objects.create(
        company=company, reference=f'PR-{n}', nom=f'Programme {n}')
    BudgetProjet.objects.create(
        company=company, projet=projet, budget_materiel=materiel)
    return projet


class TestControleBudgetaire(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.projet = make_projet_budget(self.company, materiel=100000)

    def test_within_budget_ok(self):
        r = self.api.get(f'{BASE}/controle-budgetaire/', {
            'montant': '30000', 'projet': self.projet.id,
            'categorie': 'materiel',
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['controle'], 'ok')
        self.assertFalse(r.data['depasse'])
        self.assertEqual(r.data['reste_categorie'], 100000.0)

    def test_over_budget_depassement(self):
        r = self.api.get(f'{BASE}/controle-budgetaire/', {
            'montant': '150000', 'projet': self.projet.id,
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['controle'], 'depassement')
        self.assertTrue(r.data['depasse'])

    def test_no_projet_non_configure(self):
        r = self.api.get(f'{BASE}/controle-budgetaire/', {'montant': '5000'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['controle'], 'non_configure')
        self.assertFalse(r.data['depasse'])

    def test_projet_without_budget_non_configure(self):
        n = next(_seq)
        projet = Projet.objects.create(
            company=self.company, reference=f'PR-NB-{n}', nom='Sans budget')
        r = self.api.get(f'{BASE}/controle-budgetaire/', {
            'montant': '5000', 'projet': projet.id,
        })
        self.assertEqual(r.data['controle'], 'non_configure')

    def test_negative_montant_rejected(self):
        r = self.api.get(f'{BASE}/controle-budgetaire/', {
            'montant': '-5', 'projet': self.projet.id,
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_invalid_categorie_rejected(self):
        r = self.api.get(f'{BASE}/controle-budgetaire/', {
            'montant': '5', 'projet': self.projet.id, 'categorie': 'inconnu',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_other_company_budget_not_seen(self):
        other = make_company()
        projet_o = make_projet_budget(other, materiel=999999)
        # Vu depuis NOTRE société, le programme de l'autre société n'a pas de
        # budget scopé → non_configure (pas de fuite cross-tenant).
        r = self.api.get(f'{BASE}/controle-budgetaire/', {
            'montant': '5000', 'projet': projet_o.id,
        })
        self.assertEqual(r.data['controle'], 'non_configure')
