"""NTSAN2 — Modèle `Salle`/`Ressource` : CRUD scopé tenant.

Le critère « une salle ne peut pas être double-réservée sur le même créneau »
(contrainte applicative dans `services.py`) est implémenté et testé dans
`test_rendez_vous.py` (NTSAN4) : le créneau qu'une salle peut occuper n'existe
qu'une fois `RendezVous` posé — cette réservation croisée praticien+salle est
l'unique consommateur d'un créneau de salle.
"""
from django.test import TestCase

from authentication.models import Company

from apps.sante.models import Salle


class SalleModelTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-salle-co', defaults={'nom': 'Clinique Salle'})

    def test_create_and_scope(self):
        salle = Salle.objects.create(
            company=self.company, nom='Salle 1', type=Salle.Type.CONSULTATION,
            capacite=1)
        self.assertEqual(salle.company, self.company)
        self.assertEqual(str(salle), 'Salle 1')
