"""ASAV18 — le rapport `insights/sav-sla` mesure la résolution par
`sav.selectors.sla_respecte` (échéance EFFECTIVE, pauses décomptées) et la
première réponse par `premiere_reponse_respectee` (échéance de RÉPONSE).

Run :
    python manage.py test apps.reporting.tests_asav18_sav_sla -v2
"""
from datetime import timedelta

from apps.reporting.tests_sav_sla import SavSlaBase
from apps.sav.models import Ticket
from core.dates import aujourd_hui_local


class SavSlaRapportTests(SavSlaBase):

    URL = '/api/django/reporting/insights/sav-sla/'

    def _priorite(self, resp, code):
        return next(p for p in resp.data['par_priorite']
                    if p['priorite'] == code)

    def test_resolution_pause_respectee(self):
        today = aujourd_hui_local()
        # Résolu aujourd'hui, échéance brute J-3 mais 5 jours de pause :
        # échéance effective J+2 -> SLA respecté.
        t = self._make_ticket(
            priorite=Ticket.Priorite.NORMALE, statut=Ticket.Statut.CLOTURE,
            sla_due_at=today - timedelta(days=3), jours_pause=5,
            date_resolution=today)
        self.assertIsNotNone(t.pk)
        resp = self.api.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._priorite(resp, 'normale')['pct_resolution_ok'],
                         100.0)

    def test_premiere_reponse_contre_delai_reponse(self):
        today = aujourd_hui_local()
        # Haute : réponse due à J-5 (ouvert à J-6, délai de réponse 1 j),
        # répondu aujourd'hui, résolution encore dans les 7 jours.
        t = self._make_ticket(
            priorite=Ticket.Priorite.HAUTE, statut=Ticket.Statut.CLOTURE,
            sla_due_at=today + timedelta(days=1),
            sla_reponse_due_at=today - timedelta(days=5),
            date_resolution=today)
        Ticket.objects.filter(pk=t.pk).update(date_premiere_reponse=today)
        resp = self.api.get(self.URL + '?priorite=haute')
        self.assertEqual(resp.status_code, 200)
        haute = self._priorite(resp, 'haute')
        self.assertEqual(haute['pct_premiere_reponse_ok'], 0.0)
        self.assertEqual(haute['pct_resolution_ok'], 100.0)
