"""ACAL126 — chaque refus de simulation est NOMMÉ et ATTEIGNABLE.

Constats C-ACAL-074 / C-ACAL-067. Avant : ``POST simuler/`` rendait 202 pour
une société sans mode météo (la tâche échouait ensuite, en texte libre) ; une
seule température saisie faisait un 500 ; un σ saisi illisible, un horizon
illisible ou PVGIS indisponible pour un pan levaient une exception brute ; et
le job en échec n'avait AUCUNE charge en cache — l'écran ne savait pas quel
champ pointer.

Désormais : pré-vérification 400 dans la vue par LA fonction de la
simulation (``verifier_simulable``), exceptions d'entrée converties en
``SimulationRefusee``, échec de job structuré ``elements[0] = {statut,
champ, motif}`` servi par ``GET moteur/resultat/<job>/``.

Run :
    python manage.py test apps.calepinage.tests.test_acal_refus_simulation -v2
"""
from __future__ import annotations

import copy
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.calepinage.services.pvgis_serie import EntreeInvalide
from apps.calepinage.services.simulation import (
    SimulationRefusee, construire_contexte, simuler_calepinage,
)

from .test_acal_multi_pans import _layout, _zone
from .test_calx5_simulation import (
    LAYOUT, MATERIEL, REGLAGES, _Calepinage, _ClientRejoue, _reponse_meteo,
)


class _ClientQuiRefuseLeSecondPan:
    """Un client double : le SECOND plan demandé est refusé (horizon
    illisible côté appel), comme ``ClientPvgis`` le ferait."""

    def __init__(self):
        self.demandes = []

    def serie_irradiance(self, **parametres):
        self.demandes.append(parametres)
        if len(self.demandes) > 1:
            raise EntreeInvalide(
                "Profil d'horizon illisible : 12 hauteurs attendues.",
                champ='horizonProfile')
        return _reponse_meteo()


class RefusDuServiceTest(SimpleTestCase):

    def test_sigma_illisible_refus_nomme(self):
        reglages = copy.deepcopy(REGLAGES)
        reglages['simulation']['sigma_modele_pct'] = {
            'valeur': '2,5', 'source': 'societe', 'reference': 'essai'}

        with self.assertRaises(SimulationRefusee) as refus:
            simuler_calepinage(_Calepinage(), client=_ClientRejoue(),
                               materiel=MATERIEL, reglages=reglages,
                               enregistrer=False)
        self.assertEqual(refus.exception.champ, 'sigma_modele_pct')
        self.assertTrue(refus.exception.motif)

    def test_entree_invalide_multi_pans_nommee(self):
        calepinage = _Calepinage(layout=_layout(_zone(1, 8, 90.0),
                                                _zone(2, 8, 270.0)))
        with self.assertRaises(SimulationRefusee) as refus:
            simuler_calepinage(calepinage,
                               client=_ClientQuiRefuseLeSecondPan(),
                               materiel=MATERIEL, reglages=REGLAGES,
                               enregistrer=False)
        self.assertEqual(refus.exception.champ, 'horizonProfile')
        self.assertIn('horizon', refus.exception.motif)

    def test_temperature_partielle_refus_nomme(self):
        calepinage = _Calepinage(resultat={
            'entree_electrique': {'temperature_min_c': -5.0}})
        with self.assertRaises(SimulationRefusee) as refus:
            construire_contexte(calepinage, materiel=MATERIEL,
                                reglages=REGLAGES)
        self.assertEqual(refus.exception.champ, 'temperature_max_c')


class _BaseApi(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.roles.models import Role
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
        from authentication.models import Company

        self.societe = Company.objects.create(nom='ACAL126', slug='acal126')
        role = Role.objects.create(company=self.societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = get_user_model().objects.create_user(
            username='acal126', password='x', company=self.societe,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        lead = Lead.objects.create(company=self.societe, nom='Toiture 126')
        self.calepinage = Calepinage.objects.create(
            company=self.societe, lead_id=lead.pk, titre='Refus 126',
            roof_layout=copy.deepcopy(LAYOUT))
        self.url = (f'/api/django/calepinage/calepinages/'
                    f'{self.calepinage.pk}/simuler/')

    def _poster(self):
        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=MATERIEL), \
                mock.patch('core.jobs.submit') as soumettre:
            reponse = self.api.post(self.url, {}, format='json')
        return reponse, soumettre


class PreVerificationApiTest(_BaseApi):

    def test_sans_mode_meteo_400_nomme(self):
        # La société n'a RIEN réglé : aucun mode météo.
        reponse, soumettre = self._poster()

        self.assertEqual(reponse.status_code, 400, reponse.content[:300])
        self.assertIn('parametres.simulation.mode_meteo', reponse.data)
        self.assertTrue(reponse.data['parametres.simulation.mode_meteo'][0])
        soumettre.assert_not_called()

    def test_temperature_partielle_400_pas_500(self):
        self.calepinage.resultat = {
            'entree_electrique': {'temperature_min_c': -5.0}}
        self.calepinage.save(update_fields=['resultat'])

        reponse, soumettre = self._poster()

        self.assertEqual(reponse.status_code, 400, reponse.content[:300])
        self.assertIn('temperature_max_c', reponse.data)
        soumettre.assert_not_called()


class EchecDeJobStructureTest(_BaseApi):

    def _job(self):
        from core.models import BackgroundJob

        from apps.calepinage.tasks import KIND_CALEPINAGE

        return BackgroundJob.objects.create(
            company=self.societe, user=self.user, kind=KIND_CALEPINAGE,
            statut=BackgroundJob.STATUT_QUEUED)

    def test_sigma_illisible_echec_structure_avec_champ(self):
        from apps.calepinage.tasks import simuler_calepinage as tache

        job = self._job()
        reglages = copy.deepcopy(REGLAGES)
        reglages['simulation']['sigma_modele_pct'] = {
            'valeur': '2,5', 'source': 'societe', 'reference': 'essai'}
        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=MATERIEL), \
                mock.patch(
                    'apps.calepinage.services.electrique.parametres_societe',
                    return_value=reglages), \
                mock.patch('apps.calepinage.services.simulation.ClientPvgis',
                           return_value=_ClientRejoue()):
            issue = tache(job_id=job.pk, company_id=self.societe.pk,
                          calepinage_id=self.calepinage.pk, forcer=True)

        job.refresh_from_db()
        self.assertEqual(issue['statut'], 'failed')
        self.assertEqual(issue['champ'], 'sigma_modele_pct')
        self.assertEqual(job.statut, job.STATUT_FAILED)
        from apps.calepinage.tasks import resultat_du_job

        element = resultat_du_job(job)['elements'][0]
        self.assertEqual(element['statut'], 'failed')
        self.assertEqual(element['champ'], 'sigma_modele_pct')
        self.assertTrue(element['motif'])

    def test_suivi_job_expose_champ_et_motif(self):
        from apps.calepinage.tasks import simuler_calepinage as tache

        job = self._job()
        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=MATERIEL):
            tache(job_id=job.pk, company_id=self.societe.pk,
                  calepinage_id=self.calepinage.pk, forcer=True)

        reponse = self.api.get(
            f'/api/django/calepinage/moteur/resultat/{job.pk}/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        self.assertEqual(reponse.data['statut'], 'failed')
        element = reponse.data['elements'][0]
        self.assertEqual(element['statut'], 'failed')
        self.assertEqual(element['champ'],
                         'parametres.simulation.mode_meteo')
        self.assertTrue(element['motif'])
