"""NTOBS25 — recalcul planifié de rattrapage du SLA mensuel en cas d'incident
déclaré tardivement.

LIMITE ASSUMÉE (lane isolée ``core/{sla.py,tasks.py}``) : les champs de
traçabilité ``SlaSnapshot.recalcule_le``/``raison_recalcul`` nommés par le
plan ne sont PAS posés ici (``core/models.py``/``core/migrations``
appartiennent à une autre lane en ce moment) — le recalcul est journalisé via
le logger applicatif. Voir ``core/sla.py`` pour la migration exacte à poser
par l'orchestrateur."""
import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from django.apps import apps as django_apps
from authentication.models import Company
from core.sla import (
    SlaSnapshot, generer_snapshot_societe, recalculer_sla_perimes,
)

# Pas d'import statique d'une app domaine sous core (contrat import-linter M3)
IncidentPublic = django_apps.get_model('statuspage', 'IncidentPublic')

PERIODE = datetime.date(2026, 6, 1)


class RecalculerSlaPerimesTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Acme', slug='ntobs25-acme', actif=True)

    def _figer_genere_le(self, snapshot, quand):
        SlaSnapshot.objects.filter(pk=snapshot.pk).update(genere_le=quand)

    def test_snapshot_untouched_when_no_late_incident(self):
        snapshot = generer_snapshot_societe(self.company, PERIODE)
        genere_le_avant = snapshot.genere_le
        regeneres = recalculer_sla_perimes()
        self.assertEqual(regeneres, [])
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.genere_le, genere_le_avant)

    def test_snapshot_regenerated_when_incident_declared_after_generation(self):
        snapshot = generer_snapshot_societe(self.company, PERIODE)
        self._figer_genere_le(snapshot, timezone.now() - datetime.timedelta(days=5))

        # Incident tardif touchant la période du snapshot, MODIFIÉ (created)
        # après ``genere_le`` figé ci-dessus.
        IncidentPublic.objects.create(
            titre='Panne découverte tardivement', company=None,
            severite='critique',
            debute_le=timezone.make_aware(
                datetime.datetime(2026, 6, 15, 10, 0)),
            resolu_le=timezone.make_aware(
                datetime.datetime(2026, 6, 15, 14, 0)))

        regeneres = recalculer_sla_perimes()

        self.assertEqual(len(regeneres), 1)
        snapshot.refresh_from_db()
        self.assertLess(snapshot.uptime_pct, 100)

    def test_notifies_directeur_when_credit_amount_changes(self):
        snapshot = generer_snapshot_societe(self.company, PERIODE)
        self._figer_genere_le(snapshot, timezone.now() - datetime.timedelta(days=5))
        IncidentPublic.objects.create(
            titre='Panne majeure', company=None, severite='critique',
            debute_le=timezone.make_aware(
                datetime.datetime(2026, 6, 10, 0, 0)),
            resolu_le=timezone.make_aware(
                datetime.datetime(2026, 6, 20, 0, 0)))

        with mock.patch('core.sla._notifier_recalcul_credit') as notifier:
            recalculer_sla_perimes()
        self.assertTrue(notifier.called)

    def test_never_overwrites_a_human_decided_credit(self):
        """Un crédit déjà émis/refusé par un humain n'est jamais réécrit par
        le recalcul (même garantie que ``generer_snapshot_societe``)."""
        snapshot = generer_snapshot_societe(self.company, PERIODE)
        snapshot.credit_statut = SlaSnapshot.CreditStatut.EMIS
        snapshot.credit_du_montant = 999.0
        snapshot.save(update_fields=['credit_statut', 'credit_du_montant'])
        self._figer_genere_le(snapshot, timezone.now() - datetime.timedelta(days=5))

        IncidentPublic.objects.create(
            titre='Panne majeure', company=None, severite='critique',
            debute_le=timezone.make_aware(
                datetime.datetime(2026, 6, 10, 0, 0)),
            resolu_le=timezone.make_aware(
                datetime.datetime(2026, 6, 20, 0, 0)))

        recalculer_sla_perimes()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.credit_statut, SlaSnapshot.CreditStatut.EMIS)
        self.assertEqual(float(snapshot.credit_du_montant), 999.0)

    def test_other_companies_unaffected(self):
        autre = Company.objects.create(
            nom='Autre', slug='ntobs25-autre', actif=True)
        snapshot_autre = generer_snapshot_societe(autre, PERIODE)
        genere_le_avant = snapshot_autre.genere_le
        generer_snapshot_societe(self.company, PERIODE)

        IncidentPublic.objects.create(
            titre='Panne société A seulement', company=self.company,
            severite='critique',
            debute_le=timezone.make_aware(
                datetime.datetime(2026, 6, 15, 10, 0)),
            resolu_le=timezone.make_aware(
                datetime.datetime(2026, 6, 15, 14, 0)))
        SlaSnapshot.objects.filter(company=self.company).update(
            genere_le=timezone.now() - datetime.timedelta(days=5))

        recalculer_sla_perimes()
        snapshot_autre.refresh_from_db()
        self.assertEqual(snapshot_autre.genere_le, genere_le_avant)
