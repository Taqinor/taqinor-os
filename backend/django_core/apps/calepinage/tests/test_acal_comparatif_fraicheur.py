"""ACAL111 — comparatifs de variantes et de projets : UNE définition de
« simulation périmée » (le verdict servi), plus de clé ``layout_hash`` que
personne n'écrit.

Constat C-ACAL-086 (C10, S2). Les deux comparatifs lisaient une clé
``layout_hash`` du ``resultat`` que le moteur n'écrit JAMAIS : un calepinage
modifié après sa simulation restait « simulé » dans le comparatif alors que
``GET resultat/`` le disait périmé.

Le calepinage est fabriqué par les VRAIS écrivains
(``tests/acal_livrables_helpers.calepinage_simule_reel`` : seul le réseau
météo est rejoué), puis enregistré en base ; le client HTTP est le vrai.

Run :
    python manage.py test apps.calepinage.tests.test_acal_comparatif_fraicheur -v2
"""
import copy

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.comparaison_projets import MOTIF_PERIME
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

from .acal_livrables_helpers import (
    calepinage_simule_reel, modifier_la_conception, patch_materiel,
)

User = get_user_model()

BASE = '/api/django/calepinage/calepinages/'


class ComparatifFraicheurTest(TestCase):
    def setUp(self):
        societe = Company.objects.create(nom='ACAL111', slug='acal111')
        role = Role.objects.create(company=societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = User.objects.create_user(username='acal111', password='x',
                                        company=societe, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        lead = Lead.objects.create(company=societe, nom='Toiture 111')
        pivot = calepinage_simule_reel()
        self.calepinage = Calepinage.objects.create(
            company=societe, lead_id=lead.pk, titre='Comparatif 111',
            roof_layout=copy.deepcopy(pivot.roof_layout),
            resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '',
            version_moteur=pivot.version_moteur or '')

    def _ligne_projet(self):
        with patch_materiel():
            reponse = self.api.post(BASE + 'comparer-projets/',
                                    {'ids': [self.calepinage.pk]},
                                    format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data['lignes'][0]

    def _servi(self):
        with patch_materiel():
            return self.api.get(
                f'{BASE}{self.calepinage.pk}/resultat/').data

    def test_le_depart_est_frais_et_simule(self):
        self.assertFalse(self._servi()['simulation_perimee'])
        ligne = self._ligne_projet()
        self.assertTrue(ligne['simule'])
        self.assertEqual(ligne['motif'], '')

    def test_projet_modifie_apres_simulation_non_simule(self):
        modifier_la_conception(self.calepinage)
        self.calepinage.save()
        self.assertTrue(self._servi()['simulation_perimee'])
        ligne = self._ligne_projet()
        self.assertFalse(ligne['simule'])
        self.assertEqual(ligne['motif'], MOTIF_PERIME)
        self.assertIsNone(ligne['p50_kwh'])

    def _variante(self, nom, layout):
        return CalepinageVariante.objects.create(
            company=self.calepinage.company, calepinage=self.calepinage,
            nom=nom, roof_layout=layout,
            resultat=copy.deepcopy(self.calepinage.resultat))

    def test_variante_modifiee_non_simulee(self):
        intacte = self._variante('Intacte',
                                 copy.deepcopy(self.calepinage.roof_layout))
        modifiee = copy.deepcopy(self.calepinage.roof_layout)
        modifiee['zones'][0]['geometry']['count'] += 1
        changee = self._variante('Modifiée', modifiee)
        with patch_materiel():
            reponse = self.api.get(
                f'{BASE}{self.calepinage.pk}/comparer/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = {ligne['id']: ligne for ligne in reponse.data['lignes']}
        self.assertTrue(lignes[intacte.pk]['simulee'])
        self.assertFalse(lignes[changee.pk]['simulee'])
        self.assertIsNone(lignes[changee.pk]['production']['p50_kwh'])
