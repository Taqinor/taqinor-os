"""NTMFG30 — Tâche planifiée : recalcul MRP nocturne + notification des
ruptures prévisionnelles.

Critère : la tâche s'exécute par société sans fuite cross-tenant, une
notification est créée une seule fois par rupture détectée (pas de doublon
si déjà notifiée la veille pour le même produit/période), dégrade proprement
sans Celery beat déployé (callable directement comme une fonction)."""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.mrp.tasks import recalculer_besoins_nocturne
from apps.notifications.models import Notification

from ._fixtures import make_company, make_user

_LIGNE_RUPTURE = {
    'produit_id': 1, 'produit_nom': 'Produit rupture', 'sku': '',
    'demande': '20', 'stock_disponible': '0', 'en_cours_fabrication': '0',
    'stock_securite': '0', 'besoin_net': '20', 'proposition': 'fabriquer',
    'date_besoin': None,
}


def _sans_rupture(*args, **kwargs):
    return []


class RecalculerBesoinsNocturneTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg30-1', 'MRP NTMFG30 1')
        self.responsable = make_user(
            self.company, 'mrp-ntmfg30-resp', role='responsable')

    @patch('apps.mrp.selectors.calculer_besoins_nets')
    def test_notifie_une_rupture_detectee(self, mock_calc):
        mock_calc.return_value = [dict(_LIGNE_RUPTURE, produit_id=101)]
        result = recalculer_besoins_nocturne()
        self.assertEqual(result[self.company.id], 1)
        notifs = Notification.objects.filter(
            company=self.company, recipient=self.responsable)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('Produit rupture', notifs.first().title)

    @patch('apps.mrp.selectors.calculer_besoins_nets')
    def test_sans_rupture_aucune_notification(self, mock_calc):
        mock_calc.side_effect = _sans_rupture
        result = recalculer_besoins_nocturne()
        self.assertEqual(result[self.company.id], 0)
        self.assertEqual(
            Notification.objects.filter(company=self.company).count(), 0)

    @patch('apps.mrp.selectors.calculer_besoins_nets')
    def test_pas_de_doublon_pour_la_meme_rupture(self, mock_calc):
        mock_calc.return_value = [dict(_LIGNE_RUPTURE, produit_id=102)]
        recalculer_besoins_nocturne()
        result = recalculer_besoins_nocturne()  # ré-exécution le même jour.
        self.assertEqual(result[self.company.id], 0)  # déjà notifié -> no-op.
        self.assertEqual(
            Notification.objects.filter(company=self.company).count(), 1)

    @patch('apps.mrp.selectors.calculer_besoins_nets')
    def test_pas_de_doublon_si_deja_notifie_la_veille(self, mock_calc):
        mock_calc.return_value = [dict(_LIGNE_RUPTURE, produit_id=103)]
        recalculer_besoins_nocturne()
        hier_notif = Notification.objects.filter(company=self.company).first()
        # Simule un envoi la veille (recule l'horodatage d'un jour).
        Notification.objects.filter(pk=hier_notif.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=1))
        result = recalculer_besoins_nocturne()
        self.assertEqual(result[self.company.id], 0)
        self.assertEqual(
            Notification.objects.filter(company=self.company).count(), 1)

    @patch('apps.mrp.selectors.calculer_besoins_nets')
    def test_isolation_cross_tenant(self, mock_calc):
        autre_company = make_company('mrp-ntmfg30-2', 'MRP NTMFG30 2')
        make_user(autre_company, 'mrp-ntmfg30-resp2', role='responsable')

        def _par_societe(company, **kwargs):
            if company.id == self.company.id:
                return [dict(_LIGNE_RUPTURE, produit_id=104)]
            return []

        mock_calc.side_effect = _par_societe
        result = recalculer_besoins_nocturne()
        self.assertEqual(result[self.company.id], 1)
        self.assertEqual(result[autre_company.id], 0)
        self.assertEqual(
            Notification.objects.filter(company=autre_company).count(), 0)

    @patch('apps.mrp.selectors.calculer_besoins_nets')
    def test_appel_direct_sans_celery_beat_ne_leve_pas(self, mock_calc):
        # NTMFG30 — dégrade proprement sans Celery beat déployé : la tâche
        # reste une fonction Python normale, appelable directement.
        mock_calc.return_value = []
        result = recalculer_besoins_nocturne()
        self.assertIn(self.company.id, result)

    @patch('apps.mrp.selectors.calculer_besoins_nets')
    def test_societe_en_echec_n_interrompt_pas_les_suivantes(self, mock_calc):
        autre_company = make_company('mrp-ntmfg30-3', 'MRP NTMFG30 3')
        make_user(autre_company, 'mrp-ntmfg30-resp3', role='responsable')

        def _leve_pour_premiere(company, **kwargs):
            if company.id == self.company.id:
                raise ValueError('boom')
            return [dict(_LIGNE_RUPTURE, produit_id=105)]

        mock_calc.side_effect = _leve_pour_premiere
        result = recalculer_besoins_nocturne()
        self.assertNotIn(self.company.id, result)
        self.assertEqual(result[autre_company.id], 1)
