# -*- coding: utf-8 -*-
"""ACAL303 (D-ACAL-11) — séparation des tâches : qui a conçu ou porte la
conception ne l'approuve pas.

LE CONSTAT (C-ACAL-095, PLAUSIBLE → oracle) : ``services/approbation.decider``
écrivait ``decide_par_id`` sans comparer le décideur à l'auteur : un Directeur
(gérer + approuver) concevait puis approuvait SA conception (200,
``decide_par_id == cree_par_id``). Oracle rouge d'abord : ce test était ROUGE
sur le commit pré-correctif (aucune garde dans ``decider``).

Désormais : l'auteur du calepinage, son responsable et l'auteur de sa
DERNIÈRE version reçoivent 400 ``{decision: …}`` sur un ACCORD, RIEN n'est
écrit (approbation et chatter inchangés) ; un REFUS reste admis ; un tiers
approuve. Rôles réels, base réelle, route HTTP réelle, aucun mock.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.approbation import (
    MESSAGE_AUTO_APPROBATION, MENTION_SEUL_APPROBATEUR,
)
from apps.records.models import Activity

from .test_api_liste import BaseApiCalepinage, url_detail

User = get_user_model()
DESSIN = {'zones': [{'id': 'z1', 'label': 'Pan Sud',
                     'vertices': [[0, 0], [10, 0], [10, 6]]}]}


class AutoApprobationTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        # D = ``self.user`` (Directeur : gérer ET approuver) ; E = un second
        # approbateur, étranger à la conception.
        self.tiers = User.objects.create_user(
            username='acal303_e', password='x', company=self.company,
            role=self.role)
        self.api_tiers = self._client(self.tiers)

    def _calepinage(self, **champs):
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL303',
            roof_layout=DESSIN, **champs)

    def _decider(self, calepinage, api=None, **corps):
        return (api or self.api).post(
            f'{url_detail(calepinage.pk)}approbation/', corps, format='json')

    def _notes(self, calepinage):
        return Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk).count()

    def _refus_sans_ecriture(self, calepinage):
        avant = self._notes(calepinage)
        reponse = self._decider(calepinage, decision='approuve')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual(reponse.data, {'decision': MESSAGE_AUTO_APPROBATION})
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.approbation)
        self.assertEqual(self._notes(calepinage), avant)
        lecture = self.api.get(f'{url_detail(calepinage.pk)}approbation/')
        self.assertIsNone(lecture.data['etat'])

    def test_auteur_ne_peut_pas_approuver(self):
        self._refus_sans_ecriture(self._calepinage(cree_par=self.user))

    def test_responsable_ne_peut_pas_approuver(self):
        self._refus_sans_ecriture(self._calepinage(responsable=self.user))

    def test_auteur_derniere_version_ne_peut_pas_approuver(self):
        calepinage = self._calepinage()
        CalepinageVersion.objects.create(
            company=self.company, calepinage=calepinage, libelle='V1',
            roof_layout=DESSIN, cree_par=self.user)
        self._refus_sans_ecriture(calepinage)

    def test_auteur_peut_refuser(self):
        calepinage = self._calepinage(cree_par=self.user)

        reponse = self._decider(calepinage, decision='refuse', motif='x')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['etat'], 'refuse')

    def test_tiers_approuve(self):
        calepinage = self._calepinage(cree_par=self.user,
                                      responsable=self.user)

        reponse = self._decider(calepinage, api=self.api_tiers,
                                decision='approuve')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['etat'], 'approuve')
        self.assertEqual(reponse.data['decide_par']['id'], self.tiers.pk)


class SeulApprobateurTest(BaseApiCalepinage):
    """Décision fondateur 07/10/2026 — l'auto-approbation est permise au SEUL
    approbateur actif de la société, et journalisée « auto-approuvé (seul
    approbateur) ». ``self.user`` (Directeur) est l'unique approbateur de la
    société : ``user_sans`` (Technicien) n'approuve pas, ``user_autre`` est
    d'une autre société."""

    def _calepinage(self):
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Seul',
            roof_layout=DESSIN, cree_par=self.user, responsable=self.user)

    def _approuver_et_verifier_journal(self):
        calepinage = self._calepinage()

        reponse = self.api.post(f'{url_detail(calepinage.pk)}approbation/',
                                {'decision': 'approuve'}, format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['etat'], 'approuve')
        notes = Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk, kind='note',
            body__contains=MENTION_SEUL_APPROBATEUR)
        self.assertEqual(notes.count(), 1)
        self.assertEqual(MENTION_SEUL_APPROBATEUR,
                         'auto-approuvé (seul approbateur)')

    def test_seul_approbateur_s_auto_approuve_journalise(self):
        self._approuver_et_verifier_journal()

    def test_autre_approbateur_inactif_ne_compte_pas(self):
        User.objects.create_user(
            username='acal303_inactif', password='x', company=self.company,
            role=self.role, is_active=False)
        self._approuver_et_verifier_journal()

    def test_autre_approbateur_actif_refuse_toujours(self):
        User.objects.create_user(
            username='acal303_actif', password='x', company=self.company,
            role=self.role)
        calepinage = self._calepinage()

        reponse = self.api.post(f'{url_detail(calepinage.pk)}approbation/',
                                {'decision': 'approuve'}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual(reponse.data, {'decision': MESSAGE_AUTO_APPROBATION})
