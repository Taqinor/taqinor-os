"""Tests du budget projet (PROJ21 — lignes par catégorie).

Couvre : création d'un budget + de lignes (société posée côté serveur, jamais
du corps) ; le sélecteur ``budget_total`` (somme + ventilation par catégorie,
budget vide → 0, pas de division-par-zéro) ; l'action ``total`` du ViewSet ;
le scoping multi-société (isolation des listes + filtres ``?projet=`` /
``?budget=`` / ``?categorie=``) ; les garde-fous même-société (lier un budget au
projet d'une AUTRE société → 400 ; lier une ligne au budget d'une AUTRE société
→ 400) ; le cross-tenant sur l'action ``total`` (404) ; et l'accès réservé au
palier Administrateur/Responsable (rôle ``normal`` → 403).

Le ``categorie``/``statut`` est PROPRE à ce module et ne réutilise aucune clé de
``STAGES.py`` (règle #2). Le budget est INTERNE — jamais exposé au client final.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import BudgetProjet, LigneBudgetProjet, Projet

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class BudgetTotalSelectorTests(TestCase):
    """Sélecteur ``budget_total`` — somme + ventilation par catégorie."""

    def setUp(self):
        self.co = make_company('gp-bud-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-BUD', nom='Projet budget')
        self.budget = BudgetProjet.objects.create(
            company=self.co, projet=self.projet, libelle='Budget initial')

    def _ligne(self, categorie, montant):
        return LigneBudgetProjet.objects.create(
            company=self.co, budget=self.budget, categorie=categorie,
            libelle=f'{categorie} test', montant_prevu=Decimal(montant))

    def test_empty_budget_total_is_zero(self):
        agg = selectors.budget_total(self.budget)
        self.assertEqual(agg['total'], Decimal('0'))
        self.assertEqual(agg['nb_lignes'], 0)
        # toutes les catégories canoniques présentes à 0.
        self.assertEqual(set(agg['par_categorie'].keys()), {
            'materiel', 'main_oeuvre', 'sous_traitance', 'divers'})
        self.assertTrue(
            all(v == Decimal('0') for v in agg['par_categorie'].values()))

    def test_per_category_totals(self):
        self._ligne('materiel', '1000.00')
        self._ligne('materiel', '500.50')
        self._ligne('main_oeuvre', '300.00')
        self._ligne('sous_traitance', '200.00')
        self._ligne('divers', '99.50')
        agg = selectors.budget_total(self.budget)
        self.assertEqual(agg['total'], Decimal('2100.00'))
        self.assertEqual(agg['nb_lignes'], 5)
        self.assertEqual(agg['par_categorie']['materiel'], Decimal('1500.50'))
        self.assertEqual(agg['par_categorie']['main_oeuvre'], Decimal('300.00'))
        self.assertEqual(
            agg['par_categorie']['sous_traitance'], Decimal('200.00'))
        self.assertEqual(agg['par_categorie']['divers'], Decimal('99.50'))

    def test_total_scoped_to_budget(self):
        # une ligne d'un AUTRE budget ne compte pas dans le total.
        self._ligne('materiel', '1000.00')
        autre = BudgetProjet.objects.create(
            company=self.co, projet=self.projet, libelle='Autre', version=2)
        LigneBudgetProjet.objects.create(
            company=self.co, budget=autre, categorie='materiel',
            libelle='autre ligne', montant_prevu=Decimal('9999.00'))
        agg = selectors.budget_total(self.budget)
        self.assertEqual(agg['total'], Decimal('1000.00'))
        self.assertEqual(agg['nb_lignes'], 1)


class BudgetProjetApiTests(TestCase):
    BASE = '/api/django/gestion-projet/budgets/'

    def setUp(self):
        self.co_a = make_company('gp-bud-a', 'A')
        self.co_b = make_company('gp-bud-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-bud-a')
        self.user_b = make_user(self.co_b, 'gp-bud-b')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-A', nom='Projet A')
        self.projet_b = Projet.objects.create(
            company=self.co_b, code='P-B', nom='Projet B')

    def _payload(self, projet):
        return {
            'projet': projet.id,
            'libelle': 'Budget travaux',
            'version': 1,
            'devise': 'MAD',
        }

    def test_create_forces_company_server_side(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = BudgetProjet.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.projet, self.projet_a)

    def test_create_ignores_company_from_body(self):
        payload = self._payload(self.projet_a)
        payload['company'] = self.co_b.id
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = BudgetProjet.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_create_rejects_cross_tenant_projet(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('projet', resp.data)
        self.assertFalse(
            BudgetProjet.objects.filter(projet=self.projet_b).exists())

    def test_list_isolation(self):
        BudgetProjet.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='A')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_list_filter_by_projet(self):
        BudgetProjet.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='A1')
        other = Projet.objects.create(
            company=self.co_a, code='P-A2', nom='Projet A2')
        BudgetProjet.objects.create(
            company=self.co_a, projet=other, libelle='A2')
        resp = auth(self.user_a).get(self.BASE + '?projet=%d' % self.projet_a.id)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertTrue(all(r['projet'] == self.projet_a.id for r in data))

    def test_total_action(self):
        budget = BudgetProjet.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='B')
        LigneBudgetProjet.objects.create(
            company=self.co_a, budget=budget, categorie='materiel',
            libelle='panneaux', montant_prevu=Decimal('1200.00'))
        LigneBudgetProjet.objects.create(
            company=self.co_a, budget=budget, categorie='main_oeuvre',
            libelle='pose', montant_prevu=Decimal('800.00'))
        resp = auth(self.user_a).get(f'{self.BASE}{budget.id}/total/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], '2000.00')
        self.assertEqual(resp.data['nb_lignes'], 2)
        self.assertEqual(resp.data['par_categorie']['materiel'], '1200.00')
        self.assertEqual(resp.data['par_categorie']['main_oeuvre'], '800.00')

    def test_total_action_cross_tenant_404(self):
        budget = BudgetProjet.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='B')
        resp = auth(self.user_b).get(f'{self.BASE}{budget.id}/total/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'gp-bud-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class LigneBudgetProjetApiTests(TestCase):
    BASE = '/api/django/gestion-projet/lignes-budget/'

    def setUp(self):
        self.co_a = make_company('gp-lig-a', 'A')
        self.co_b = make_company('gp-lig-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-lig-a')
        self.user_b = make_user(self.co_b, 'gp-lig-b')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-LA', nom='Projet LA')
        self.projet_b = Projet.objects.create(
            company=self.co_b, code='P-LB', nom='Projet LB')
        self.budget_a = BudgetProjet.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='Budget A')
        self.budget_b = BudgetProjet.objects.create(
            company=self.co_b, projet=self.projet_b, libelle='Budget B')

    def _payload(self, budget, categorie='materiel'):
        return {
            'budget': budget.id,
            'categorie': categorie,
            'libelle': 'Onduleur 5kW',
            'quantite': '2.00',
            'pu': '600.00',
            'montant_prevu': '1200.00',
        }

    def test_create_forces_company_server_side(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.budget_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = LigneBudgetProjet.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.budget, self.budget_a)
        self.assertEqual(obj.categorie, 'materiel')
        self.assertEqual(obj.montant_prevu, Decimal('1200.00'))

    def test_create_persists_optional_quantite_pu(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.budget_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = LigneBudgetProjet.objects.get(id=resp.data['id'])
        self.assertEqual(obj.quantite, Decimal('2.00'))
        self.assertEqual(obj.pu, Decimal('600.00'))

    def test_create_without_optional_quantite_pu(self):
        payload = {
            'budget': self.budget_a.id,
            'categorie': 'divers',
            'libelle': 'Imprévus',
            'montant_prevu': '300.00',
        }
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = LigneBudgetProjet.objects.get(id=resp.data['id'])
        self.assertIsNone(obj.quantite)
        self.assertIsNone(obj.pu)
        self.assertEqual(obj.categorie, 'divers')

    def test_create_rejects_cross_tenant_budget(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.budget_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('budget', resp.data)
        self.assertFalse(
            LigneBudgetProjet.objects.filter(budget=self.budget_b).exists())

    def test_list_isolation(self):
        LigneBudgetProjet.objects.create(
            company=self.co_a, budget=self.budget_a, categorie='materiel',
            libelle='x', montant_prevu=Decimal('100.00'))
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_list_filter_by_budget(self):
        LigneBudgetProjet.objects.create(
            company=self.co_a, budget=self.budget_a, categorie='materiel',
            libelle='ligne1', montant_prevu=Decimal('100.00'))
        autre = BudgetProjet.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='Autre', version=2)
        LigneBudgetProjet.objects.create(
            company=self.co_a, budget=autre, categorie='materiel',
            libelle='ligne2', montant_prevu=Decimal('200.00'))
        resp = auth(self.user_a).get(
            self.BASE + '?budget=%d' % self.budget_a.id)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertTrue(all(r['budget'] == self.budget_a.id for r in data))

    def test_list_filter_by_categorie(self):
        LigneBudgetProjet.objects.create(
            company=self.co_a, budget=self.budget_a, categorie='materiel',
            libelle='mat', montant_prevu=Decimal('100.00'))
        LigneBudgetProjet.objects.create(
            company=self.co_a, budget=self.budget_a, categorie='main_oeuvre',
            libelle='mo', montant_prevu=Decimal('200.00'))
        resp = auth(self.user_a).get(self.BASE + '?categorie=main_oeuvre')
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['categorie'], 'main_oeuvre')

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'gp-lig-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
