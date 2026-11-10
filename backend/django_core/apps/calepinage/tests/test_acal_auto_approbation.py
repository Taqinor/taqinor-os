# -*- coding: utf-8 -*-
"""ACAL303 (D-ACAL-11) — séparation des tâches : qui a conçu ou porte la
conception ne l'approuve pas.

LE CONSTAT (C-ACAL-095, PLAUSIBLE → oracle) : ``services/approbation.decider``
écrivait ``decide_par_id`` sans comparer le décideur à l'auteur : un Directeur
(gérer + approuver) concevait puis approuvait SA conception (200,
``decide_par_id == cree_par_id``). Oracle rouge d'abord : ce test était ROUGE
sur le commit pré-correctif (aucune garde dans ``decider``).

Désormais : l'auteur du calepinage, son responsable et l'auteur de sa
DERNIÈRE version reçoivent 409 ``{decision: …}`` sur un ACCORD, RIEN n'est
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
        if corps.get('decision') == 'approuve':  # ACON23 — l'empreinte VUE
            corps.setdefault('empreinte', Calepinage.objects.get(
                pk=calepinage.pk).layout_hash or '')
        return (api or self.api).post(
            f'{url_detail(calepinage.pk)}approbation/', corps, format='json')

    def _notes(self, calepinage):
        return Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk).count()

    def _refus_sans_ecriture(self, calepinage):
        avant = self._notes(calepinage)
        reponse = self._decider(calepinage, decision='approuve')
        self.assertEqual(reponse.status_code, 409, reponse.data)
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

    def test_auteur_d_une_version_ancienne_ou_d_une_variante_refuse(self):
        """ACON22 — D a conçu les versions 1-6 (C la 7e) ou la variante
        retenue par C : D ne l'approuve pas ; E (tiers) l'approuve."""
        from apps.calepinage.services.variantes import (
            creer_variante, retenir_variante,
        )

        c = User.objects.create_user(username='acon22_c', password='x',
                                     company=self.company, role=self.role)
        cas_a = self._calepinage(cree_par=c, responsable=c)
        for rang in range(1, 7):
            CalepinageVersion.objects.create(
                company=self.company, calepinage=cas_a, libelle=f'V{rang}',
                roof_layout=DESSIN, cree_par=self.user)
        CalepinageVersion.objects.create(
            company=self.company, calepinage=cas_a, libelle='V7',
            roof_layout=DESSIN, cree_par=c)
        self._refus_sans_ecriture(cas_a)

        cas_b = self._calepinage(cree_par=c, responsable=c)
        # ``retenue`` ne s'écrit que par le service de variantes (CAL9) : D
        # crée la variante, C la retient (sans réécrire la conception).
        variante = creer_variante(cas_b, nom='Option B', roof_layout=DESSIN,
                                  user=self.user)
        retenir_variante(variante, user=c, appliquer=False)
        self._refus_sans_ecriture(cas_b)

        reponse = self._decider(cas_b, api=self.api_tiers,
                                decision='approuve')
        self.assertEqual(reponse.status_code, 200, reponse.data)

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
                                {'decision': 'approuve',
                                 'empreinte': calepinage.layout_hash or ''},
                                format='json')

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
                                {'decision': 'approuve',
                                 'empreinte': calepinage.layout_hash or ''},
                                format='json')

        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data, {'decision': MESSAGE_AUTO_APPROBATION})
