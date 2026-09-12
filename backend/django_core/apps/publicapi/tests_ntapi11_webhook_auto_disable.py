"""NTAPI11 — désactivation automatique d'un endpoint webhook mort + alerte.

Critère d'acceptation, dans les deux sens :
  * un endpoint qui échoue AU-DELÀ du seuil est auto-désactivé (`enabled=False`,
    `disabled_reason`/`disabled_at` posés) ET son admin est notifié ;
  * un endpoint SAIN n'est JAMAIS désactivé.

Le point le plus important est le garde-fou « consécutifs, pas cumulés » : un
seul succès remet le compteur à zéro, sinon n'importe quelle intégration vivante
finirait par être coupée au bout de quelques mois d'aléas réseau.
"""
import datetime

from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from apps.notifications.models import EventType, Notification

from .constants import EVENT_LEAD_CREATED
from .models import Webhook, WebhookDelivery
from . import webhook_health


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


@override_settings(WEBHOOK_AUTO_DISABLE_THRESHOLD=3,
                   WEBHOOK_AUTO_DISABLE_WINDOW_HOURS=24)
class Ntapi11WebhookAutoDisableTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi11', 'NTAPI11')
        self.webhook = Webhook.objects.create(
            company=self.co, label='Intégration cliente',
            target_url='https://exemple-client.test/hook',
            secret=Webhook.generate_secret(),
            events=[EVENT_LEAD_CREATED])

    def _livraison(self, statut, *, age_heures=0):
        livraison = WebhookDelivery.objects.create(
            company=self.co, webhook=self.webhook, event=EVENT_LEAD_CREATED,
            payload={}, status=statut)
        if age_heures:
            quand = timezone.now() - datetime.timedelta(hours=age_heures)
            WebhookDelivery.objects.filter(pk=livraison.pk).update(
                created_at=quand)
            livraison.refresh_from_db()
        return livraison

    # ── Endpoint mort ─────────────────────────────────────────────────────
    def test_au_dela_du_seuil_le_webhook_est_desactive(self):
        for _ in range(3):
            self._livraison(WebhookDelivery.Statut.FAILED)
        self.assertTrue(webhook_health.evaluer_sante(self.webhook))
        self.webhook.refresh_from_db()
        self.assertFalse(self.webhook.enabled)
        self.assertIn('3 échecs consécutifs', self.webhook.disabled_reason)
        self.assertIsNotNone(self.webhook.disabled_at)

    def test_desactivation_notifie_ladmin_du_tenant(self):
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_user(
            username='admin-ntapi11', password='x', company=self.co,
            role_legacy='admin')
        for _ in range(3):
            self._livraison(WebhookDelivery.Statut.FAILED)
        webhook_health.evaluer_sante(self.webhook)
        notifs = Notification.objects.filter(
            event_type=EventType.API_WEBHOOK_DESACTIVE, company=self.co)
        self.assertTrue(notifs.exists())
        self.assertIn('Intégration cliente', notifs.first().title)

    def test_echec_definitif_compte_comme_un_echec(self):
        self._livraison(WebhookDelivery.Statut.FAILED)
        self._livraison(WebhookDelivery.Statut.FAILED)
        self._livraison(WebhookDelivery.Statut.EN_ECHEC)
        self.assertTrue(webhook_health.evaluer_sante(self.webhook))

    # ── Endpoint sain : jamais désactivé ──────────────────────────────────
    def test_endpoint_sain_nest_jamais_desactive(self):
        for _ in range(20):
            self._livraison(WebhookDelivery.Statut.SUCCESS)
        self.assertFalse(webhook_health.evaluer_sante(self.webhook))
        self.webhook.refresh_from_db()
        self.assertTrue(self.webhook.enabled)

    def test_un_succes_remet_le_compteur_a_zero(self):
        # 5 échecs ANCIENS, puis un succès, puis 2 échecs : la série
        # consécutive vaut 2 (< seuil 3) — l'endpoint vit.
        for heures in (6, 5, 4, 3, 2):
            self._livraison(WebhookDelivery.Statut.FAILED, age_heures=heures)
        self._livraison(WebhookDelivery.Statut.SUCCESS, age_heures=1)
        self._livraison(WebhookDelivery.Statut.FAILED)
        self._livraison(WebhookDelivery.Statut.FAILED)
        self.assertEqual(webhook_health.echecs_consecutifs(self.webhook), 2)
        self.assertFalse(webhook_health.evaluer_sante(self.webhook))
        self.webhook.refresh_from_db()
        self.assertTrue(self.webhook.enabled)

    def test_echecs_hors_fenetre_ne_comptent_pas(self):
        for _ in range(5):
            self._livraison(WebhookDelivery.Statut.FAILED, age_heures=48)
        self.assertEqual(webhook_health.echecs_consecutifs(self.webhook), 0)
        self.assertFalse(webhook_health.evaluer_sante(self.webhook))

    def test_sous_le_seuil_rien_ne_bouge(self):
        self._livraison(WebhookDelivery.Statut.FAILED)
        self._livraison(WebhookDelivery.Statut.FAILED)
        self.assertFalse(webhook_health.evaluer_sante(self.webhook))
        self.webhook.refresh_from_db()
        self.assertTrue(self.webhook.enabled)

    # ── Idempotence, réglages, réactivation ───────────────────────────────
    def test_deuxieme_evaluation_ne_renotifie_pas(self):
        for _ in range(3):
            self._livraison(WebhookDelivery.Statut.FAILED)
        self.assertTrue(webhook_health.evaluer_sante(self.webhook))
        self.webhook.refresh_from_db()
        self.assertFalse(webhook_health.evaluer_sante(self.webhook))

    @override_settings(WEBHOOK_AUTO_DISABLE_THRESHOLD=0)
    def test_seuil_zero_desactive_le_mecanisme(self):
        for _ in range(50):
            self._livraison(WebhookDelivery.Statut.FAILED)
        self.assertFalse(webhook_health.evaluer_sante(self.webhook))
        self.webhook.refresh_from_db()
        self.assertTrue(self.webhook.enabled)

    def test_reactivation_manuelle_efface_la_tracabilite(self):
        for _ in range(3):
            self._livraison(WebhookDelivery.Statut.FAILED)
        webhook_health.evaluer_sante(self.webhook)
        self.webhook.refresh_from_db()
        self.assertFalse(self.webhook.enabled)
        webhook_health.reactiver_webhook(self.webhook)
        self.webhook.refresh_from_db()
        self.assertTrue(self.webhook.enabled)
        self.assertEqual(self.webhook.disabled_reason, '')
        self.assertIsNone(self.webhook.disabled_at)

    def test_un_webhook_dune_autre_societe_nest_pas_affecte(self):
        autre_co = _company('ntapi11-autre', 'NTAPI11 autre')
        autre = Webhook.objects.create(
            company=autre_co, label='autre',
            target_url='https://autre.test/hook',
            secret=Webhook.generate_secret(), events=[EVENT_LEAD_CREATED])
        for _ in range(3):
            self._livraison(WebhookDelivery.Statut.FAILED)
        webhook_health.evaluer_sante(self.webhook)
        autre.refresh_from_db()
        self.assertTrue(autre.enabled)
        self.assertEqual(webhook_health.echecs_consecutifs(autre), 0)
