"""NTFPA28 — notification cycle de validation : ouvrir un cycle en saisie
notifie automatiquement tous les responsables de département actif."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import CycleBudgetaire, Departement
from apps.fpa.services import notifier_ouverture_cycle
from apps.notifications.models import Notification

User = get_user_model()


class TestNotifierOuvertureCycle(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa28-co', defaults={'nom': 'NTFPA28 Co'})
        self.r1 = User.objects.create_user(
            username='ntfpa28-r1', password='x', company=self.company)
        self.r2 = User.objects.create_user(
            username='ntfpa28-r2', password='x', company=self.company)
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        Departement.objects.create(
            company=self.company, code='A', nom='A', responsable=self.r1, actif=True)
        Departement.objects.create(
            company=self.company, code='B', nom='B', responsable=self.r2, actif=True)
        # Département inactif : son responsable n'est PAS notifié.
        Departement.objects.create(
            company=self.company, code='C', nom='C',
            responsable=User.objects.create_user(
                username='ntfpa28-r3', password='x', company=self.company),
            actif=False)

    def test_ouverture_notifie_tous_les_responsables_actifs(self):
        notifier_ouverture_cycle(self.cycle)
        destinataires = set(
            Notification.objects.filter(company=self.company)
            .values_list('recipient', flat=True))
        self.assertIn(self.r1.pk, destinataires)
        self.assertIn(self.r2.pk, destinataires)
        # Le responsable du département inactif n'est pas notifié.
        self.assertEqual(len(destinataires), 2)
