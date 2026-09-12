"""NTEXT33 — catalogue de MODÈLES d'automatisation prêts à l'emploi.

``GET automation/modeles-catalogue/`` liste les recettes installables ;
``POST automation/modeles-catalogue/installer/<code>/`` MATÉRIALISE une
vraie ``AutomationRule`` (multi-étapes le cas échéant), distinct du préset
FG3 (``automation/templates/``) qui ne fait que préremplir un formulaire.
Critère : installer « relance J+3 » crée une règle fonctionnelle prête à
activer.
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.automation.models import AutomationRule, AutomationStep

User = get_user_model()

CATALOGUE = '/api/django/automation/modeles-catalogue/'
INSTALLER = '/api/django/automation/modeles-catalogue/installer/'

_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    return Company.objects.create(
        slug=f'ntext33-co-{n}', nom=f'NTEXT33 Co {n}')


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ModelesCatalogueListeTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = User.objects.create_user(
            username='ntext33_u', password='x', company=self.co)
        self.api = _auth(self.user)

    def test_liste_les_recettes_avec_deja_installe(self):
        res = self.api.get(CATALOGUE)
        self.assertEqual(res.status_code, 200, res.data)
        codes = {m['code'] for m in res.data['modeles']}
        self.assertIn('relance_j3_devis_sans_reponse', codes)
        self.assertIn('alerte_stock_bas_bcf', codes)
        self.assertIn('nouveau_lead_assignation', codes)
        for modele in res.data['modeles']:
            self.assertFalse(modele['deja_installe'])
            self.assertNotIn('steps', modele)


class InstallerRelanceJ3Tests(TestCase):
    """Le critère explicite : installer « relance J+3 » crée une règle
    fonctionnelle prête à activer."""

    def setUp(self):
        self.co = make_company()
        self.admin = User.objects.create_user(
            username='ntext33_admin', password='x', role_legacy='admin',
            company=self.co)
        self.api = _auth(self.admin)

    def test_installation_cree_une_regle_activable(self):
        res = self.api.post(
            f'{INSTALLER}relance_j3_devis_sans_reponse/', {}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        rule = AutomationRule.objects.get(company=self.co)
        self.assertEqual(rule.trigger_type, 'date_echeance_champ')
        self.assertEqual(
            rule.trigger_config,
            {'model': 'ventes.devis', 'champ': 'date_validite',
             'offset_jours': 3})
        self.assertEqual(rule.action_type, 'send_email')
        # « Prête à activer » : le défaut du modèle (enabled=True) tient déjà.
        self.assertTrue(rule.enabled)

    def test_reinstaller_est_idempotent(self):
        self.api.post(
            f'{INSTALLER}relance_j3_devis_sans_reponse/', {}, format='json')
        res2 = self.api.post(
            f'{INSTALLER}relance_j3_devis_sans_reponse/', {}, format='json')
        self.assertEqual(res2.status_code, 200, res2.data)
        self.assertFalse(res2.data['cree'])
        self.assertEqual(
            AutomationRule.objects.filter(company=self.co).count(), 1)

    def test_modele_inconnu_404(self):
        res = self.api.post(f'{INSTALLER}inconnu/', {}, format='json')
        self.assertEqual(res.status_code, 404)

    def test_ecriture_reservee_a_ladmin(self):
        commercial = User.objects.create_user(
            username='ntext33_commercial', password='x',
            role_legacy='normal', company=self.co)
        res = _auth(commercial).post(
            f'{INSTALLER}relance_j3_devis_sans_reponse/', {}, format='json')
        self.assertEqual(res.status_code, 403)


class InstallerNouveauLeadAssignationTests(TestCase):
    """Un paramètre requis (user_id) manquant refuse l'installation."""

    def setUp(self):
        self.co = make_company()
        self.admin = User.objects.create_user(
            username='ntext33_admin2', password='x', role_legacy='admin',
            company=self.co)
        self.api = _auth(self.admin)

    def test_sans_user_id_refuse_avec_message_clair(self):
        res = self.api.post(
            f'{INSTALLER}nouveau_lead_assignation/', {}, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('user_id', res.data['detail'])
        self.assertFalse(AutomationRule.objects.filter(company=self.co).exists())

    def test_avec_user_id_installe_et_lassigne(self):
        cible = User.objects.create_user(
            username='ntext33_cible', password='x', company=self.co)
        res = self.api.post(
            f'{INSTALLER}nouveau_lead_assignation/',
            {'user_id': cible.pk}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        rule = AutomationRule.objects.get(company=self.co)
        self.assertEqual(rule.action_config, {'user_id': cible.pk})


class InstallerMultiEtapesTests(TestCase):
    """Une recette avec plusieurs steps matérialise AUSSI les AutomationStep."""

    def setUp(self):
        self.co = make_company()
        self.admin = User.objects.create_user(
            username='ntext33_admin3', password='x', role_legacy='admin',
            company=self.co)
        self.api = _auth(self.admin)

    def test_alerte_stock_bas_une_seule_etape(self):
        res = self.api.post(
            f'{INSTALLER}alerte_stock_bas_bcf/', {}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        rule = AutomationRule.objects.get(company=self.co)
        self.assertEqual(AutomationStep.objects.filter(rule=rule).count(), 0)
        self.assertEqual(rule.action_type, 'create_activity')
