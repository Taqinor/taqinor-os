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
