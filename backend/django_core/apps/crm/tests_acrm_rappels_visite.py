"""ACRM42 (C-ACRM-037) — un rappel par rendez-vous, et jamais un rappel
« envoyé » à personne.

Sondes V_VC LSVC3-2 et LSVC3-7 : en période de Ramadan, un RDV de 19 h 30
avait toute sa fenêtre de rappel (18 h 30–19 h 30) dans la plage iftar —
jamais rappelé ; et un RDV d'un lead sans responsable était marqué
``reminder_sent`` sans qu'aucune notification ne parte. Désormais : rappel
dans l'heure qui PRÉCÈDE la plage, managers prévenus à défaut de
responsable, et sans destinataire le rappel reste à faire (retenté).

Horloge figée (``testkit.time.frozen`` sur ``timezone.now``) — l'horloge,
jamais la source testée.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires
from apps.crm.models import Appointment, Lead
from apps.crm.visites_rdv import send_due_appointment_reminders
from apps.notifications.models import Notification
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS

User = get_user_model()
JOUR = datetime.date(2026, 10, 14)
RDV_19H30 = datetime.datetime.combine(JOUR, datetime.time(19, 30),
                                      tzinfo=horaires.CASABLANCA)


class RappelsVisiteTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM42 Solaire', slug='acrm42-rappels')
        self.commercial = User.objects.create_user(
            username='acrm42-com', password='x', company=self.company,
            role_legacy='responsable')

    def _manager(self):
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        return User.objects.create_user(
            username='acrm42-dir', password='x', company=self.company,
            role=role)

    def _rdv(self, lead, quand):
        return Appointment.objects.create(
            company=self.company, lead=lead, scheduled_at=quand,
            statut=Appointment.Statut.PLANIFIE)

    def test_rdv_iftar_rappele_avant(self):
        profil, _ = CompanyProfile.objects.get_or_create(company=self.company)
        profil.ramadan_debut = JOUR - datetime.timedelta(days=3)
        profil.ramadan_fin = JOUR + datetime.timedelta(days=3)
        profil.save()
        lead = Lead.objects.create(company=self.company, nom='Ftour',
                                   owner=self.commercial)
        rdv = self._rdv(lead, RDV_19H30)
        instant = datetime.datetime.combine(
            JOUR, datetime.time(17, 0), tzinfo=horaires.CASABLANCA)
        fin = datetime.datetime.combine(
            JOUR, datetime.time(21, 5), tzinfo=horaires.CASABLANCA)
        rappele_a = None
        while instant <= fin and rappele_a is None:
            with frozen(instant):
                send_due_appointment_reminders()
            rdv.refresh_from_db()
            if rdv.reminder_sent:
                rappele_a = instant
            instant += datetime.timedelta(minutes=5)
        self.assertIsNotNone(rappele_a, 'RDV de 19 h 30 jamais rappelé')
        self.assertLess(rappele_a, RDV_19H30)
        self.assertFalse(horaires.dans_plage_iftar(rappele_a))

    def test_sans_responsable_managers(self):
        manager = self._manager()
        lead = Lead.objects.create(company=self.company, nom='SansResp')
        rdv = self._rdv(lead, timezone.now() + datetime.timedelta(minutes=30))
        send_due_appointment_reminders()
        rdv.refresh_from_db()
        self.assertTrue(rdv.reminder_sent)
        self.assertTrue(Notification.objects.filter(
            recipient=manager, body__contains=f'RDV #{rdv.pk}').exists())

    def test_sans_destinataire_non_marque(self):
        lead = Lead.objects.create(company=self.company, nom='Personne')
        rdv = self._rdv(lead, timezone.now() + datetime.timedelta(minutes=30))
        send_due_appointment_reminders()
        rdv.refresh_from_db()
        self.assertFalse(rdv.reminder_sent)
