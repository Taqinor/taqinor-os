# -*- coding: utf-8 -*-
"""ACAL283 — dérogations d'alerte et écarts de longueur SERVIS par
``GET resultat/``, chaque dérogation notée au chatter.

Route HTTP RÉELLE (POST entree-electrique, GET resultat, GET chatter), base
réelle, aucun mock. D-ACAL-9 : toute dérogation électrique exige
``calepinage_approuver`` ; un BLOQUANT ne se passe jamais outre.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, CLE_FIL_ECARTS, _journaliser_ecart_longueur,
)
from apps.roles.models import Role
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [{'id': 'z1', 'label': 'Sud', 'result': {'count': 12},
               'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0}],
}
#: Une alerte NON bloquante prononcée par le noyau : Imp cumulé au-dessus du
#: courant d'entrée admissible (écrêtage), aucune borne Isc publiée.
CODE_ALERTE = 'CH_IMP_CUMULE_ECRETAGE'
CODE_BLOQUANT = 'CH_ISC_CUMULE_HORS_SPECIFICATION'


def _url(pk, suffixe):
    return f'{url_detail(pk)}{suffixe}/'


class Derogations(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        module = self._produit(
            nom='Module 710', type_fiche='module', vmp_v=41.4, voc_v=49.3,
            isc_a=18.59, imp_a=17.59, pmax_wc=710.0)
        self.onduleur = self._produit(
            nom='Onduleur 1 MPPT', type_fiche='onduleur', ond_n_mppt=1,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
            ond_v_max_abs=1100.0, ond_i_max_mppt_a=15.0, ond_ac_kw=10.0,
            ond_phases=3)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa',
            roof_layout=LAYOUT, resultat={CLE_ENTREE: {
                'module_produit': module.pk,
                'onduleur_produit': self.onduleur.pk,
                'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
                'phases': 3}})

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL283-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def _deroger(self, api, code):
        return api.post(_url(self.calepinage.pk, 'entree-electrique'),
                        {'derogations': [{'code': code,
                                          'motif': 'validé avec le client'}]},
                        format='json')

    def test_derogation_posee_est_servie_et_notee_au_chatter(self):
        reponse = self._deroger(self.api, CODE_ALERTE)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        resultat = self.api.get(_url(self.calepinage.pk, 'resultat'))
        self.assertEqual(resultat.status_code, 200, resultat.data)
        derogations = resultat.data['derogations']
        self.assertEqual(len(derogations), 1)
        derogation = derogations[0]
        self.assertEqual(sorted(derogation),
                         ['auteur', 'code', 'horodatage', 'libelle',
                          'motif', 'texte'])
        self.assertEqual(derogation['code'], CODE_ALERTE)
        self.assertTrue(derogation['auteur'])
        # Rouvrir : la MÊME trace (auteur, horodatage), jamais recalculée.
        relu = self.api.get(_url(self.calepinage.pk, 'resultat'))
        self.assertEqual(relu.data['derogations'], derogations)
        chatter = self.api.get(
            _url(self.calepinage.pk, 'chatter/historique'))
        self.assertEqual(chatter.status_code, 200, chatter.data)
        self.assertTrue(any(entree.get('body') == derogation['texte']
                            for entree in chatter.data), chatter.data)
        # Enregistrer sans toucher n'ajoute aucune entrée au fil.
        self.api.post(_url(self.calepinage.pk, 'entree-electrique'),
                      {'phases': 3}, format='json')
        self.assertEqual(
            len(self.api.get(_url(self.calepinage.pk,
                                  'resultat')).data['derogations']), 1)

    def test_listes_vides_jamais_absentes(self):
        resultat = self.api.get(_url(self.calepinage.pk, 'resultat'))
        self.assertEqual(resultat.data['derogations'], [])
        self.assertEqual(resultat.data['ecarts_longueur'], [])

    def test_ecart_de_longueur_est_servi(self):
        _journaliser_ecart_longueur(self.calepinage, {
            'hors_tolerance': True, 'longueur': 12, 'longueur_dossier': 18,
            'ecart': -6, 'par_pan': {'Sud': 12}})
        self.calepinage.refresh_from_db()
        self.assertEqual(len(self.calepinage.resultat[CLE_FIL_ECARTS]), 1)
        resultat = self.api.get(_url(self.calepinage.pk, 'resultat'))
        self.assertEqual(resultat.data['ecarts_longueur'][0]['ecart'], -6)

    def test_bloquant_reste_refuse(self):
        FicheTechnique.objects.filter(produit=self.onduleur).update(
            ond_isc_max_mppt_a=10.0)
        reponse = self._deroger(self.api, CODE_BLOQUANT)
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.calepinage.refresh_from_db()
        self.assertNotIn('journal_derogations', self.calepinage.resultat)

    def test_derogation_sans_calepinage_approuver_403(self):
        role = Role.objects.create(
            company=self.company, nom='Commercial calepinage',
            permissions=['calepinage_voir', 'calepinage_gerer'])
        self.user_sans.role = role
        self.user_sans.save(update_fields=['role'])
        reponse = self._deroger(self._client(self.user_sans), CODE_ALERTE)
        self.assertEqual(reponse.status_code, 403, reponse.data)
        self.assertIn('derogations', reponse.data)
        self.calepinage.refresh_from_db()
        self.assertNotIn('journal_derogations', self.calepinage.resultat)
