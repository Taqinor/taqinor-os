# -*- coding: utf-8 -*-
"""ACAL172 (D-ACAL-9, D-ACAL-2, C-ACAL-064) — l'approbation et « retenir une
variante » LISENT le verdict électrique ; une variante s'évalue par
``GET resultat/?variante=`` et porte ``verdict_electrique`` dans comparer/.

HTTP réel, base réelle, matériel RÉEL (fiches techniques en base) : module
Isc 18,4 A sur un onduleur à UNE entrée MPPT qui admet 26 A. 12 modules ⇒
une chaîne (conforme) ; 24 modules ⇒ deux chaînes en parallèle, 36,8 A
(bloquant). Aucun patch de la lecture des bloquants.
"""
from __future__ import annotations

import copy
from decimal import Decimal

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.electrique import CLE_ENTREE
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage, url_detail

CODE_ISC = 'CH_ISC_CUMULE_HORS_SPECIFICATION'


def _dessin(modules):
    return {'zones': [{'id': 'z1', 'label': 'PAN-A',
                       'vertices': [[0, 0], [12, 0], [12, 6]],
                       'geometry': {'count': modules, 'azimuthDeg': 180.0,
                                    'tiltDeg': 15.0}}]}


class Gouvernance(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.module = self._produit(
            nom='Module 18A', type_fiche='module', vmp_v=41.5, voc_v=49.6,
            isc_a=18.4, imp_a=17.1, pmax_wc=710.0)
        self.onduleur = self._produit(
            nom='Onduleur 26A', type_fiche='onduleur', ond_n_mppt=1,
            ond_mppt_v_min=150.0, ond_mppt_v_max=800.0,
            ond_v_max_abs=1000.0, ond_i_max_mppt_a=26.0,
            ond_isc_max_mppt_a=26.0, ond_ac_kw=20.0, ond_phases=3)

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL172-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def _calepinage(self, modules, *, onduleur=True):
        entree = {'module_produit': self.module.pk,
                  'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
                  'phases': 3}
        if onduleur:
            entree['onduleur_produit'] = self.onduleur.pk
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL172',
            roof_layout=_dessin(modules), resultat={CLE_ENTREE: entree})

    def _variante(self, calepinage, modules, nom='V'):
        return CalepinageVariante.objects.create(
            company=self.company, calepinage=calepinage, nom=nom,
            roof_layout=copy.deepcopy(_dessin(modules)))

    def _url(self, calepinage, suffixe=''):
        return f'{url_detail(calepinage.pk)}{suffixe}'

    def test_approbation_refusee_sur_bloquant(self):
        enregistrer_parametres(self.company,
                               {'presets': {'approbation_exigee': True}})
        calepinage = self._calepinage(24)
        reponse = self.api.post(self._url(calepinage, 'approbation/'),
                                {'decision': 'approuve'}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('electrique', reponse.data)
        self.assertIn('Isc', reponse.data['electrique'])
        calepinage.refresh_from_db()
        self.assertFalse(calepinage.approbation)

    def test_retenue_refusee_verdict_de_la_variante(self):
        # La conception COURANTE est conforme (12 modules) : c'est le
        # verdict de LA variante (24 modules) qui refuse.
        calepinage = self._calepinage(12)
        variante = self._variante(calepinage, 24, nom='Dense')
        reponse = self.api.post(
            self._url(calepinage, f'variantes/{variante.pk}/retenir/'), {},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('Isc', str(reponse.data))
        variante.refresh_from_db()
        self.assertFalse(variante.retenue)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.roof_layout, _dessin(12))

    def test_indetermine_n_empeche_pas(self):
        # Onduleur non désigné : verdict INDÉTERMINÉ — accord permis, avec
        # l'avertissement consigné au chatter ; retenue permise.
        calepinage = self._calepinage(24, onduleur=False)
        reponse = self.api.post(self._url(calepinage, 'approbation/'),
                                {'decision': 'approuve'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['etat'], 'approuve')
        chatter = self.api.get(self._url(calepinage, 'chatter/historique/'))
        self.assertEqual(chatter.status_code, 200, chatter.data)
        self.assertTrue(any('indéterminé' in (entree.get('body') or '')
                            for entree in chatter.data), chatter.data)
        variante = self._variante(calepinage, 12)
        retenue = self.api.post(
            self._url(calepinage, f'variantes/{variante.pk}/retenir/'), {},
            format='json')
        self.assertEqual(retenue.status_code, 200, retenue.data)

    def test_resultat_par_variante(self):
        calepinage = self._calepinage(12)
        variante = self._variante(calepinage, 24, nom='Dense')
        courant = self.api.get(self._url(calepinage, 'resultat/'))
        self.assertEqual(courant.status_code, 200, courant.data)
        self.assertIsNone(courant.data['variante'])

        def bloquants_en_echec(data):
            return [v.get('code') for v in data['electrique']['verdicts']
                    if v.get('bloquant') and not v.get('conforme')]

        self.assertEqual(bloquants_en_echec(courant.data), [])
        reponse = self.api.get(self._url(calepinage, 'resultat/'),
                               {'variante': variante.pk})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['variante'],
                         {'id': variante.pk, 'nom': 'Dense'})
        self.assertIn('courant_par_entree_mppt',
                      bloquants_en_echec(reponse.data))
        # Lecture pure : rien n'a été écrit sur le calepinage.
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.roof_layout, _dessin(12))
        etrangere = self.api.get(self._url(calepinage, 'resultat/'),
                                 {'variante': 999999})
        self.assertEqual(etrangere.status_code, 404)

    def test_comparer_porte_verdict_electrique(self):
        calepinage = self._calepinage(12)
        sage = self._variante(calepinage, 12, nom='Sage')
        dense = self._variante(calepinage, 24, nom='Dense')
        reponse = self.api.get(self._url(calepinage, 'comparer/'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        par_id = {ligne['id']: ligne['verdict_electrique']
                  for ligne in reponse.data['lignes']}
        self.assertEqual(par_id[dense.pk]['verdict'], 'bloquant')
        self.assertIn(CODE_ISC, par_id[dense.pk]['bloquants'])
        self.assertNotEqual(par_id[sage.pk]['verdict'], 'bloquant')
        self.assertEqual(par_id[sage.pk]['bloquants'], [])
