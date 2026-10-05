"""ACAL198 — parité des types de la recherche globale / échantillon partagé.

``contract_samples/recherche_types.json`` est lu par le vitest du front
(ACAL199) : chaque type listé doit avoir une ROUTE. Ce test garantit que la
liste égale les types RÉELLEMENT produits par les constructeurs de specs.
"""
import json
from pathlib import Path

from django.test import TestCase

from apps.reporting import search
from authentication.models import Company

ECHANTILLON = (Path(__file__).resolve().parent
               / 'contract_samples' / 'recherche_types.json')


class TestRechercheTypes(TestCase):
    def test_types_serveur_egalent_l_echantillon(self):
        company = Company.objects.get_or_create(
            slug='acal198-co', defaults={'nom': 'ACAL198'})[0]
        co = {'company': company}
        serveur = [builder(co, 'zz')[0]
                   for _cle, builder in search._SEARCH_SPECS]
        # Une même clé de type ne doit pas être doublée.
        self.assertEqual(len(serveur), len(set(serveur)), serveur)
        echantillon = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
        self.assertEqual(sorted(serveur), sorted(echantillon['types']))
        self.assertIn('calepinage', echantillon['types'])
