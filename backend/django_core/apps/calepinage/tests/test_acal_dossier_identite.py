# -*- coding: utf-8 -*-
"""ACAL241 — le préremplissage réglementaire lit client et adresse par les
fonctions EXISTANTES du module (``client_du_calepinage``,
``selectors.contexte_geographique``).

LE CONSTAT (C-ACAL-135) : ``infos_du_calepinage`` lisait
``calepinage.client`` seul — un calepinage né d'un lead (client nul) sortait
avec ``client_nom`` et ``adresse`` vides, et un calepinage à client ET lead
imprimait l'adresse de FACTURATION du client au lieu de celle du site.

Base réelle, calepinages réels, aucun mock.
"""
from __future__ import annotations

from apps.calepinage.models import Calepinage
from apps.calepinage.services.reglementaire import infos_du_calepinage
from apps.crm.models import Client, Lead

from .test_api_liste import BaseApiCalepinage


class IdentiteDossierTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.lead_site = Lead.objects.create(
            company=self.company, nom='Alami', adresse='12 rue X',
            ville='Rabat')

    def test_calepinage_de_lead_sans_client_preremplit_nom_et_adresse(self):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_site.pk, titre='Villa')

        infos = infos_du_calepinage(calepinage)

        self.assertEqual(infos['client_nom'], 'Alami')
        self.assertEqual(infos['adresse'], '12 rue X, Rabat')

    def test_adresse_du_site_prime_sur_l_adresse_de_facturation(self):
        client = Client.objects.create(company=self.company, nom='Alami SARL',
                                       adresse='Bd de la Facturation')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_site.pk, client=client,
            titre='Villa')

        infos = infos_du_calepinage(calepinage)

        self.assertEqual(infos['adresse'], '12 rue X, Rabat')
        self.assertEqual(infos['client_nom'], 'Alami SARL')

    def test_sans_lead_ni_client_reste_a_completer(self):
        # La base exige un lead OU un client : un lead INTROUVABLE (autre
        # société / supprimé) est le seul « sans lead ni client » possible.
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=999999, titre='Sans rattachement')

        infos = infos_du_calepinage(calepinage)

        self.assertIsNone(infos['client_nom'])
        self.assertIsNone(infos['adresse'])
