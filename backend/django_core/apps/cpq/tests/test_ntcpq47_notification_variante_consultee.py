"""NTCPQ47 — Notification à l'auteur du devis quand une variante CPQ
(NTCPQ16) est consultée par le client (préparation portail).

Le fichier vit sous ``apps/cpq/tests`` (couvre un comportement CPQ) mais
teste le code réellement modifié dans ``apps/ventes/public_views.py`` (seul
app à la fois en périmètre CRM_VENTES ET porteuse du mécanisme d'ouverture
publique ShareLink/QJ1 — ``apps.portail`` n'expose pas encore de suivi de
consultation par variante, d'où l'implémentation côté ventes)."""
from django.test import TestCase

from apps.notifications.models import Notification
from apps.ventes.models import ShareLink
from apps.ventes.public_views import _notifier_variante_consultee, _notify_first_open
from testkit.factories import CompanyFactory, DevisFactory, UserFactory


class TestNotificationVarianteConsultee(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.commercial = UserFactory(company=self.company)
        self.devis_base = DevisFactory(
            company=self.company, created_by=self.commercial)
        self.variante = DevisFactory(
            company=self.company, variante_de=self.devis_base,
            variante_tier='premium')

    def _link(self, devis):
        return ShareLink.objects.create(company=self.company, devis=devis)

    def test_consultation_variante_notifie_lauteur_du_devis_de_base(self):
        link = self._link(self.variante)
        _notifier_variante_consultee(link)
        self.assertTrue(Notification.objects.filter(
            recipient=self.commercial,
            event_type='devis_opened').exists())
        notif = Notification.objects.get(
            recipient=self.commercial, event_type='devis_opened')
        self.assertIn('premium', notif.title)
        self.assertIn(self.devis_base.reference, notif.title)

    def test_idempotent_meme_lien_consulte_deux_fois(self):
        link = self._link(self.variante)
        _notifier_variante_consultee(link)
        _notifier_variante_consultee(link)
        self.assertEqual(Notification.objects.filter(
            recipient=self.commercial, event_type='devis_opened').count(), 1)

    def test_devis_de_base_ne_declenche_rien(self):
        """Un devis qui n'EST PAS une variante (variante_de_id vide) ne
        déclenche jamais cette notification — seule une VARIANTE consultée
        déclenche l'événement."""
        link = self._link(self.devis_base)
        _notifier_variante_consultee(link)
        self.assertFalse(Notification.objects.filter(
            event_type='devis_opened').exists())

    def test_notify_first_open_appelle_bien_le_chemin_variante(self):
        """Preuve de câblage : ``_notify_first_open`` (point d'entrée des 3
        vues publiques ShareLink) déclenche la notification de variante
        même en l'ABSENCE de lead lié (chemin indépendant du QJ1/QJ2)."""
        link = self._link(self.variante)
        _notify_first_open(link)
        self.assertTrue(Notification.objects.filter(
            recipient=self.commercial, event_type='devis_opened').exists())
