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
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.calepinage.serializers_pertes import PostesDePertesSerializer
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

from .test_calx5_simulation import LAYOUT

BASE = '/api/django/calepinage/calepinages/'

IAM = {'poste': 'iam', 'libelle': 'Incidence (IAM)', 'pct': 3.0,
       'source': 'saisie', 'reference': 'relevé bureau d’études'}


def _contrat_pertes():
    chemin = Path(__file__).resolve().parents[1] / 'contract_samples' / 'calepinage_pertes.json'
    return json.loads(chemin.read_text(encoding='utf-8'))


class ReglageSocieteParPosteTest(SimpleTestCase):
    """ACAL979 — le résumé du réglage société d'un poste (lecture pure)."""

    def test_ashrae_b0_et_societe_vide(self):
        from apps.calepinage.views.simulation import _societe_des_postes

        rempli = _societe_des_postes({
            'modele_iam': {'valeur': 'ashrae', 'source': 'societe'},
            'b0_iam': {'valeur': 0.05, 'source': 'societe'}})
        self.assertEqual(rempli['iam'], {
            'cles': ['modele_iam', 'b0_iam'], 'renseigne': True,
            'resume': 'ASHRAE, b0 = 0,05', 'source': 'societe'})
        vide = _societe_des_postes({})
        self.assertEqual(vide['iam'], {'cles': ['modele_iam', 'b0_iam'], 'renseigne': False,
                                       'resume': '', 'source': None})
        # Une valeur sans source n'est pas un réglage (même règle que `etapes.reglage`).
        self.assertFalse(_societe_des_postes({'mismatch_fabricant_pct': {'valeur': 2}})['mismatch']['renseigne'])
        self.assertEqual(_societe_des_postes({'mismatch_fabricant_pct': {'valeur': 2, 'source': 'societe'}})
                         ['mismatch']['resume'], '2 %')

    def test_chaque_cle_existe_au_registre(self):
        from apps.calepinage.services.parametres_cles import SECTION_SIMULATION, registre
        from apps.calepinage.services.pertes import CATALOGUE_PAR_POSTE, CLES_SOCIETE_PAR_POSTE

        connues = registre(SECTION_SIMULATION)
        for poste, cles in CLES_SOCIETE_PAR_POSTE.items():
            self.assertIn(poste, CATALOGUE_PAR_POSTE, poste)
            for cle, _court in cles:
                self.assertIn(cle, connues, (poste, cle))


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

    def test_regles_liees_409_forme_publiee_400(self):
        """ENF11 (fuzz 01/11) : doublon, poste sans valeur, forçage sans motif
        = 409 (le schéma ne les dit pas) ; 11 mois, pct >= 100, source
        inconnue = 400 (publiés)."""
        url = f'{BASE}{self.calepinage.pk}/enregistrer-pertes/'
        for postes in (
                [dict(IAM), dict(IAM)],
                [{'poste': 'iam'}],
                [{'poste': 'iam', 'pct': 1.0, 'force': True}]):
            reponse = self.api.post(url, {'pertes': postes}, format='json')
            self.assertEqual(reponse.status_code, 409, (postes, reponse.data))
        for postes in (
                [{'poste': 'salissure', 'mensuel': [1.0] * 11}],
                [{'poste': 'iam', 'pct': 100}],
                [{'poste': 'iam', 'pct': 1.0, 'source': 'inconnue'}]):
            reponse = self.api.post(url, {'pertes': postes}, format='json')
            self.assertEqual(reponse.status_code, 400, (postes, reponse.data))
        schema = PostesDePertesSerializer().fields['pertes'].child.fields
        self.assertEqual(schema['mensuel'].min_length, 12)
        self.assertEqual(schema['mensuel'].max_length, 12)

    def test_acal979_catalogue_cite_le_reglage_societe(self):
        """ACAL979 — société à ashrae et b0 = 0,05 ⇒ `societe.resume` servi
        sur la ligne `iam` du catalogue ; un poste sans clé société porte
        `societe: null` ; la ligne a la forme du contrat."""
        from apps.calepinage.services.parametres import enregistrer_parametres

        enregistrer_parametres(self.calepinage.company, {'simulation': {
            'modele_iam': {'valeur': 'ashrae', 'source': 'societe', 'reference': 'PVsyst'},
            'b0_iam': {'valeur': 0.05, 'source': 'societe', 'reference': 'PVsyst'}}})

        catalogue = {e['poste']: e for e in self._get('pertes')['catalogue']}

        self.assertEqual(catalogue['iam']['societe']['resume'], 'ASHRAE, b0 = 0,05')
        self.assertTrue(catalogue['iam']['societe']['renseigne'])
        self.assertEqual(catalogue['iam']['societe']['cles'], ['modele_iam', 'b0_iam'])
        self.assertFalse(catalogue['salissure']['societe']['renseigne'])
        self.assertIsNone(catalogue['ohmique_dc']['societe'])
        contrat = _contrat_pertes()['exemple']['catalogue']
        self.assertEqual(set(catalogue['iam']), set(contrat[0]))
        self.assertEqual(set(catalogue['iam']['societe']), set(contrat[0]['societe']))

    def test_corps_formulaire_refuse_415_pas_400_trompeur(self):
        # CI #997 fuzz : le schéma ne déclare que du JSON (liste d'objets) ;
        # un corps `pertes=a&pertes=b` n'est pas « une requête valide refusée ».
        reponse = self.api.post(
            f'{BASE}{self.calepinage.pk}/enregistrer-pertes/',
            'pertes=poste&pertes=mensuel',
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(reponse.status_code, 415, reponse.content[:300])
