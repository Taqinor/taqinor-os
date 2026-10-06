"""ACAL134 — « tout recalculer » après un changement de réglage société.

Constat C-ACAL-068 : un réglage société modifié périme TOUTES les
simulations (l'empreinte de simulation porte les réglages, D-ACAL-8), et
rien ne permettait de les relancer autrement qu'une par une.

``POST /api/django/calepinage/parametres/recalculer-simulations/`` soumet,
pour chaque calepinage NON archivé de la société de l'appelant dont le
résultat porte une simulation, le MÊME travail de fond que ``POST simuler/``
(sans forcer : un calcul encore frais se court-circuite).

Base de test réelle, ``core.jobs.submit`` réel (les ``BackgroundJob`` sont
créés) ; seul le transport Celery (``.delay``) est neutralisé — il lancerait
la simulation, qui n'est pas le sujet ici.

Run :
    python manage.py test apps.calepinage.tests.test_acal_recalculer_tout -v2
"""
from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company
from core.models import BackgroundJob

URL = '/api/django/calepinage/parametres/recalculer-simulations/'
SIMULE = {'simulation': {'hash_entree': 'a' * 64,
                         'calcule_le': '2026-10-01T10:00:00Z'}}


class RecalculerToutTest(TestCase):

    def setUp(self):
        self.societe = Company.objects.create(nom='ACAL134', slug='acal134')
        self.autre = Company.objects.create(nom='Voisine', slug='acal134-v')
        role = Role.objects.create(company=self.societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = get_user_model().objects.create_user(
            username='acal134', password='x', company=self.societe,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        lead = Lead.objects.create(company=self.societe, nom='Toiture 134')
        lead_autre = Lead.objects.create(company=self.autre, nom='Voisin')
        self.simules = [
            Calepinage.objects.create(company=self.societe, lead_id=lead.pk,
                                      titre=f'Simulé {rang}', resultat=SIMULE)
            for rang in range(3)]
        self.jamais = Calepinage.objects.create(
            company=self.societe, lead_id=lead.pk, titre='Jamais simulé')
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=lead_autre.pk, titre='Voisin',
            resultat=SIMULE)

    def _poster(self):
        with mock.patch('apps.calepinage.tasks.simuler_calepinage.delay') \
                as envoi:
            reponse = self.api.post(URL, {}, format='json')
        return reponse, envoi

    def test_soumet_un_job_par_calepinage_simule(self):
        reponse, envoi = self._poster()

        self.assertEqual(reponse.status_code, 202, reponse.content[:300])
        self.assertEqual(reponse.data['soumis'], 3)
        self.assertEqual(reponse.data['reste'], 0)
        self.assertEqual(sorted(job['calepinage'] for job in
                                reponse.data['jobs']),
                         sorted(c.pk for c in self.simules))
        self.assertEqual(envoi.call_count, 3)
        for appel in envoi.call_args_list:
            self.assertIs(appel.kwargs['forcer'], False)
            self.assertEqual(appel.kwargs['nature'], 'simulation')
        self.assertEqual(
            BackgroundJob.objects.filter(company=self.societe).count(), 3)

    def test_autre_societe_jamais_touchee(self):
        reponse, envoi = self._poster()

        ids = {job['calepinage'] for job in reponse.data['jobs']}
        self.assertNotIn(self.etranger.pk, ids)
        self.assertNotIn(self.jamais.pk, ids)
        self.assertFalse(
            BackgroundJob.objects.filter(company=self.autre).exists())
        for appel in envoi.call_args_list:
            self.assertEqual(appel.kwargs['company_id'], self.societe.pk)

    def test_archive_exclu(self):
        from apps.calepinage.services.archivage import archiver

        archiver(self.simules[0], user=self.user)

        reponse, _envoi = self._poster()

        ids = {job['calepinage'] for job in reponse.data['jobs']}
        self.assertNotIn(self.simules[0].pk, ids)
        self.assertEqual(reponse.data['soumis'], 2)

    def test_plafond_par_appel_dit_ce_qui_reste(self):
        from apps.calepinage.services.simulation import (
            recalculer_simulations_societe,
        )

        with mock.patch('apps.calepinage.tasks.simuler_calepinage.delay'):
            rendu = recalculer_simulations_societe(self.societe, self.user,
                                                   plafond=2)
        self.assertEqual(rendu['soumis'], 2)
        self.assertEqual(rendu['reste'], 1)
