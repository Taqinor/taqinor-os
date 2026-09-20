"""NTAPI41 — alertes de santé d'intégration à seuils configurables.

Un webhook auto-désactivé après trop d'échecs consécutifs est DÉJÀ couvert
de bout en bout par NTAPI11 (`apps.publicapi.webhook_health`) : ce lot
n'y touche pas. Ce qui est neuf ici : `notify_integration_health()`, la
brique générique réutilisable par les DEUX autres cas de la même famille
(quota proche de sa limite, pic de taux d'erreur) — elle réutilise
`core.rules.palier_franchi` pour ne jamais notifier deux fois le même
palier, et `notify_many()` pour l'émission effective.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from .models import EventType, Notification
from .services import notify_integration_health

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _admin(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')


class NotifyIntegrationHealthTests(TestCase):
    def setUp(self):
        self.company = _company('ntapi41-health')
        self.admin = _admin(self.company, 'ntapi41-admin')

    def test_sous_le_plus_bas_palier_ne_notifie_pas(self):
        palier = notify_integration_health(
            self.company, [self.admin], title='Alerte', valeur=50,
            paliers=(80, 100))
        self.assertIsNone(palier)
        self.assertFalse(Notification.objects.filter(recipient=self.admin).exists())

    def test_palier_franchi_notifie_et_renvoie_le_palier(self):
        palier = notify_integration_health(
            self.company, [self.admin], title='Taux d\'erreur élevé',
            body='12% sur la dernière heure', link='/parametres/api',
            valeur=85, paliers=(80, 100))
        self.assertEqual(palier, 80)
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin, event_type=EventType.API_TAUX_ERREUR_ELEVE,
            title='Taux d\'erreur élevé', link='/parametres/api').exists())

    def test_palier_deja_notifie_ne_renotifie_pas(self):
        palier = notify_integration_health(
            self.company, [self.admin], title='Alerte', valeur=85,
            paliers=(80, 100), dernier_palier=80)
        self.assertIsNone(palier)
        self.assertFalse(Notification.objects.filter(recipient=self.admin).exists())

    def test_saut_direct_ne_notifie_que_le_plus_haut(self):
        palier = notify_integration_health(
            self.company, [self.admin], title='Alerte', valeur=150,
            paliers=(80, 100))
        self.assertEqual(palier, 100)
        self.assertEqual(Notification.objects.filter(recipient=self.admin).count(), 1)

    def test_event_type_surchargeable_pour_un_quota(self):
        palier = notify_integration_health(
            self.company, [self.admin], title='Quota atteint', valeur=100,
            paliers=(80, 100), event_type=EventType.USAGE_QUOTA_SEUIL_FRANCHI)
        self.assertEqual(palier, 100)
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin,
            event_type=EventType.USAGE_QUOTA_SEUIL_FRANCHI).exists())
