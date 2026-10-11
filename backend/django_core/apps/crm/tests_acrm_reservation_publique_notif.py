"""ACRM41 (C-ACRM-036) — une visite réservée par le prospect via le lien
public PRÉVIENT son responsable.

Sonde V_VC LSVC3-1 : ``reserver_creneau_public`` créait le RDV sans aucune
notification (dNotif 0) — le commercial découvrait la visite par hasard.
Désormais, après validation : le responsable (et son supérieur, repli
managers) est notifié, et une note lisible entre au chatter.

Services et notifications réels ; aucun mock.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Appointment, BookingLink, Lead, LeadActivity
from apps.crm.visites_rdv import reserver_creneau_public
from apps.notifications.models import Notification
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS

User = get_user_model()


class ReservationPubliqueNotifTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM41 Solaire', slug='acrm41-reservation')
        directeur = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.manager = User.objects.create_user(
            username='acrm41-dir', password='x', company=self.company,
            role=directeur)
        self.commercial = User.objects.create_user(
            username='acrm41-com', password='x', company=self.company,
            role_legacy='responsable')
        self.quand = timezone.now() + datetime.timedelta(days=2)

    def _reserver(self, lead):
        lien = BookingLink.objects.create(company=self.company, lead=lead)
        with self.captureOnCommitCallbacks(execute=True):
            return reserver_creneau_public(lien.token,
                                           scheduled_at=self.quand)

    def test_responsable_notifie(self):
        lead = Lead.objects.create(company=self.company, nom='Reserve',
                                   owner=self.commercial)
        rdv = self._reserver(lead)
        self.assertEqual(Appointment.objects.filter(lead=lead).count(), 1)
        self.assertTrue(Notification.objects.filter(
            recipient=self.commercial, body__contains=f'RDV #{rdv.pk}'
        ).exists())
        self.assertEqual(LeadActivity.objects.filter(
            lead=lead, body__startswith='Le client a réservé sa visite le'
        ).count(), 1)

    def test_sans_responsable_managers(self):
        lead = Lead.objects.create(company=self.company, nom='SansResp')
        rdv = self._reserver(lead)
        self.assertTrue(Notification.objects.filter(
            recipient=self.manager, body__contains=f'RDV #{rdv.pk}'
        ).exists())
