"""Tests AUDV09 — révisions, scénarios what-if et auto-imputation (XACC20/22).

Trois services complets et testés unitairement (`test_revisions_budgetaires.py`,
`test_ventilation_analytique.py`), sans AUCUN appelant HTTP :

* `reviser_budget` — un budget se modifiait donc SUR PLACE, écrasant la
  version approuvée : plus aucune comparaison « prévu à l'approbation » vs
  « prévu aujourd'hui » n'était possible, alors que c'est tout l'objet d'une
  révision budgétaire ;
* `creer_scenario_what_if` — chiffrer une hypothèse haute ou basse obligeait à
  toucher au budget officiel ;
* `creer_regle_imputation` — le MOTEUR d'auto-imputation était pourtant déjà
  appelé par `creer_ecriture`, mais aucune règle ne pouvait être créée hors
  admin Django : il tournait à vide, chaque écriture restant à ventiler à la
  main indéfiniment.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Budget, CentreCout, RegleImputation

User = get_user_model()

BUDGETS = '/api/django/compta/budgets/'
REGLES = '/api/django/compta/regles-imputation/'


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RevisionEtScenarioRestTests(TestCase):
    def setUp(self):
        self.co = make_company('audv09-budget', 'AUDV09 Budget')
        services.seed_plan_comptable(self.co)
        self.user = make_user(self.co, 'audv09-budget-user')
        self.api = auth(self.user)
        self.compte = services.get_compte(self.co, '6111')
        self.budget = services.creer_budget(
            self.co, annee=2026, libelle='Budget 2026',
            lignes=[{'compte': self.compte, 'centre_cout': None,
                     'libelle': 'Achats', 'm01': Decimal('1000')}],
            user=self.user)

    def test_revision_fige_la_version_et_copie_les_lignes(self):
        resp = self.api.post(f'{BUDGETS}{self.budget.id}/reviser/', {},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['version'], self.budget.version + 1)
        self.budget.refresh_from_db()
        # La version N reste CONSULTABLE : figée, jamais supprimée.
        self.assertTrue(self.budget.figee)
        nouvelle = Budget.objects.get(id=resp.data['id'])
        self.assertFalse(nouvelle.figee)
        self.assertEqual(nouvelle.budget_parent_id, self.budget.id)
        self.assertEqual(nouvelle.lignes.count(), self.budget.lignes.count())

    def test_reviser_une_version_deja_figee_est_refuse(self):
        self.api.post(f'{BUDGETS}{self.budget.id}/reviser/', {}, format='json')
        second = self.api.post(f'{BUDGETS}{self.budget.id}/reviser/', {},
                               format='json')
        self.assertEqual(second.status_code, 400, second.content)

    def test_scenario_what_if_est_une_copie_independante(self):
        resp = self.api.post(
            f'{BUDGETS}{self.budget.id}/scenario-what-if/',
            {'scenario': Budget.Scenario.OPTIMISTE}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        scenario = Budget.objects.get(id=resp.data['id'])
        self.assertEqual(scenario.scenario, Budget.Scenario.OPTIMISTE)
        self.assertEqual(scenario.lignes.count(), self.budget.lignes.count())
        # Le budget OFFICIEL n'a pas bougé : ni figé, ni re-versionné.
        self.budget.refresh_from_db()
        self.assertFalse(self.budget.figee)
        self.assertEqual(self.budget.scenario, Budget.Scenario.ENGAGE)

    def test_scenario_engage_refuse(self):
        """Ce serait fabriquer un SECOND budget officiel."""
        resp = self.api.post(
            f'{BUDGETS}{self.budget.id}/scenario-what-if/',
            {'scenario': Budget.Scenario.ENGAGE}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_scopee_par_societe(self):
        autre = make_company('audv09-budget-autre', 'AUDV09 Autre')
        services.seed_plan_comptable(autre)
        budget_autre = services.creer_budget(
            autre, annee=2026, libelle='Hors société', lignes=[])
        resp = self.api.post(f'{BUDGETS}{budget_autre.id}/reviser/', {},
                             format='json')
        self.assertEqual(resp.status_code, 404)


class RegleImputationRestTests(TestCase):
    def setUp(self):
        self.co = make_company('audv09-regle', 'AUDV09 Règle')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.api = auth(make_user(self.co, 'audv09-regle-user'))
        self.centre_a = CentreCout.objects.create(
            company=self.co, code='CA', libelle='Chantiers')
        self.centre_b = CentreCout.objects.create(
            company=self.co, code='CB', libelle='Siège')

    def _corps(self, **extra):
        corps = {
            'libelle': 'Achats chantier 60 %',
            'prefixe_compte': '611',
            'distributions': [
                {'centre_cout': self.centre_a.id, 'pourcentage': '60.00'},
                {'centre_cout': self.centre_b.id, 'pourcentage': '40.00'},
            ],
        }
        corps.update(extra)
        return corps

    def test_creation_pose_la_societe_et_les_distributions(self):
        resp = self.api.post(REGLES, self._corps(), format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        regle = RegleImputation.objects.get(id=resp.data['id'])
        self.assertEqual(regle.company_id, self.co.id)
        self.assertEqual(regle.distributions.count(), 2)
        self.assertEqual(len(resp.data['distributions']), 2)

    def test_distribution_qui_ne_somme_pas_a_100_refusee(self):
        """Une distribution partielle imputerait une part de la charge nulle
        part — exactement ce qu'une auto-imputation doit rendre impossible."""
        resp = self.api.post(REGLES, self._corps(distributions=[
            {'centre_cout': self.centre_a.id, 'pourcentage': '60.00'},
        ]), format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(RegleImputation.objects.filter(company=self.co).count(), 0)

    def test_centre_de_cout_d_une_autre_societe_refuse(self):
        autre = make_company('audv09-regle-autre', 'AUDV09 Règle Autre')
        centre_autre = CentreCout.objects.create(
            company=autre, code='CX', libelle='Hors société')
        resp = self.api.post(REGLES, self._corps(distributions=[
            {'centre_cout': centre_autre.id, 'pourcentage': '100.00'},
        ]), format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_la_regle_creee_par_l_api_est_APPLIQUEE_aux_ecritures(self):
        """Le moteur tournait à vide : c'est le lien que cette tâche ferme."""
        self.api.post(REGLES, self._corps(), format='json')
        compte_achat = services.get_compte(self.co, '6111')
        compte_banque = services.get_compte(self.co, '5141')
        from datetime import date
        ecriture = services.creer_ecriture_od(
            self.co, date(2026, 3, 1), 'Achat chantier',
            [{'compte': compte_achat, 'debit': Decimal('1000'),
              'credit': Decimal('0'), 'libelle': 'Achat'},
             {'compte': compte_banque, 'debit': Decimal('0'),
              'credit': Decimal('1000'), 'libelle': 'Achat'}])
        ligne = ecriture.lignes.get(compte=compte_achat)
        # La règle a ventilé la ligne 60/40 sans aucune saisie manuelle.
        ventilation = getattr(ligne, 'ventilation_analytique', None)
        self.assertIsNotNone(
            ventilation,
            "Le moteur d'auto-imputation n'a pas appliqué la règle créée par "
            "l'API : il tourne toujours à vide.")
        self.assertEqual(ventilation.distributions.count(), 2)
        self.assertEqual(
            sorted(d.pourcentage for d in ventilation.distributions.all()),
            [Decimal('40.00'), Decimal('60.00')])

    def test_isolation_multi_societe_en_lecture(self):
        autre = make_company('audv09-regle-iso', 'AUDV09 Iso')
        RegleImputation.objects.create(
            company=autre, libelle='Hors société', prefixe_compte='6')
        resp = self.api.get(REGLES)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)
