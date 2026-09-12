"""Tests NTWFL4 — apps.notifications.calendar_utils.ajouter_heures_ouvrees.

Couvre l'acceptance criteria NTWFL1/NTWFL4 : une étape SLA 48h démarrée un
vendredi, calendrier ouvré actif, échoit après avoir sauté le week-end
(jamais un samedi/dimanche) ; sans jour non ouvré traversé, comportement
identique au calcul brut (heures linéaires) ; ``sla_heures`` vide/0 renvoie
``started`` tel quel.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from .calendar_utils import ajouter_heures_ouvrees


def _prochain_jour_semaine(annee, mois, jour_cible):
    """Premier jour >= 1er du mois dont ``weekday() == jour_cible`` (0=Lun)."""
    d = datetime.date(annee, mois, 1)
    while d.weekday() != jour_cible:
        d += datetime.timedelta(days=1)
    return d


class AjouterHeuresOuvreesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTWFL4 Co')

    def test_sans_sla_renvoie_started_tel_quel(self):
        started = timezone.now()
        self.assertEqual(
            ajouter_heures_ouvrees(started, None, self.company), started)
        self.assertEqual(
            ajouter_heures_ouvrees(started, 0, self.company), started)

    def test_48h_depuis_vendredi_saute_le_weekend(self):
        vendredi = _prochain_jour_semaine(2026, 6, 4)  # 4 = vendredi
        started = timezone.make_aware(
            datetime.datetime(vendredi.year, vendredi.month, vendredi.day, 10, 0))

        echeance = ajouter_heures_ouvrees(started, 48, self.company)

        # Jamais un samedi (5) ni un dimanche (6).
        self.assertNotIn(echeance.weekday(), (5, 6))
        # Doit avoir avancé d'AU MOINS 48h brutes (jamais un raccourci).
        self.assertGreaterEqual(echeance, started + datetime.timedelta(hours=48))
        # La même heure du jour est préservée (heures intra-journée linéaires).
        self.assertEqual(echeance.hour, 10)

    def test_sla_qui_ne_traverse_aucun_weekend_inchange(self):
        lundi = _prochain_jour_semaine(2026, 6, 0)  # 0 = lundi
        started = timezone.make_aware(
            datetime.datetime(lundi.year, lundi.month, lundi.day, 9, 0))
        # 5h un lundi matin reste dans la même journée ouvrée : aucun jour
        # non ouvré traversé, résultat identique au calcul brut.
        echeance = ajouter_heures_ouvrees(started, 5, self.company)
        self.assertEqual(echeance, started + datetime.timedelta(hours=5))
