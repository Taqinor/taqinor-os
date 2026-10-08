"""APAR43 — garde BIDIRECTIONNELLE du bus d'événements (C-APAR-036).

* un signal avec un abonné VIVANT doit avoir un émetteur statique, sauf
  producteur parqué justifié dans ``ALLOWED_UNEMITTED`` ;
* aucune liste blanche n'est périmée (``facture_emise`` a un abonné : il ne
  peut plus être « sans abonné ») ;
* les abonnés X3 câblés sur des producteurs parqués sont retirés
  (``contrat_signe``, ``projet_status_change``, ``rfq_attribuee``) ;
* un déclencheur d'automatisation parqué est refusé à la création (400) et
  absent du brouillon IA ; une règle existante n'est pas supprimée.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from core import event_coverage, events

User = get_user_model()


class BusBidirectionnelTests(TestCase):
    def test_aucun_abonne_sans_emetteur_non_justifie(self):
        self.assertEqual(event_coverage.receivers_without_emitter(), set())

    def test_listes_blanches_a_jour(self):
        self.assertEqual(event_coverage.stale_allowlist(), set())
        self.assertNotIn('facture_emise', event_coverage.ALLOWED_UNCONSUMED)
        self.assertEqual(
            event_coverage.ALLOWED_UNEMITTED,
            {'abonnement_monitoring_resilie', 'effet_rejete'})
        self.assertEqual(event_coverage.orphan_signals(), set())
        self.assertEqual(event_coverage.unproduced_eventtypes(), set())

    def test_producteurs_parques_justifies(self):
        for nom in event_coverage.ALLOWED_UNEMITTED:
            self.assertTrue(event_coverage.signal_has_receiver(
                getattr(events, nom)), nom)
            self.assertNotIn(nom, event_coverage.emitted_signals(), nom)

    def test_abonnes_retires(self):
        for nom in ('contrat_signe', 'projet_status_change', 'rfq_attribuee'):
            self.assertFalse(event_coverage.signal_has_receiver(
                getattr(events, nom)), nom)
        for nom in ('CONTRAT_SIGNE', 'PROJET_STATUT_CHANGE'):
            self.assertIn(nom, event_coverage.ALLOWED_UNPRODUCED)

    def test_un_abonne_sans_emetteur_fait_rougir_la_garde(self):
        def recepteur(sender, **kwargs):  # pragma: no cover - jamais appelé
            return None

        events.contrat_signe.connect(recepteur, dispatch_uid='apar43_sonde')
        try:
            self.assertIn('contrat_signe',
                          event_coverage.receivers_without_emitter())
            self.assertIn('contrat_signe', event_coverage.stale_allowlist())
        finally:
            events.contrat_signe.disconnect(dispatch_uid='apar43_sonde')


class DeclencheursParquesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR43')
        self.admin = User.objects.create_user(
            username='apar43_admin', password='pw', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def test_creation_refusee(self):
        for trigger in ('projet_status_change', 'projet_phase_change',
                        'rfq_attribuee'):
            r = self.api.post('/api/django/automation/rules/', {
                'nom': f'R {trigger}', 'trigger_type': trigger,
                'action_type': 'send_email', 'trigger_config': {},
                'action_config': {}}, format='json')
            self.assertEqual(r.status_code, 400, (trigger, r.data))
            self.assertIn('module parqué', str(r.data))

    def test_absent_du_brouillon_ia(self):
        from apps.automation.selectors import closed_rule_catalogue
        types = closed_rule_catalogue()['trigger_types']
        self.assertNotIn('projet_status_change', types)
        self.assertNotIn('rfq_attribuee', types)
        self.assertIn('devis_accepted', types)

    def test_regle_existante_conservee(self):
        from apps.automation.models import AutomationRule
        regle = AutomationRule.objects.create(
            company=self.company, nom='Ancienne',
            trigger_type='projet_status_change', action_type='send_email')
        r = self.api.patch(
            f'/api/django/automation/rules/{regle.pk}/', {'nom': 'Renommée'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(AutomationRule.objects.filter(pk=regle.pk).exists())
