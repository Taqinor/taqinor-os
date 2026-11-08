"""Tests NTOBS25 — traçabilité d'un recalcul de rapport SLA (schéma).

Ce que les deux champs doivent garantir : vides sur tout snapshot fraîchement
généré (« jamais recalculé »), et ``genere_le`` INTACT quand un recalcul est
enregistré — sinon on perdrait la date de la première publication, qui est
justement celle que le client a vue.

Schéma seul : aucune logique de recalcul n'est écrite ici (elle appartient à la
lane qui possède les fonctions de ``core/sla.py``).
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from core.sla import SlaSnapshot, SlaSnapshotSerializer


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class SlaSnapshotRecalculTests(TestCase):

    def setUp(self):
        self.company = make_company('ntobs25-co', 'NTOBS25 Co')

    def _snapshot(self, mois=9):
        return SlaSnapshot.objects.create(
            company=self.company,
            periode=datetime.date(2026, mois, 1),
            uptime_pct=Decimal('99.9500'))

    def test_vides_sur_un_snapshot_neuf(self):
        snapshot = self._snapshot()
        self.assertIsNone(snapshot.recalcule_le)
        self.assertEqual(snapshot.raison_recalcul, '')

    def test_recalcul_ne_touche_pas_la_date_de_generation(self):
        snapshot = self._snapshot(mois=8)
        genere_le = snapshot.genere_le
        moment = datetime.datetime(
            2026, 9, 20, 12, 0, tzinfo=datetime.timezone.utc)

        snapshot.recalcule_le = moment
        snapshot.raison_recalcul = 'Sonde de latence défectueuse'
        snapshot.save(update_fields=[
            'recalcule_le', 'raison_recalcul', 'updated_at'])

        snapshot.refresh_from_db()
        self.assertEqual(snapshot.recalcule_le, moment)
        self.assertEqual(
            snapshot.raison_recalcul, 'Sonde de latence défectueuse')
        self.assertEqual(snapshot.genere_le, genere_le)

    def test_la_forme_servie_reste_inchangee(self):
        """Schéma seul : la réponse API existante ne bouge pas encore."""
        snapshot = self._snapshot(mois=7)
        champs = set(SlaSnapshotSerializer(snapshot).data)
        self.assertNotIn('recalcule_le', champs)
        self.assertNotIn('raison_recalcul', champs)

    def test_recalcul_pose_la_trace_et_garde_genere_le(self):
        """AMON34 — un recalcul garde ``genere_le``, date le recalcul et pose
        sa raison ; un second passage ne régénère pas le même snapshot ; une
        génération neuve garde ``recalcule_le`` vide."""
        from django.apps import apps as django_apps
        from django.utils import timezone

        from core.sla import (
            RAISON_RECALCUL_INCIDENT_TARDIF, generer_snapshot_societe,
            recalculer_sla_perimes,
        )

        periode = datetime.date(2026, 9, 1)
        snapshot = generer_snapshot_societe(self.company, periode)
        self.assertIsNone(snapshot.recalcule_le)
        il_y_a_5_jours = timezone.now() - datetime.timedelta(days=5)
        SlaSnapshot.objects.filter(pk=snapshot.pk).update(
            genere_le=il_y_a_5_jours)
        django_apps.get_model('statuspage', 'IncidentPublic').objects.create(
            titre='Panne tardive', company=None, severite='critique',
            debute_le=timezone.make_aware(datetime.datetime(2026, 9, 10)),
            resolu_le=timezone.make_aware(datetime.datetime(2026, 9, 11)))

        avant = timezone.now()
        self.assertEqual(len(recalculer_sla_perimes()), 1)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.genere_le, il_y_a_5_jours)
        self.assertGreaterEqual(snapshot.recalcule_le, avant)
        self.assertEqual(snapshot.raison_recalcul,
                         RAISON_RECALCUL_INCIDENT_TARDIF)
        self.assertEqual(recalculer_sla_perimes(), [])
