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

    def test_calepinage_fige_exclu(self):
        """ACON85 — le calepinage d'un devis ACCEPTÉ n'est jamais soumis :
        aucun job, ``soumis`` ne le compte pas."""
        from apps.crm.models import Client
        from apps.ventes.models import Devis

        client = Client.objects.create(company=self.societe, nom='C ACON85')
        devis = Devis.objects.create(company=self.societe, client=client,
                                     reference='DEV-ACON85-1')
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ACCEPTE)
        fige = self.simules[0]
        Calepinage.objects.filter(pk=fige.pk).update(devis=devis)

        reponse, envoi = self._poster()

        self.assertEqual(reponse.status_code, 202, reponse.content[:300])
        self.assertEqual(reponse.data['soumis'], 2)
        self.assertNotIn(fige.pk, {job['calepinage']
                                   for job in reponse.data['jobs']})
        self.assertEqual(envoi.call_count, 2)

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

    def test_commercial_ne_voit_que_les_jobs_de_sa_portee(self):
        """ACAL1247 (D-ALEC-4) — le travail lancé reste toute la société ; la
        réponse et le suivi ne montrent que ce que le rôle lit, un compte
        pour le reste ; le suivi d'un job hors portée répond 404."""
        from core import cache as cache_tenant

        from apps.calepinage.tasks import cle_job
        from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

        role = Role.objects.create(company=self.societe, nom='Commercial',
                                   permissions=list(COMMERCIAL_PERMISSIONS))
        rec_b = get_user_model().objects.create_user(
            username='acal1247_b', password='x', company=self.societe,
            role=role)
        lead_b = Lead.objects.create(company=self.societe, nom='De B',
                                     owner=rec_b)
        siens = [Calepinage.objects.create(
            company=self.societe, lead_id=lead_b.pk, titre=f'B {rang}',
            cree_par=rec_b, resultat=SIMULE) for rang in range(2)]
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(rec_b)}')

        reponse, envoi = self._poster()

        self.assertEqual(reponse.status_code, 202, reponse.content[:300])
        self.assertEqual(reponse.data['soumis'], 5)
        self.assertEqual(reponse.data['hors_portee'], 3)
        self.assertEqual(sorted(j['calepinage'] for j in reponse.data['jobs']),
                         sorted(c.pk for c in siens))
        self.assertEqual(envoi.call_count, 5)  # le travail : toute la société
        for rang, appel in enumerate(envoi.call_args_list):
            job = BackgroundJob.objects.get(pk=appel.kwargs['job_id'])
            pk = appel.kwargs['calepinage_id']
            # Succès (résumé) ou échec publié (motif nommé), comme tasks.py.
            charge = ({'elements': [], 'resultat': {'calepinage': pk}}
                      if rang % 2 else
                      {'elements': [{'index': 0, 'repere': str(pk),
                                     'statut': 'failed', 'champ': 'meteo',
                                     'motif': 'Mode météo non saisi.',
                                     'resultat': None}], 'resultat': None})
            cache_tenant.set(self.societe.pk, cle_job(job.pk), charge)
            job.marquer_termine(cle_job(job.pk))
            suivi = self.api.get(
                f'/api/django/calepinage/moteur/resultat/{job.pk}/')
            attendu = 200 if pk in {c.pk for c in siens} else 404
            self.assertEqual(suivi.status_code, attendu, suivi.data)
            self.assertEqual(self.api.get(
                f'/api/django/calepinage/moteur/resultat/{job.pk}/')
                .status_code, attendu, 'relire le suivi : même réponse')

    def test_plafond_par_appel_dit_ce_qui_reste(self):
        from apps.calepinage.services.simulation import (
            recalculer_simulations_societe,
        )

        with mock.patch('apps.calepinage.tasks.simuler_calepinage.delay'):
            rendu = recalculer_simulations_societe(self.societe, self.user,
                                                   plafond=2)
        self.assertEqual(rendu['soumis'], 2)
        self.assertEqual(rendu['reste'], 1)
