"""ACAL127 — ``resultat['pertes']`` = les postes SAISIS du calepinage, même
jamais simulé ou périmé ; ``GET pertes/`` dit vrai sur « simulable ».

Constat C-ACAL-071 : ``GET resultat/`` servait ``pertes: []`` tant que la
simulation n'avait pas tourné (ou dès qu'elle était périmée) alors que
``Calepinage.pertes`` portait les postes saisis — la note de calcul et
l'export CSV n'imprimaient rien. ``GET pertes/`` déclarait « non
simulable » une liste vide, alors que la chaîne tourne sans aucun poste
(P50 « borne haute », D-ACAL-7).

Calepinage RÉEL en base de test, client HTTP réel ; aucun mock de la source.

Run :
    python manage.py test apps.calepinage.tests.test_acal_pertes_servies -v2
"""
from __future__ import annotations

import copy

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

from .test_calx5_simulation import LAYOUT

BASE = '/api/django/calepinage/calepinages/'

IAM = {'poste': 'iam', 'libelle': 'Incidence (IAM)', 'pct': 3.0,
       'source': 'saisie', 'reference': 'relevé bureau d’études'}


class PertesServiesTest(TestCase):

    def setUp(self):
        societe = Company.objects.create(nom='ACAL127', slug='acal127')
        role = Role.objects.create(company=societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = get_user_model().objects.create_user(
            username='acal127', password='x', company=societe, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        lead = Lead.objects.create(company=societe, nom='Toiture 127')
        self.calepinage = Calepinage.objects.create(
            company=societe, lead_id=lead.pk, titre='Pertes 127',
            roof_layout=copy.deepcopy(LAYOUT), pertes=[dict(IAM)])

    def _get(self, quoi):
        reponse = self.api.get(f'{BASE}{self.calepinage.pk}/{quoi}/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.data

    def test_resultat_sert_les_postes_saisis(self):
        servi = self._get('resultat')

        self.assertFalse(servi['simule'])
        self.assertEqual([poste['poste'] for poste in servi['pertes']],
                         ['iam'])
        self.assertEqual(servi['pertes'][0]['pct'], 3.0)
        self.assertEqual(servi['pertes'][0]['source'], 'saisie')

    def test_perime_garde_les_postes(self):
        self.calepinage.resultat = {'simulation': {
            'hash_entree': '0' * 64, 'calcule_le': '2026-10-01T10:00:00Z'},
            'pertes': []}
        self.calepinage.save(update_fields=['resultat'])

        servi = self._get('resultat')

        self.assertTrue(servi['simulation_perimee'])
        self.assertIsNone(servi['production'])
        self.assertEqual([poste['poste'] for poste in servi['pertes']],
                         ['iam'])

    def test_get_pertes_sans_poste_est_simulable(self):
        self.calepinage.pertes = []
        self.calepinage.save(update_fields=['pertes'])

        publie = self._get('pertes')

        self.assertEqual(publie['pertes'], [])
        self.assertTrue(publie['simulable'])
        self.assertEqual(publie['motif_non_simulable'], '')

    def test_aller_retour_enregistrer_rouvrir(self):
        poste = {'poste': 'salissure', 'pct': 2.0, 'source': 'mesure'}
        reponse = self.api.post(
            f'{BASE}{self.calepinage.pk}/enregistrer-pertes/',
            {'pertes': [dict(IAM), poste]}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])

        servi = self._get('resultat')
        publie = self._get('pertes')
        self.assertEqual(servi['pertes'], publie['pertes'])
        self.assertEqual([p['poste'] for p in servi['pertes']],
                         ['iam', 'salissure'])
