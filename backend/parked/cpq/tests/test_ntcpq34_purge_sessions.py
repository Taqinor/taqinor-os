"""NTCPQ34 — Job planifié « Purge des sessions configurateur abandonnées »."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.cpq.models import SessionConfigurateur
from apps.cpq.scheduled import purger_sessions_configurateur_abandonnees
from testkit.factories import CompanyFactory, DevisFactory


class TestPurgeSessionsConfigurateur(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def _session(self, *, jours_inactif, devis=None):
        session = SessionConfigurateur.objects.create(
            company=self.company, devis=devis)
        SessionConfigurateur.objects.filter(id=session.id).update(
            updated_at=timezone.now() - timedelta(days=jours_inactif))
        return session

    def test_session_45j_sans_devis_purgee(self):
        session = self._session(jours_inactif=45)
        count = purger_sessions_configurateur_abandonnees()
        self.assertEqual(count, 1)
        self.assertFalse(
            SessionConfigurateur.objects.filter(id=session.id).exists())

    def test_session_recente_conservee(self):
        self._session(jours_inactif=5)
        count = purger_sessions_configurateur_abandonnees()
        self.assertEqual(count, 0)
        self.assertEqual(SessionConfigurateur.objects.count(), 1)

    def test_session_avec_devis_jamais_purgee_meme_agee(self):
        devis = DevisFactory(company=self.company)
        session = self._session(jours_inactif=45, devis=devis)
        count = purger_sessions_configurateur_abandonnees()
        self.assertEqual(count, 0)
        self.assertTrue(
            SessionConfigurateur.objects.filter(id=session.id).exists())

    def test_session_exactement_30j_pas_encore_purgee(self):
        # Frontière : le job utilise `updated_at__lt=seuil` (strict) — une
        # session inactive depuis PILE 30 jours n'est pas encore purgeable.
        self._session(jours_inactif=29)
        self.assertEqual(purger_sessions_configurateur_abandonnees(), 0)
