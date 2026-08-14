"""NTLOG38 — tâche Celery beat quotidienne `transport.check_etapes_transport_
retard` : rappel J-3 sur les étapes en retard (`date_prevue` dépassée,
`statut_etape` != fait), notification unique par étape par jour."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import Notification
from apps.transport.models import EtapeTransport, OrdreTransport
from apps.transport.tasks import check_etapes_transport_retard

from ._helpers import make_company, make_user


class CheckEtapesRetardTests(TestCase):
    def setUp(self):
        self.company = make_company('transport-retard-a', 'A')
        self.user = make_user(self.company, 'transport-retard-a')
        self.ordre = OrdreTransport.objects.create(
            company=self.company, numero='OT-RETARD-1')
        self.etape = EtapeTransport.objects.create(
            company=self.company, ordre=self.ordre, sequence=1,
            type_etape=EtapeTransport.TypeEtape.LIVRAISON,
            statut_etape=EtapeTransport.StatutEtape.A_FAIRE,
            date_prevue=timezone.localdate() - timedelta(days=2))

    def test_etape_en_retard_declenche_une_notification(self):
        check_etapes_transport_retard()
        notifs = Notification.objects.filter(
            company=self.company, event_type='transport_etape_retard',
            recipient=self.user)
        self.assertEqual(notifs.count(), 1)

    def test_pas_de_doublon_si_deja_notifiee_le_jour_meme(self):
        check_etapes_transport_retard()
        check_etapes_transport_retard()
        notifs = Notification.objects.filter(
            company=self.company, event_type='transport_etape_retard',
            recipient=self.user)
        self.assertEqual(notifs.count(), 1)

    def test_etape_a_l_heure_ne_declenche_rien(self):
        EtapeTransport.objects.all().delete()
        EtapeTransport.objects.create(
            company=self.company, ordre=self.ordre, sequence=1,
            type_etape=EtapeTransport.TypeEtape.LIVRAISON,
            statut_etape=EtapeTransport.StatutEtape.A_FAIRE,
            date_prevue=timezone.localdate() + timedelta(days=3))
        check_etapes_transport_retard()
        self.assertFalse(
            Notification.objects.filter(
                company=self.company,
                event_type='transport_etape_retard').exists())

    def test_etape_deja_faite_ne_declenche_rien(self):
        self.etape.statut_etape = EtapeTransport.StatutEtape.FAIT
        self.etape.save(update_fields=['statut_etape'])
        check_etapes_transport_retard()
        self.assertFalse(
            Notification.objects.filter(
                company=self.company,
                event_type='transport_etape_retard').exists())

    def test_isolation_societe(self):
        autre_company = make_company('transport-retard-b', 'B')
        autre_user = make_user(autre_company, 'transport-retard-b')
        check_etapes_transport_retard()
        self.assertFalse(
            Notification.objects.filter(recipient=autre_user).exists())
