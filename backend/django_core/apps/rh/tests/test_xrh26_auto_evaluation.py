"""Tests XRH26 — Auto-évaluation + issues d'évaluation structurées.

Couvre :
* l'employé concerné remplit son auto-évaluation via le portail ;
* un AUTRE employé de la société reçoit 403 sur cette même évaluation ;
* la validation avec ``issue='formation'`` crée un ``BesoinFormation`` lié ;
* la validation avec ``issue='augmentation_proposee'`` notifie les porteurs
  de ``salaires_voir`` SANS jamais inclure de montant ;
* idempotence : revalider ne recrée pas le besoin/la notification.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.notifications.models import Notification
from apps.rh.models import (
    BesoinFormation, CampagneEvaluation, DossierEmploye, EvaluationEmploye,
)
from apps.roles.models import Role

User = get_user_model()

EVALS_URL = '/api/django/rh/evaluations-employe/'
PORTAIL_AUTO_EVAL = '/api/django/rh/portail/{}/mon-auto-evaluation/'


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


class AutoEvaluationTests(TestCase):
    def setUp(self):
        self.co = make_company('eval-a', 'A')
        self.rh = make_user(self.co, 'eval-rh')
        self.employe_user = make_user(self.co, 'eval-employe', role='normal')
        self.autre_user = make_user(self.co, 'eval-autre', role='normal')

        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='N', prenom='P',
            user=self.employe_user)
        self.autre_dossier = DossierEmploye.objects.create(
            company=self.co, matricule='E2', nom='N2', prenom='P2',
            user=self.autre_user)

        self.campagne = CampagneEvaluation.objects.create(
            company=self.co, intitule='Campagne 2026', annee=2026)
        self.evaluation = EvaluationEmploye.objects.create(
            company=self.co, campagne=self.campagne, employe=self.dossier)

    def test_employe_remplit_sa_propre_auto_evaluation(self):
        resp = auth(self.employe_user).patch(
            PORTAIL_AUTO_EVAL.format(self.evaluation.id), {
                'auto_evaluation': 'Je pense avoir bien performé cette année.',
                'note_auto': '4.5',
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.evaluation.refresh_from_db()
        self.assertIn('bien performé', self.evaluation.auto_evaluation)
        self.assertEqual(str(self.evaluation.note_auto), '4.5')

    def test_autre_employe_recoit_403(self):
        resp = auth(self.autre_user).patch(
            PORTAIL_AUTO_EVAL.format(self.evaluation.id), {
                'auto_evaluation': 'Je tente de remplir celle de quelqu\'un.',
            }, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_manager_ne_peut_pas_editer_auto_eval_via_serializer_generique(self):
        resp = auth(self.rh).patch(
            f'{EVALS_URL}{self.evaluation.id}/', {
                'auto_evaluation': 'Injecté par le manager',
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.auto_evaluation, '')

    def test_validation_issue_formation_cree_besoin_formation(self):
        resp = auth(self.rh).post(
            f'{EVALS_URL}{self.evaluation.id}/valider/', {
                'issue': 'formation',
                'issue_details': 'Formation sécurité électrique avancée',
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        besoin = BesoinFormation.objects.filter(
            company=self.co, employe=self.dossier).first()
        self.assertIsNotNone(besoin)
        self.assertIn('sécurité électrique', besoin.theme)

    def test_validation_issue_augmentation_notifie_salaires_voir_sans_montant(self):
        role_paie = Role.objects.create(
            company=self.co, nom='Paie', permissions=['salaires_voir'])
        porteur = make_user(self.co, 'eval-porteur-salaires')
        porteur.role = role_paie
        porteur.save(update_fields=['role'])

        resp = auth(self.rh).post(
            f'{EVALS_URL}{self.evaluation.id}/valider/', {
                'issue': 'augmentation_proposee',
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        notif = Notification.objects.filter(
            company=self.co, recipient=porteur).first()
        self.assertIsNotNone(notif)
        # Aucun chiffre (montant) dans le corps de la notification.
        self.assertNotRegex(notif.body, r'\d')

    def test_revalider_idempotent_ne_reccree_pas_le_besoin(self):
        auth(self.rh).post(
            f'{EVALS_URL}{self.evaluation.id}/valider/',
            {'issue': 'formation'}, format='json')
        auth(self.rh).post(
            f'{EVALS_URL}{self.evaluation.id}/valider/',
            {'issue': 'formation'}, format='json')
        count = BesoinFormation.objects.filter(
            company=self.co, employe=self.dossier).count()
        self.assertEqual(count, 1)

    def test_issue_aucune_ne_declenche_rien(self):
        resp = auth(self.rh).post(
            f'{EVALS_URL}{self.evaluation.id}/valider/',
            {'issue': 'aucune'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            BesoinFormation.objects.filter(
                company=self.co, employe=self.dossier).count(), 0)
