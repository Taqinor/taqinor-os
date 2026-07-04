"""YSERV5 — Génération automatique planifiée des visites préventives dues.

Couvre :
  * OFF (défaut) = rien, la tâche n'agit pas sur une société non opt-in ;
  * ON → les visites dues sous N jours sont créées, notification émise ;
  * idempotence préservée (un second run le même jour ne double pas) ;
  * `generer_visites_dues(avance_jours=...)` matérialise en avance une visite
    dont l'échéance n'est pas encore atteinte aujourd'hui.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_yserv5 -v 2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.maintenance import generer_visites_dues
from apps.sav.models import ContratMaintenance, SavSlaSettings, Ticket
from apps.sav.tasks import generer_visites_dues_quotidien
from apps.notifications.models import Notification

User = get_user_model()


def make_company(slug='sav-yserv5', nom='Sav Co YSERV5'):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom, 'actif': True})
    return company


class YSERV5GenerationAutoTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='yserv5_admin', password='x', role_legacy='admin',
            company=self.company, is_active=True)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YSERV5',
            email='yserv5-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-YSERV5', client=self.client_obj)
        # Contrat dont la visite tombe dans 5 jours.
        self.contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst,
            date_debut=date.today() - timedelta(days=360), actif=True)

    def test_off_par_defaut_aucun_effet(self):
        # generation_auto_visites reste False par défaut.
        result = generer_visites_dues_quotidien()
        self.assertEqual(result['societes'], 0)
        self.assertFalse(
            Ticket.objects.filter(company=self.company).exists())

    def test_on_genere_visites_avance_et_notifie(self):
        reglage = SavSlaSettings.get(self.company)
        reglage.generation_auto_visites = True
        reglage.visites_avance_jours = 10
        reglage.save(update_fields=[
            'generation_auto_visites', 'visites_avance_jours'])

        result = generer_visites_dues_quotidien()
        self.assertEqual(result['societes'], 1)
        self.assertGreaterEqual(result['visites_generees'], 1)
        self.assertTrue(
            Ticket.objects.filter(
                company=self.company, type=Ticket.Type.PREVENTIF).exists())
        self.assertTrue(
            Notification.objects.filter(
                user=self.admin, event_type='sav_visites_auto_generees',
            ).exists())

    def test_idempotent_pas_de_doublon_meme_jour(self):
        reglage = SavSlaSettings.get(self.company)
        reglage.generation_auto_visites = True
        reglage.visites_avance_jours = 10
        reglage.save(update_fields=[
            'generation_auto_visites', 'visites_avance_jours'])

        generer_visites_dues_quotidien()
        n1 = Ticket.objects.filter(company=self.company).count()
        generer_visites_dues_quotidien()
        n2 = Ticket.objects.filter(company=self.company).count()
        self.assertEqual(n1, n2)

    def test_avance_jours_materialise_avant_echeance(self):
        # Sans avance : pas encore due (visite dans 5 jours).
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst,
            date_debut=date.today() + timedelta(days=5), actif=True)
        n0 = generer_visites_dues(self.company, self.admin, avance_jours=0)
        self.assertEqual(n0, 0)
        # Avec 10 jours d'avance : la visite dans 5 jours est due.
        n1 = generer_visites_dues(self.company, self.admin, avance_jours=10)
        self.assertGreaterEqual(n1, 1)
        contrat.refresh_from_db()
        self.assertIsNotNone(contrat.derniere_visite)
