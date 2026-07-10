"""QX12be — les deep-links de notification devis ATTERRISSENT.

« Devis accepté »/« Devis expiré » liaient ``/devis/<pk>`` — une route
inexistante côté front. Ils pointent désormais vers ``/ventes/devis?devis=<pk>``
(param consommé par DevisList, lane frontend).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.notifications.models import Notification, EventType

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class Qx12DevisLinkTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX12 Co')
        self.user = User.objects.create_user(
            username='qx12_seller', password='x', role_legacy='commercial',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX12',
            telephone='+212600000059')

    def test_accepted_notification_link_lands(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX1201',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.user)
        devis.statut = Devis.Statut.ACCEPTE
        devis.save(update_fields=['statut'])
        notif = Notification.objects.filter(
            recipient=self.user,
            event_type=EventType.DEVIS_ACCEPTED).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.link, f'/ventes/devis?devis={devis.id}')
        self.assertNotIn('/devis/' + str(devis.id), notif.link)

    def test_expired_notification_link_lands(self):
        from core.events import devis_expired
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX1202',
            client=self.client_obj, statut=Devis.Statut.EXPIRE,
            taux_tva=Decimal('20'), created_by=self.user)
        devis_expired.send(
            sender=Devis, devis=devis, ancien_statut='envoye')
        notif = Notification.objects.filter(
            recipient=self.user,
            event_type=EventType.DEVIS_EXPIRED).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.link, f'/ventes/devis?devis={devis.id}')
