"""ASAV21 — échéance SLA horodatée en heures ouvrées.

Chemin heures (NTSRV11, double opt-in) : ``sla_echeance_at`` (aware) posée,
retard comparé à MAINTENANT (2 h ouvrées → en retard 2 h après, pas le
lendemain). Chemin en jours : ``sla_echeance_at`` reste NULL, ``sla_due_at``
inchangé.

Run :
    python manage.py test apps.sav.tests_asav21_sla_heures -v2
"""
from datetime import date, datetime, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import SavSlaSettings, Ticket
from apps.sav.services import compute_sla_echeance

User = get_user_model()
JEUDI = date(2026, 10, 8)


def local(heure, minute):
    return timezone.make_aware(
        datetime.combine(JEUDI, time(heure, minute)),
        timezone.get_current_timezone())


class SlaHeuresTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav21-co', defaults={'nom': 'ASAV21 Co'})
        self.sla = SavSlaSettings.get(self.company)
        self.sla.sla_breach_enabled = True
        self.sla.sla_heures_ouvrees_actif = True
        self.sla.sla_par_priorite = {'urgente': {'resolution_heures': 2}}
        self.sla.save()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV21')

    def test_echeance_horodatee(self):
        due, echeance = compute_sla_echeance(
            self.company, self.client_obj, 'urgente', JEUDI,
            depart=datetime.combine(JEUDI, time(9, 29)))
        self.assertEqual(due, JEUDI)
        self.assertIsNotNone(echeance)
        self.assertFalse(timezone.is_naive(echeance))
        self.assertEqual(echeance, local(11, 29))

    def test_retard_a_l_heure(self):
        t = Ticket.objects.create(
            company=self.company, reference='SAV-ASAV21-1',
            client=self.client_obj, type=Ticket.Type.CORRECTIF,
            priorite='urgente', statut=Ticket.Statut.EN_COURS,
            date_ouverture=JEUDI)
        Ticket.objects.filter(pk=t.pk).update(
            sla_due_at=JEUDI, sla_echeance_at=local(11, 29))
        t.refresh_from_db()
        with patch('django.utils.timezone.now', return_value=local(11, 0)):
            t.recompute_sla_breach()
            self.assertFalse(t.sla_breach)
        with patch('django.utils.timezone.now', return_value=local(12, 0)):
            t.recompute_sla_breach()
            self.assertTrue(t.sla_breach)

    def test_chemin_jours_inchange(self):
        due, echeance = compute_sla_echeance(
            self.company, self.client_obj, 'normale', JEUDI)
        self.assertIsNone(echeance)
        self.assertEqual(due, date(2026, 10, 15))
