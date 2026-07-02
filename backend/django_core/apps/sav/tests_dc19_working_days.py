"""DC19 — ContratMaintenance.prochaine_visite tombe sur un JOUR OUVRÉ.

La date de la prochaine visite de maintenance est reportée au prochain jour
ouvré de la société (par défaut Lun–Ven) via le référentiel calendrier partagé
(apps.notifications.calendar_utils). Une visite n'est jamais planifiée un
week-end/férié.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance


class TestDC19MaintenanceWorkingDay(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='dc19-co', defaults={'nom': 'DC19 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='C', prenom='D', email='c@d.ma',
            telephone='+212600000019')

    def _contrat(self, **kw):
        defaults = dict(
            company=self.company, client=self.client_obj,
            periodicite='mensuel', date_debut=date(2024, 1, 1),
            actif=True, prix=Decimal('1000'))
        defaults.update(kw)
        return ContratMaintenance.objects.create(**defaults)

    def test_prochaine_visite_rolls_weekend_to_monday(self):
        # derniere_visite 2024-05-01 → +1 mois = 2024-06-01 (samedi) → lundi 03.
        c = self._contrat(derniere_visite=date(2024, 5, 1))
        self.assertEqual(c.prochaine_visite(), date(2024, 6, 3))

    def test_prochaine_visite_keeps_working_day(self):
        # derniere_visite 2024-05-05 → +1 mois = 2024-06-05 (mercredi) inchangé.
        c = self._contrat(derniere_visite=date(2024, 5, 5))
        self.assertEqual(c.prochaine_visite().weekday() < 5, True)
        self.assertEqual(c.prochaine_visite(), date(2024, 6, 5))
