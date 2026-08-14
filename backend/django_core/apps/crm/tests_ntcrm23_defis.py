"""NTCRM23 — Défis et leaderboards d'équipe."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Defi, Lead
from apps.crm.selectors import classement_defi
from apps.roles.models import Role

User = get_user_model()


class ClassementDefiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM23', slug='taqinor-ntcrm23')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])
        self.com1 = User.objects.create_user(
            username='com1_ntcrm23', password='x', company=self.company, role=self.role)
        self.com2 = User.objects.create_user(
            username='com2_ntcrm23', password='x', company=self.company, role=self.role)
        self.com3 = User.objects.create_user(
            username='com3_ntcrm23', password='x', company=self.company, role=self.role)
        today = timezone.now().date()
        self.defi = Defi.objects.create(
            company=self.company, nom='Défi du mois',
            periode_debut=today - datetime.timedelta(days=5),
            periode_fin=today + datetime.timedelta(days=5),
            metrique='nb_leads')

    def test_classement_trie_par_commercial_avec_donnees_connues(self):
        for _ in range(5):
            Lead.objects.create(company=self.company, owner=self.com1, nom='L')
        for _ in range(2):
            Lead.objects.create(company=self.company, owner=self.com2, nom='L')
        # com3 sans lead — absent du classement.

        classement = classement_defi(self.defi)
        self.assertEqual(len(classement), 2)
        self.assertEqual(classement[0]['owner_id'], self.com1.id)
        self.assertEqual(classement[0]['realise'], 5)
        self.assertEqual(classement[0]['rang'], 1)
        self.assertEqual(classement[1]['owner_id'], self.com2.id)
        self.assertEqual(classement[1]['rang'], 2)

    def test_lead_hors_periode_ignore(self):
        old = Lead.objects.create(company=self.company, owner=self.com1, nom='Vieux')
        Lead.objects.filter(pk=old.pk).update(
            date_creation=timezone.now() - datetime.timedelta(days=100))
        self.assertEqual(classement_defi(self.defi), [])


class DefiApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM23b', slug='taqinor-ntcrm23b')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm23', password='x',
            company=self.company, role=self.role)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_creer_et_lire_classement(self):
        today = timezone.now().date()
        resp = self.api.post('/api/django/crm/defis/', {
            'nom': 'Défi RDV', 'metrique': 'nb_rdv',
            'periode_debut': str(today), 'periode_fin': str(today),
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        defi_id = resp.data['id']
        resp2 = self.api.get(f'/api/django/crm/defis/{defi_id}/classement/')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data, [])
