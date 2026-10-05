# -*- coding: utf-8 -*-
"""ACAL157 — la saisie de raccordement PROPOSE ce que le lead sait déjà.

``GET raccordement/`` porte ``proposition_lead`` = la puissance souscrite et
le mono/triphasé du LEAD (``source: 'lead'``), sans jamais les écrire : ni
dans le lead, ni dans ``resultat``. La valeur ne devient une saisie que par
un ``POST`` explicite. Base RÉELLE, lecture par ``apps.crm.selectors``.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.models import Calepinage
from apps.calepinage.services.raccordement import CLE_SAISIE
from apps.crm.models import Lead

from .test_api_liste import BaseApiCalepinage, url_detail


def url_raccordement(pk):
    return f'{url_detail(pk)}raccordement/'


class PropositionLead(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        Lead.objects.filter(pk=self.lead.pk).update(
            compteur_puissance_kva=Decimal('6'), raccordement='monophase')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')

    def _lire(self, calepinage=None):
        reponse = self.api.get(
            url_raccordement((calepinage or self.calepinage).pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_get_propose_les_valeurs_du_lead(self):
        donnees = self._lire()
        self.assertEqual(donnees['proposition_lead'],
                         {'puissance_souscrite_kva': 6.0, 'phases': 1,
                          'source': 'lead'})
        # La saisie reste VIDE tant que l'utilisateur n'a pas confirmé.
        self.assertIsNone(donnees['saisie']['puissance_souscrite_kva'])
        self.assertIsNone(donnees['saisie']['phases'])

    def test_aucune_ecriture(self):
        self._lire()
        self.calepinage.refresh_from_db()
        self.assertNotIn(CLE_SAISIE, self.calepinage.resultat or {})
        lead = Lead.objects.get(pk=self.lead.pk)
        self.assertEqual(lead.compteur_puissance_kva, Decimal('6'))
        self.assertEqual(lead.raccordement, 'monophase')

    def test_la_valeur_ne_devient_saisie_que_par_un_post(self):
        reponse = self.api.post(url_raccordement(self.calepinage.pk),
                                {'puissance_souscrite_kva': 6, 'phases': 1},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.calepinage.refresh_from_db()
        self.assertEqual(
            self.calepinage.resultat[CLE_SAISIE]['puissance_souscrite_kva'],
            6.0)

    def test_lead_absent_ou_vide_donne_null(self):
        sans_lead = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Sans lead')
        self.assertIsNone(self._lire(sans_lead)['proposition_lead'])
        vide = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk, titre='Lead vide')
        self.assertIsNone(self._lire(vide)['proposition_lead'])

    def test_lead_d_une_autre_societe_introuvable(self):
        etranger = Lead.objects.create(
            company=self.autre, nom='Voisin', raccordement='triphase',
            compteur_puissance_kva=Decimal('9'))
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=etranger.pk, titre='Piège')
        self.assertIsNone(self._lire(calepinage)['proposition_lead'])
