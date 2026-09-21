"""NTESG10 — Alertes de dérive trajectoire.

Critère d'acceptation : franchir le seuil déclenche une notification une
seule fois par période (pas de spam à chaque recalcul).
"""
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from testkit.factories import CompanyFactory, UserFactory

from authentication.models import CustomUser
from apps.esg import services
from apps.esg.models import ObjectifESGTrajectoire, PeriodeReportingESG
from apps.notifications.models import EventType, Notification


class AlerteDeriveTrajectoireTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.admin = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_ADMIN)

    def _seed_indicateur(self, code, annee, valeur):
        from apps.qhse.models import IndicateurESG

        IndicateurESG.objects.create(
            company=self.company, code=code, libelle='Émissions',
            pilier=IndicateurESG.Pilier.ENVIRONNEMENT, valeur=valeur,
            annee=annee)

    def _periode(self, libelle):
        return PeriodeReportingESG.objects.create(
            company=self.company, libelle=libelle,
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))

    def test_figer_periode_notifies_on_unfavorable_drift_beyond_threshold(self):
        # Réduction visée 100 -> 50 (2024 -> 2028) : théorique 2026 = 75.
        # Réel 90 en 2026 -> +20 % (bien pire que la trajectoire).
        ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code='E5', libelle='Émissions',
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2028)
        self._seed_indicateur('E5', 2026, 90)
        periode = self._periode('2026')

        services.figer_periode(periode)

        self.assertTrue(Notification.objects.filter(
            recipient=self.admin, event_type=EventType.DIGEST).exists())

    def test_figer_periode_no_notification_within_threshold(self):
        # Théorique 2026 = 75, réel = 78 -> +4 % (sous le seuil de 10 %).
        ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code='E6', libelle='Déchets',
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2028)
        self._seed_indicateur('E6', 2026, 78)
        periode = self._periode('2026-b')

        services.figer_periode(periode)

        self.assertFalse(Notification.objects.filter(
            recipient=self.admin).exists())

    def test_growth_target_unfavorable_when_behind_schedule(self):
        # Trajectoire CROISSANTE (ex. taux de valorisation) 10 -> 90 : réel
        # bien en dessous de la théorique = défavorable (retard).
        ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code='S3', libelle='Valorisation',
            valeur_reference=10, annee_reference=2024,
            valeur_cible=90, annee_cible=2028)
        # Théorique 2026 = 50, réel 10 -> -80 % (bien en retard).
        self._seed_indicateur('S3', 2026, 10)
        periode = self._periode('2026-c')

        services.figer_periode(periode)

        self.assertTrue(Notification.objects.filter(
            recipient=self.admin, event_type=EventType.DIGEST).exists())

    def test_figer_twice_never_double_notifies(self):
        ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code='E7', libelle='Eau',
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2028)
        self._seed_indicateur('E7', 2026, 90)
        periode = self._periode('2026-d')

        services.figer_periode(periode)
        count_after_first = Notification.objects.filter(
            recipient=self.admin).count()
        self.assertGreater(count_after_first, 0)

        with self.assertRaises(ValidationError):
            services.figer_periode(periode)

        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(),
            count_after_first)

    def test_no_objectif_never_raises(self):
        """Aucun objectif actif -> aucune notification, aucune exception."""
        periode = self._periode('2026-e')
        services.figer_periode(periode)
        self.assertFalse(Notification.objects.filter(
            recipient=self.admin).exists())

    def test_alerter_derive_trajectoire_returns_empty_without_company(self):
        periode = self._periode('2026-f')
        periode.company = None
        self.assertEqual(services.alerter_derive_trajectoire(periode), [])
