"""NTMAR15 — Rappels d'échéance fiscale (in-app, best-effort).

Critère : lancer la commande la veille d'une échéance crée une notification
in-app pour le responsable, sans doublon si relancée."""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.fiscal.models import EcheanceFiscale, ObligationFiscale
from apps.fiscal.services import envoyer_rappels_fiscaux
from apps.notifications.models import Notification

from ._fixtures import make_company, make_user


class RappelsFiscauxTests(TestCase):
    def setUp(self):
        self.company = make_company('fiscal-rappel', 'Fiscal Rappel')
        self.responsable = make_user(
            self.company, 'fiscal-resp', role='responsable')
        self.obligation = ObligationFiscale.objects.create(
            company=self.company, type_obligation=ObligationFiscale.Type.TVA,
            libelle='TVA', periodicite=ObligationFiscale.Periodicite.MENSUELLE,
            regle_echeance='20 du mois suivant')
        today = timezone.localdate()
        self.echeance = EcheanceFiscale.objects.create(
            company=self.company, obligation=self.obligation,
            periode_debut=today, periode_fin=today,
            date_limite=today + timedelta(days=7))

    def test_rappel_notifies_responsable_once(self):
        notifiees = envoyer_rappels_fiscaux(self.company, jours_avant=7)
        self.assertEqual(len(notifiees), 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.responsable).exists())

    def test_relancer_ne_double_pas(self):
        envoyer_rappels_fiscaux(self.company, jours_avant=7)
        count_after_first = Notification.objects.filter(
            recipient=self.responsable).count()
        notifiees2 = envoyer_rappels_fiscaux(self.company, jours_avant=7)
        self.assertEqual(notifiees2, [])
        self.assertEqual(
            Notification.objects.filter(recipient=self.responsable).count(),
            count_after_first)

    def test_management_command_is_idempotent(self):
        call_command('rappels_fiscaux', '--jours-avant', '7')
        count_after_first = Notification.objects.filter(
            recipient=self.responsable).count()
        call_command('rappels_fiscaux', '--jours-avant', '7')
        self.assertEqual(
            Notification.objects.filter(recipient=self.responsable).count(),
            count_after_first)
