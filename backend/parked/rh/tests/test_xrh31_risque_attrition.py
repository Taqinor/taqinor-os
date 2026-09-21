"""Tests XRH31 — Score de risque d'attrition (assemblage côté apps.rh).

Couvre :
* ``selectors.features_risque_attrition`` assemble les bonnes features depuis
  les modèles rh (incidents, absences, évaluation, augmentation, sanctions) ;
* l'endpoint agrégé ``employes/{id}/risque-attrition/`` renvoie un score
  cohérent, gaté ``IsResponsableOrAdmin`` ;
* le top-N cockpit est trié décroissant ;
* isolation société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import (
    CampagneEvaluation, DossierEmploye, EvaluationEmploye, IncidentPresence,
    Remuneration, Sanction,
)

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


class FeaturesRisqueAttritionTests(TestCase):
    def setUp(self):
        self.co = make_company('att-a', 'A')
        self.today = timezone.localdate()
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='N', prenom='P',
            statut=DossierEmploye.Statut.ACTIF,
            date_embauche=self.today - timedelta(days=60))

    def test_assemble_ancienneté_et_incidents(self):
        IncidentPresence.objects.create(
            company=self.co, employe=self.employe,
            type_incident=IncidentPresence.TypeIncident.RETARD,
            date=self.today - timedelta(days=10))
        IncidentPresence.objects.create(
            company=self.co, employe=self.employe,
            type_incident=IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE,
            date=self.today - timedelta(days=5))

        features = selectors.features_risque_attrition(self.employe)
        self.assertAlmostEqual(features['seniority_months'], 60 / 30.44, places=1)
        self.assertEqual(features['recent_attendance_incidents'], 1)
        self.assertEqual(features['unplanned_absences'], 1)

    def test_incident_justifie_exclu(self):
        IncidentPresence.objects.create(
            company=self.co, employe=self.employe,
            type_incident=IncidentPresence.TypeIncident.RETARD,
            date=self.today - timedelta(days=5), justifie=True)
        features = selectors.features_risque_attrition(self.employe)
        self.assertEqual(features['recent_attendance_incidents'], 0)

    def test_derniere_evaluation_et_augmentation_et_sanctions(self):
        campagne = CampagneEvaluation.objects.create(
            company=self.co, intitule='2026', annee=2026)
        EvaluationEmploye.objects.create(
            company=self.co, campagne=campagne, employe=self.employe,
            note_globale='2.0')
        Remuneration.objects.create(
            company=self.co, employe=self.employe, montant=8000,
            date_effet=self.today - timedelta(days=400))
        Sanction.objects.create(
            company=self.co, employe=self.employe,
            type_sanction=Sanction.TypeSanction.AVERTISSEMENT,
            date_notification=self.today)

        features = selectors.features_risque_attrition(self.employe)
        self.assertEqual(features['last_evaluation_score'], 2.0)
        self.assertAlmostEqual(
            features['months_since_last_raise'], 400 / 30.44, places=1)
        self.assertEqual(features['sanctions_count'], 1)

    def test_risque_attrition_employe_renvoie_score_borne(self):
        result = selectors.risque_attrition_employe(self.employe)
        self.assertEqual(result['employe_id'], self.employe.id)
        self.assertGreaterEqual(result['score'], 0)
        self.assertLessEqual(result['score'], 100)
        self.assertIn(result['band'], ('faible', 'moyen', 'élevé'))


class RisqueAttritionEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('att-b', 'A')
        self.rh = make_user(self.co, 'att-rh')
        self.normal = make_user(self.co, 'att-normal', role='normal')
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='N', prenom='P',
            statut=DossierEmploye.Statut.ACTIF)

    def test_endpoint_agrege_correct(self):
        resp = auth(self.rh).get(
            f'/api/django/rh/employes/{self.employe.id}/risque-attrition/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('score', resp.data)
        self.assertIn('band', resp.data)

    def test_endpoint_gate_ferme_role_normal(self):
        resp = auth(self.normal).get(
            f'/api/django/rh/employes/{self.employe.id}/risque-attrition/')
        self.assertEqual(resp.status_code, 403)

    def test_top_n_cockpit_trie_decroissant(self):
        employe_risque = DossierEmploye.objects.create(
            company=self.co, matricule='E2', nom='N2', prenom='P2',
            statut=DossierEmploye.Statut.ACTIF,
            date_embauche=timezone.localdate() - timedelta(days=10))
        for i in range(5):
            IncidentPresence.objects.create(
                company=self.co, employe=employe_risque,
                type_incident=IncidentPresence.TypeIncident.RETARD,
                date=timezone.localdate() - timedelta(days=i + 1))

        resp = auth(self.rh).get(
            '/api/django/rh/cockpit/top-risque-attrition/', {'limite': 5})
        self.assertEqual(resp.status_code, 200, resp.data)
        scores = [row['score'] for row in resp.data]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(resp.data[0]['employe_id'], employe_risque.id)

    def test_isolation_societe(self):
        co_b = make_company('att-c', 'B')
        rh_b = make_user(co_b, 'att-rh-b')
        resp = auth(rh_b).get('/api/django/rh/cockpit/top-risque-attrition/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, [])
