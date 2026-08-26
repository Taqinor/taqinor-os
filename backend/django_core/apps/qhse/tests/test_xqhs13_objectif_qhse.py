"""Tests XQHS13 — Objectifs & cibles QHSE/ESG avec revues périodiques.

Couvre :

* le calcul automatique d'atteinte (sens hausse/baisse) ;
* la trajectoire baseline→cible vs réel ;
* la détection des objectifs dont la revue est due ;
* le scoping société ;
* WIR275 — l'exposition REST (CRUD + actions ``revues-dues``/``trajectoire``,
  ``atteint`` DÉRIVÉ côté serveur, jamais reçu en écriture).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import ObjectifQhse, RevueObjectif
from apps.qhse.selectors import objectifs_revue_due, trajectoire_objectif

User = get_user_model()

OBJECTIFS = '/api/django/qhse/objectifs/'
REVUES = '/api/django/qhse/revues-objectif/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CalculerAtteintTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs13-atteint', 'CoXqhs13Atteint')

    def test_sens_hausse_atteint(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Satisfaction client',
            valeur_cible=90, sens_amelioration=ObjectifQhse.SensAmelioration.HAUSSE)
        revue = RevueObjectif.objects.create(
            company=self.company, objectif=objectif, valeur_constatee=95)
        self.assertTrue(revue.atteint)

    def test_sens_hausse_non_atteint(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Satisfaction client',
            valeur_cible=90, sens_amelioration=ObjectifQhse.SensAmelioration.HAUSSE)
        revue = RevueObjectif.objects.create(
            company=self.company, objectif=objectif, valeur_constatee=70)
        self.assertFalse(revue.atteint)

    def test_sens_baisse_atteint(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Taux accidents',
            valeur_cible=2, sens_amelioration=ObjectifQhse.SensAmelioration.BAISSE)
        revue = RevueObjectif.objects.create(
            company=self.company, objectif=objectif, valeur_constatee=1)
        self.assertTrue(revue.atteint)

    def test_sans_cible_ni_valeur_none(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Sans cible')
        revue = RevueObjectif.objects.create(
            company=self.company, objectif=objectif)
        self.assertIsNone(revue.atteint)


class TrajectoireObjectifTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs13-traj', 'CoXqhs13Traj')

    def test_points_ordonnes_chronologiquement(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='CO2', valeur_baseline=100,
            valeur_cible=50, annee_baseline=2025)
        RevueObjectif.objects.create(
            company=self.company, objectif=objectif, periode='T2',
            date_revue=date(2026, 6, 1), valeur_constatee=70)
        RevueObjectif.objects.create(
            company=self.company, objectif=objectif, periode='T1',
            date_revue=date(2026, 3, 1), valeur_constatee=85)
        result = trajectoire_objectif(objectif)
        self.assertEqual(result['baseline'], 100)
        self.assertEqual(result['cible'], 50)
        self.assertEqual(len(result['points']), 2)
        self.assertEqual(result['points'][0]['periode'], 'T1')
        self.assertEqual(result['points'][1]['periode'], 'T2')


class ObjectifsRevueDueTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs13-due', 'CoXqhs13Due')

    def test_due_sans_revue_anterieure(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Nouveau')
        dus = objectifs_revue_due(self.company)
        self.assertIn(objectif, dus)

    def test_pas_due_apres_revue_recente(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Récent',
            frequence_revue=ObjectifQhse.Frequence.TRIMESTRIELLE)
        RevueObjectif.objects.create(
            company=self.company, objectif=objectif,
            date_revue=date.today() - timedelta(days=10))
        dus = objectifs_revue_due(self.company)
        self.assertNotIn(objectif, dus)

    def test_due_apres_cadence_depassee(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='En retard',
            frequence_revue=ObjectifQhse.Frequence.TRIMESTRIELLE)
        RevueObjectif.objects.create(
            company=self.company, objectif=objectif,
            date_revue=date.today() - timedelta(days=100))
        dus = objectifs_revue_due(self.company)
        self.assertIn(objectif, dus)

    def test_isolation_societe(self):
        autre = make_company('co-xqhs13-due-autre', 'CoXqhs13DueAutre')
        ObjectifQhse.objects.create(company=self.company, intitule='X')
        dus = objectifs_revue_due(autre)
        self.assertEqual(dus, [])


class ObjectifQhseApiTests(TestCase):
    """WIR275 — CRUD + actions ``revues-dues``/``trajectoire`` (selectors
    testés, jusqu'ici sans aucun endpoint)."""

    def setUp(self):
        self.company = make_company('co-xqhs13-obj-api', 'CoXqhs13ObjApi')
        self.user = make_user(self.company, 'resp-xqhs13-obj-api')
        self.api = auth_client(self.user)

    def test_create_pose_company(self):
        resp = self.api.post(OBJECTIFS, {
            'intitule': 'Taux de fréquence accidents',
            'valeur_cible': 2, 'echeance': '2027-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        objectif = ObjectifQhse.objects.get(id=resp.data['id'])
        self.assertEqual(objectif.company_id, self.company.id)

    def test_revues_dues_action(self):
        self.api.post(OBJECTIFS, {'intitule': 'Nouveau'}, format='json')
        resp = self.api.get(f'{OBJECTIFS}revues-dues/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)

    def test_trajectoire_action(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='CO2', valeur_baseline=100,
            valeur_cible=50)
        resp = self.api.get(f'{OBJECTIFS}{objectif.id}/trajectoire/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['points'], [])

    def test_isolation_inter_societes(self):
        autre = make_company('co-xqhs13-obj-api-x', 'Autre')
        ObjectifQhse.objects.create(company=autre, intitule='Hors société')
        data = self.api.get(OBJECTIFS).data
        rows = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(rows), 0)


class RevueObjectifApiTests(TestCase):
    """WIR275 — CRUD ; ``atteint`` DÉRIVÉ côté serveur au ``save()`` du
    modèle, jamais reçu en écriture."""

    def setUp(self):
        self.company = make_company('co-xqhs13-revue-api', 'CoXqhs13RevueApi')
        self.user = make_user(self.company, 'resp-xqhs13-revue-api')
        self.api = auth_client(self.user)
        self.objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Satisfaction client',
            valeur_cible=90,
            sens_amelioration=ObjectifQhse.SensAmelioration.HAUSSE)

    def test_atteint_derive_ignore_valeur_ecrite(self):
        resp = self.api.post(REVUES, {
            'objectif': self.objectif.id, 'valeur_constatee': 95,
            'atteint': False,  # tentative d'écriture directe — ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['atteint'])

    def test_objectif_hors_societe_refuse(self):
        autre = make_company('co-xqhs13-revue-api-x', 'Autre')
        objectif_autre = ObjectifQhse.objects.create(
            company=autre, intitule='Hors société')
        resp = self.api.post(REVUES, {
            'objectif': objectif_autre.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
