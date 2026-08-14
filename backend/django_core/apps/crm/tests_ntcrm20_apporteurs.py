"""NTCRM20 — Registre des apporteurs d'affaires (Deal Registration)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Apporteur, DealEnregistre, Lead
from apps.roles.models import Role

User = get_user_model()


class DealEnregistreProtectionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM20', slug='taqinor-ntcrm20')
        self.apporteur1 = Apporteur.objects.create(
            company=self.company, nom='Apporteur A')
        self.apporteur2 = Apporteur.objects.create(
            company=self.company, nom='Apporteur B')

    def test_second_apporteur_refuse_pendant_la_fenetre(self):
        lead1 = Lead.objects.create(
            company=self.company, nom='Prospect', telephone='0612345678')
        DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur1, lead=lead1)

        lead2 = Lead.objects.create(
            company=self.company, nom='Prospect (doublon)', telephone='0612345678')
        deal2 = DealEnregistre(
            company=self.company, apporteur=self.apporteur2, lead=lead2)
        with self.assertRaises(Exception):
            deal2.full_clean()

    def test_apporteur_different_client_ok(self):
        lead1 = Lead.objects.create(
            company=self.company, nom='Client 1', telephone='0611111111')
        DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur1, lead=lead1)

        lead2 = Lead.objects.create(
            company=self.company, nom='Client 2', telephone='0622222222')
        deal2 = DealEnregistre(
            company=self.company, apporteur=self.apporteur2, lead=lead2)
        deal2.full_clean()  # ne lève pas

    def test_apres_rejet_le_deal_ne_protege_plus(self):
        lead1 = Lead.objects.create(
            company=self.company, nom='Prospect', telephone='0633333333')
        deal1 = DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur1, lead=lead1)
        deal1.statut = DealEnregistre.Statut.REJETE
        deal1.save(update_fields=['statut'])

        lead2 = Lead.objects.create(
            company=self.company, nom='Prospect (repris)', telephone='0633333333')
        deal2 = DealEnregistre(
            company=self.company, apporteur=self.apporteur2, lead=lead2)
        deal2.full_clean()  # ne lève pas : la protection est levée


class ApporteurApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM20b', slug='taqinor-ntcrm20b')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm20', password='x',
            company=self.company, role=self.role)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_crud_apporteur(self):
        resp = self.api.post('/api/django/crm/apporteurs/', {
            'nom': 'Nouvel apporteur', 'type_apporteur': 'courtier',
        })
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_enregistrer_puis_refus_second_via_api(self):
        apporteur1 = Apporteur.objects.create(company=self.company, nom='A1')
        apporteur2 = Apporteur.objects.create(company=self.company, nom='A2')
        lead1 = Lead.objects.create(
            company=self.company, nom='Prospect API', telephone='0644444444')
        resp = self.api.post('/api/django/crm/deals-enregistres/', {
            'apporteur': apporteur1.pk, 'lead': lead1.pk,
        })
        self.assertEqual(resp.status_code, 201, resp.data)

        lead2 = Lead.objects.create(
            company=self.company, nom='Prospect API bis', telephone='0644444444')
        resp2 = self.api.post('/api/django/crm/deals-enregistres/', {
            'apporteur': apporteur2.pk, 'lead': lead2.pk,
        })
        self.assertEqual(resp2.status_code, 400, resp2.data)

    def test_approuver_rejeter(self):
        apporteur = Apporteur.objects.create(company=self.company, nom='A')
        lead = Lead.objects.create(company=self.company, nom='Prospect approuver')
        deal = DealEnregistre.objects.create(
            company=self.company, apporteur=apporteur, lead=lead)
        resp = self.api.post(f'/api/django/crm/deals-enregistres/{deal.pk}/approuver/')
        self.assertEqual(resp.status_code, 200, resp.data)
        deal.refresh_from_db()
        self.assertEqual(deal.statut, DealEnregistre.Statut.APPROUVE)
