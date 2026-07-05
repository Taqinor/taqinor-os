"""XQHS18 — Exercices d'urgence (drills) rattachés aux plans d'urgence.

Couvre :
  * un exercice se planifie/réalise avec chrono + observations ;
  * un écart (observations non vide) spawne une CAPA, idempotent ;
  * sans écart renseigné, la création de CAPA échoue proprement ;
  * le retard de fréquence relance (plan sans exercice / exercice ancien) ;
  * le scoping société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import ActionCorrectivePreventive, ExerciceUrgence, PlanUrgence
from apps.qhse.services import (
    creer_capa_depuis_ecart_exercice, plans_exercices_dus,
    realiser_exercice_urgence, relancer_exercices_urgence,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_plan(company, frequence_mois=12, **kwargs):
    defaults = dict(company=company, titre='Plan A', frequence_mois=frequence_mois)
    defaults.update(kwargs)
    return PlanUrgence.objects.create(**defaults)


class RealiserExerciceUrgenceTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs18-real', 'Xqhs18 Real')
        self.plan = make_plan(self.company)

    def test_planifie_puis_realise_avec_chrono(self):
        exercice = ExerciceUrgence.objects.create(
            company=self.company, plan=self.plan,
            type_exercice=ExerciceUrgence.Type.EVACUATION)
        self.assertEqual(exercice.statut, ExerciceUrgence.Statut.PLANIFIE)

        exercice = realiser_exercice_urgence(
            exercice, duree_evacuation_secondes=185, nb_participants=12,
            observations='Sortie de secours 2 encombrée')
        self.assertEqual(exercice.statut, ExerciceUrgence.Statut.REALISE)
        self.assertEqual(exercice.duree_evacuation_secondes, 185)
        self.assertEqual(exercice.nb_participants, 12)
        self.assertIsNotNone(exercice.date_realisee)

    def test_realiser_deja_realise_est_noop(self):
        exercice = ExerciceUrgence.objects.create(
            company=self.company, plan=self.plan,
            statut=ExerciceUrgence.Statut.REALISE,
            date_realisee=timezone.localdate())
        result = realiser_exercice_urgence(
            exercice, observations='autre texte')
        self.assertEqual(result.observations, '')


class CreerCapaDepuisEcartTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs18-capa', 'Xqhs18 Capa')
        self.plan = make_plan(self.company)

    def test_ecart_cree_capa(self):
        exercice = ExerciceUrgence.objects.create(
            company=self.company, plan=self.plan,
            statut=ExerciceUrgence.Statut.REALISE,
            observations='Extincteur périmé non détecté avant exercice')
        capa, created = creer_capa_depuis_ecart_exercice(exercice)
        self.assertTrue(created)
        self.assertIsInstance(capa, ActionCorrectivePreventive)
        exercice.refresh_from_db()
        self.assertEqual(exercice.capa_liee_id, capa.pk)

    def test_idempotent(self):
        exercice = ExerciceUrgence.objects.create(
            company=self.company, plan=self.plan,
            statut=ExerciceUrgence.Statut.REALISE,
            observations='Écart X')
        capa1, created1 = creer_capa_depuis_ecart_exercice(exercice)
        capa2, created2 = creer_capa_depuis_ecart_exercice(exercice)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(capa1.pk, capa2.pk)

    def test_sans_ecart_leve_valueerror(self):
        exercice = ExerciceUrgence.objects.create(
            company=self.company, plan=self.plan,
            statut=ExerciceUrgence.Statut.REALISE, observations='')
        with self.assertRaises(ValueError):
            creer_capa_depuis_ecart_exercice(exercice)


class PlansExercicesDusTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs18-dus', 'Xqhs18 Dus')

    def test_plan_sans_exercice_est_du(self):
        plan = make_plan(self.company)
        dus = plans_exercices_dus(self.company)
        self.assertIn(plan, dus)

    def test_plan_avec_exercice_recent_pas_du(self):
        plan = make_plan(self.company, frequence_mois=12)
        ExerciceUrgence.objects.create(
            company=self.company, plan=plan,
            statut=ExerciceUrgence.Statut.REALISE,
            date_realisee=timezone.localdate() - timedelta(days=10))
        dus = plans_exercices_dus(self.company)
        self.assertNotIn(plan, dus)

    def test_plan_avec_exercice_ancien_est_du(self):
        plan = make_plan(self.company, frequence_mois=6)
        ExerciceUrgence.objects.create(
            company=self.company, plan=plan,
            statut=ExerciceUrgence.Statut.REALISE,
            date_realisee=timezone.localdate() - timedelta(days=400))
        dus = plans_exercices_dus(self.company)
        self.assertIn(plan, dus)

    def test_scope_societe(self):
        other_co = make_company('xqhs18-dus-other', 'Xqhs18 Dus Other')
        make_plan(other_co)
        dus = plans_exercices_dus(self.company)
        self.assertEqual(len(dus), 0)


class RelancerExercicesUrgenceTests(TestCase):
    def test_relance_ne_leve_pas_sans_responsable(self):
        company = make_company('xqhs18-relance', 'Xqhs18 Relance')
        make_plan(company)
        relances = relancer_exercices_urgence(company)
        self.assertEqual(len(relances), 1)


class ExerciceUrgenceApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs18-api', 'Xqhs18 Api')
        self.user = make_user(self.company, 'xqhs18-user')
        self.plan = make_plan(self.company)

    def test_create_pose_company_serveur(self):
        resp = auth(self.user).post(
            '/api/django/qhse/exercices-urgence/',
            {'plan': self.plan.pk, 'type_exercice': 'incendie'}, format='json')
        self.assertEqual(resp.status_code, 201)
        exercice = ExerciceUrgence.objects.get(id=resp.data['id'])
        self.assertEqual(exercice.company_id, self.company.pk)

    def test_realiser_action(self):
        exercice = ExerciceUrgence.objects.create(
            company=self.company, plan=self.plan)
        resp = auth(self.user).post(
            f'/api/django/qhse/exercices-urgence/{exercice.pk}/realiser/',
            {'duree_evacuation_secondes': 200, 'observations': 'RAS'},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], 'realise')

    def test_dus_endpoint(self):
        resp = auth(self.user).get('/api/django/qhse/exercices-urgence/dus/')
        self.assertEqual(resp.status_code, 200)
        ids = [item['id'] for item in resp.data]
        self.assertIn(self.plan.pk, ids)

    def test_isolation_societe(self):
        other_co = make_company('xqhs18-api-other', 'Xqhs18 Api Other')
        other_user = make_user(other_co, 'xqhs18-other-user')
        ExerciceUrgence.objects.create(company=self.company, plan=self.plan)
        resp = auth(other_user).get('/api/django/qhse/exercices-urgence/')
        ids = [item['id'] for item in resp.data.get('results', resp.data)]
        self.assertEqual(len(ids), 0)
