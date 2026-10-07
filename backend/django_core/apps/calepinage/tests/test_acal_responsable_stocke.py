# -*- coding: utf-8 -*-
"""ACAL297 — le responsable d'un calepinage est STOCKÉ à la création.

LE CONSTAT (C-ACAL-014)
-----------------------
Aucune porte ne posait ``Calepinage.responsable`` : le détail et la liste
« retombaient » à la LECTURE sur le propriétaire du lead, mais le filtre
``?responsable=`` et la vue restreinte lisaient la COLONNE (NULL) — le
propriétaire du lead voyait son nom affiché… et ne retrouvait pas le
calepinage. Désormais : UNE fonction (``creation.responsable_par_defaut``)
pour toutes les portes, la colonne publiée telle quelle, et la migration 0030
rattrape l'existant.

Base réelle, portes réelles (services et HTTP), aucun mock du CRM.
"""
from __future__ import annotations

import importlib

from django.apps import apps as registre
from django.contrib.auth import get_user_model

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.calepinage.permissions import CAL_GERER, CAL_VOIR
from apps.calepinage.selectors import CLE_VUE_RESTREINTE
from apps.calepinage.services.creation import (
    creer_pour_client, obtenir_ou_creer_pour_devis,
    ouvrir_ou_creer_pour_lead,
)
from apps.calepinage.services.reprise_public import reprendre_trace_public
from apps.calepinage.services.variantes import dupliquer
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.ventes.models import Devis

from .test_api_liste import URL, BaseApiCalepinage, url_detail

User = get_user_model()
MIGRATION = importlib.import_module(
    'apps.calepinage.migrations.0030_acal297_responsable_stocke')
CONTOUR = [[33.5, -7.6], [33.5, -7.5999], [33.5001, -7.5999],
           [33.5001, -7.6]]


class ResponsableStockeTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        # B : voit et gère, SANS approuver (un approbateur voit tout, la vue
        # restreinte ne s'applique pas à lui).
        role_b = Role.objects.create(company=self.company, nom='Commercial',
                                     permissions=[CAL_VOIR, CAL_GERER])
        self.proprietaire = User.objects.create_user(
            username='acal297_b', password='x', company=self.company,
            role=role_b)
        self.api_b = self._client(self.proprietaire)
        self.lead_b = Lead.objects.create(company=self.company,
                                          nom='Toiture B',
                                          owner=self.proprietaire)

    def _lead(self, nom, **champs):
        return Lead.objects.create(company=self.company, nom=nom,
                                   owner=self.proprietaire, **champs)

    def test_chaque_porte_stocke_le_proprietaire_du_lead(self):
        par_lead, _cree = ouvrir_ou_creer_pour_lead(
            self.lead_b.pk, self.company, user=self.user)
        self.assertEqual(par_lead.responsable_id, self.proprietaire.pk)

        reponse = self.api.post(URL, {'lead': self._lead('HTTP').pk},
                                format='json')
        self.assertIn(reponse.status_code, (200, 201), reponse.data)
        par_http = Calepinage.objects.get(pk=reponse.data['id'])
        self.assertEqual(par_http.responsable_id, self.proprietaire.pk)

        devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            lead=self._lead('Devis'), reference='DEV-ACAL297')
        par_devis, _c = obtenir_ou_creer_pour_devis(devis.pk, self.company,
                                                    user=self.user)
        self.assertEqual(par_devis.responsable_id, self.proprietaire.pk)

        copie = dupliquer(par_lead, user=self.user,
                          lead_id=self._lead('Copie').pk, client_id=None)
        self.assertEqual(copie.responsable_id, self.proprietaire.pk)

        # Un responsable EXPLICITE reste prioritaire.
        explicite, _c = ouvrir_ou_creer_pour_lead(
            self._lead('Explicite').pk, self.company, user=self.user,
            responsable=self.user)
        self.assertEqual(explicite.responsable_id, self.user.pk)
        # Pas de lead : aucun responsable deviné.
        sur_client = creer_pour_client(self.client_a.pk, self.company,
                                       user=self.user)
        self.assertIsNone(sur_client.responsable_id)

    def test_reprise_publique_sans_auteur_a_un_responsable(self):
        lead = self._lead('Public', roof_outline=CONTOUR)

        calepinage = reprendre_trace_public(lead.pk, self.company, user=None)

        self.assertIsNotNone(calepinage)
        self.assertIsNone(calepinage.cree_par_id)
        self.assertEqual(calepinage.responsable_id, self.proprietaire.pk)

    def test_filtre_responsable_rend_le_responsable_affiche(self):
        calepinage, _c = ouvrir_ou_creer_pour_lead(
            self.lead_b.pk, self.company, user=self.user)

        reponse = self.api.get(URL, {'responsable': self.proprietaire.pk})

        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = self._lignes(reponse)
        self.assertEqual([ligne['id'] for ligne in lignes], [calepinage.pk])
        self.assertEqual(lignes[0]['responsable'], self.proprietaire.pk)

    def test_vue_restreinte_montre_au_proprietaire_du_lead(self):
        calepinage, _c = ouvrir_ou_creer_pour_lead(
            self.lead_b.pk, self.company, user=self.user)
        parametres, _cree = ParametresCalepinage.objects.get_or_create(
            company=self.company)
        presets = dict(getattr(parametres, 'presets', None) or {})
        presets[CLE_VUE_RESTREINTE] = True
        parametres.presets = presets
        parametres.save()

        reponse = self.api_b.get(URL)

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIn(calepinage.pk,
                      [ligne['id'] for ligne in self._lignes(reponse)])

    def test_serialiseur_publie_la_colonne(self):
        # Un calepinage ANCIEN, colonne vide : plus aucun repli à la lecture.
        ancien = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_b.pk, titre='Ancien')

        detail = self.api.get(url_detail(ancien.pk)).data
        self.assertIsNone(detail['responsable'])
        ligne = next(rang for rang in self._lignes(self.api.get(URL))
                     if rang['id'] == ancien.pk)
        self.assertIsNone(ligne['responsable'])

        # Aller-retour : PATCH {titre} ne fabrique aucun responsable.
        posee, _c = ouvrir_ou_creer_pour_lead(
            self._lead('AR').pk, self.company, user=self.user)
        avant = self.api.get(url_detail(posee.pk)).data['responsable']
        self.api.patch(url_detail(posee.pk), {'titre': 'x'}, format='json')
        posee.refresh_from_db()
        self.assertEqual(self.api.get(url_detail(posee.pk)).data['responsable'],
                         avant)
        self.assertEqual(avant['id'], posee.responsable_id)

    def test_migration_remplit_les_responsables_nuls(self):
        ancien = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_b.pk, titre='Ancien')
        sans_proprietaire = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Sans')
        deja = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_b.pk, titre='Déjà',
            responsable=self.user)

        MIGRATION.stocker_les_responsables(registre, None)

        for calepinage in (ancien, sans_proprietaire, deja):
            calepinage.refresh_from_db()
        self.assertEqual(ancien.responsable_id, self.proprietaire.pk)
        self.assertIsNone(sans_proprietaire.responsable_id)
        self.assertEqual(deja.responsable_id, self.user.pk)
