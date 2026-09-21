"""NTCPQ33 — Job planifié « Relance des approbations en attente »."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.cpq.models import EtapeApprobationDevis, ParametresCPQ
from apps.cpq.scheduled import relancer_approbations_en_attente
from apps.notifications.models import Notification
from testkit.factories import CompanyFactory, DevisFactory, UserFactory


class TestRelanceApprobations(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.approbateur = UserFactory(company=self.company)
        self.devis = DevisFactory(company=self.company, remise_globale=Decimal('25'))

    def _etape(self, *, jours_attente=3, derniere_relance_le=None):
        etape = EtapeApprobationDevis.objects.create(
            company=self.company, devis=self.devis, niveau=1,
            approbateur=self.approbateur,
            statut=EtapeApprobationDevis.Statut.EN_ATTENTE)
        # date_creation a auto_now_add=True : on la recule manuellement via update().
        EtapeApprobationDevis.objects.filter(id=etape.id).update(
            date_creation=timezone.now() - timedelta(days=jours_attente),
            derniere_relance_le=derniere_relance_le)
        etape.refresh_from_db()
        return etape

    def test_relance_apres_seuil_par_defaut(self):
        etape = self._etape(jours_attente=3)  # seuil défaut = 2 jours
        count = relancer_approbations_en_attente()
        self.assertEqual(count, 1)
        etape.refresh_from_db()
        self.assertIsNotNone(etape.derniere_relance_le)
        self.assertTrue(Notification.objects.filter(
            recipient=self.approbateur, event_type='approval_reminder',
        ).exists())

    def test_pas_de_relance_avant_seuil(self):
        self._etape(jours_attente=1)  # seuil défaut = 2 jours
        count = relancer_approbations_en_attente()
        self.assertEqual(count, 0)

    def test_seuil_configurable_via_parametres_cpq(self):
        ParametresCPQ.objects.create(
            company=self.company, delai_relance_approbation_jours=5)
        self._etape(jours_attente=3)  # < 5 jours → pas encore
        self.assertEqual(relancer_approbations_en_attente(), 0)

    def test_idempotent_moins_de_24h_apres_derniere_relance(self):
        self._etape(
            jours_attente=3,
            derniere_relance_le=timezone.now() - timedelta(hours=1))
        count = relancer_approbations_en_attente()
        self.assertEqual(count, 0)

    def test_relance_de_nouveau_apres_24h(self):
        self._etape(
            jours_attente=5,
            derniere_relance_le=timezone.now() - timedelta(hours=25))
        count = relancer_approbations_en_attente()
        self.assertEqual(count, 1)

    def test_sans_approbateur_ignoree(self):
        etape = EtapeApprobationDevis.objects.create(
            company=self.company, devis=self.devis, niveau=1,
            statut=EtapeApprobationDevis.Statut.EN_ATTENTE)
        EtapeApprobationDevis.objects.filter(id=etape.id).update(
            date_creation=timezone.now() - timedelta(days=5))
        self.assertEqual(relancer_approbations_en_attente(), 0)
