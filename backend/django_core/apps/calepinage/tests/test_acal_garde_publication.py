# -*- coding: utf-8 -*-
"""ACAL170 (D-ACAL-9, C-ACAL-064) — « Générer / Resynchroniser le devis »
refusés sur un verdict électrique BLOQUANT, levés par une dérogation écrite.

Route HTTP RÉELLE, base réelle, matériel RÉEL (fiches techniques en base :
module Isc 18,2 A sur un onduleur dont l'entrée MPPT n'admet que 10 A). La
garde n'est JAMAIS patchée : seuls le pré-vol et le constructeur du serveur
VENTES sont doublés quand le devis doit réellement être produit — ce fichier
prouve le cliquet électrique, pas la composition (testée côté ventes).
"""
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, CLE_FIL_DEROGATIONS, CODE_DEROGATION_PUBLICATION,
)
from apps.roles.models import Role
from apps.roles.permissions_registre import RESPONSABLE_PERMISSIONS
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [{'id': 'z1', 'label': 'Sud', 'result': {'count': 12},
               'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0}],
}
CODE_ISC = 'CH_ISC_CUMULE_HORS_SPECIFICATION'
MOTIF = 'client informé'


def _url(pk, suffixe):
    return f'{url_detail(pk)}{suffixe}/'


class Garde(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.module = self._produit(
            nom='Module 18A', type_fiche='module', vmp_v=41.4, voc_v=49.3,
            isc_a=18.2, imp_a=17.2, pmax_wc=710.0)
        self.onduleur = self._produit(
            nom='Onduleur 10A', type_fiche='onduleur', ond_n_mppt=1,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
            ond_v_max_abs=1100.0, ond_i_max_mppt_a=10.0,
            ond_isc_max_mppt_a=10.0, ond_ac_kw=10.0, ond_phases=3)
        self.calepinage = self._calepinage(self.onduleur)

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL170-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def _calepinage(self, onduleur=None, lead=None):
        entree = {'module_produit': self.module.pk,
                  'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
                  'phases': 3}
        if onduleur is not None:
            entree['onduleur_produit'] = onduleur.pk
        return Calepinage.objects.create(
            company=self.company, lead_id=(lead or self.lead).pk,
            titre='Villa', roof_layout=LAYOUT,
            resultat={CLE_ENTREE: entree})

    def _devis(self, lead=None):
        return Devis.objects.create(
            company=self.company, client=self.client_a,
            lead=lead or self.lead,
            reference=f'DEV-202610-{Devis.objects.count() + 170:04d}')

    def _generer(self, api, calepinage, corps=None, devis=None):
        from apps.crm.models import Lead

        devis = devis or self._devis(
            Lead.objects.get(pk=calepinage.lead_id))
        with mock.patch(
                'apps.ventes.services.validate_composition_for_layout',
                return_value=[]), \
                mock.patch('apps.ventes.services.build_devis_from_layout',
                           return_value=devis) as construire:
            reponse = api.post(_url(calepinage.pk, 'generer-devis'),
                               corps or {}, format='json')
        return reponse, construire

    def _fil(self, calepinage):
        calepinage.refresh_from_db()
        return (calepinage.resultat or {}).get(CLE_FIL_DEROGATIONS) or []

    def test_generer_refuse_422_nomme_les_bloquants(self):
        reponse, construire = self._generer(self.api, self.calepinage)
        self.assertEqual(reponse.status_code, 422, reponse.data)
        electrique = reponse.data['electrique']
        self.assertEqual(electrique['verdict'], 'bloquant')
        self.assertTrue(electrique['derogation_possible'])
        self.assertIn(CODE_ISC, [b['code'] for b in electrique['bloquants']])
        for bloquant in electrique['bloquants']:
            self.assertEqual(sorted(bloquant), ['code', 'detail', 'libelle'])
        self.assertTrue(reponse.data['detail'])
        construire.assert_not_called()
        self.calepinage.refresh_from_db()
        self.assertIsNone(self.calepinage.devis_id)

    def test_sync_refuse(self):
        devis = self._devis()
        self.calepinage.devis = devis
        self.calepinage.save(update_fields=['devis'])
        with mock.patch('apps.ventes.services.resynchroniser_conception'
                        ) as resync:
            reponse = self.api.post(_url(self.calepinage.pk, 'sync-devis'),
                                    {}, format='json')
        self.assertEqual(reponse.status_code, 422, reponse.data)
        self.assertEqual(reponse.data['electrique']['verdict'], 'bloquant')
        resync.assert_not_called()
        self.assertEqual(self._fil(self.calepinage), [])

    def test_derogation_tracee_leve_le_refus(self):
        reponse, construire = self._generer(
            self.api, self.calepinage,
            {'derogation_electrique': {'motif': MOTIF,
                                       'auteur': 'Usurpateur',
                                       'horodatage': '2000-01-01'}})
        self.assertEqual(reponse.status_code, 201, reponse.data)
        construire.assert_called_once()
        electrique = reponse.data['electrique']
        self.assertEqual(electrique['verdict'], 'bloquant')
        self.assertEqual(electrique['derogation']['motif'], MOTIF)
        # Auteur et instant posés par le SERVEUR, jamais lus du corps.
        self.assertEqual(electrique['derogation']['auteur']['id'],
                         self.user.pk)
        self.assertNotIn('2000', electrique['derogation']['horodatage'])
        fil = self._fil(self.calepinage)
        self.assertEqual(len(fil), 1)
        trace = fil[0]
        self.assertEqual(trace['code'], CODE_DEROGATION_PUBLICATION)
        self.assertEqual(trace['motif'], MOTIF)
        self.assertNotEqual(trace['auteur'], 'Usurpateur')
        self.assertIn('Isc', trace['texte'])
        # Rouvrir : le MÊME fil, servi par GET resultat/.
        relu = self.api.get(_url(self.calepinage.pk, 'resultat'))
        self.assertEqual(relu.status_code, 200, relu.data)
        self.assertEqual(relu.data['derogations'][0]['code'],
                         CODE_DEROGATION_PUBLICATION)
        chatter = self.api.get(_url(self.calepinage.pk,
                                    'chatter/historique'))
        self.assertEqual(chatter.status_code, 200, chatter.data)
        self.assertTrue(any(entree.get('body') == trace['texte']
                            for entree in chatter.data), chatter.data)

    def test_sync_avec_derogation_passe_et_trace(self):
        devis = self._devis()
        self.calepinage.devis = devis
        self.calepinage.save(update_fields=['devis'])
        with mock.patch('apps.ventes.services.resynchroniser_conception',
                        return_value={'inchange': True}) as resync:
            reponse = self.api.post(
                _url(self.calepinage.pk, 'sync-devis'),
                {'derogation_electrique': {'motif': MOTIF}}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        resync.assert_called_once()
        self.assertTrue(reponse.data['inchange'])
        self.assertEqual(reponse.data['electrique']['derogation']['motif'],
                         MOTIF)
        self.assertEqual(len(self._fil(self.calepinage)), 1)

    def test_indetermine_ne_bloque_pas(self):
        # Aucun onduleur désigné, aucun devis lié : fiche INCOMPLÈTE.
        calepinage = self._calepinage(onduleur=None, lead=self.lead_2)
        reponse, construire = self._generer(self.api, calepinage)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        construire.assert_called_once()
        electrique = reponse.data['electrique']
        self.assertEqual(electrique['verdict'], 'indetermine')
        self.assertTrue(electrique['manquantes'])
        self.assertIsNone(electrique['derogation'])

    def test_derogation_sans_motif_refusee(self):
        reponse, construire = self._generer(
            self.api, self.calepinage,
            {'derogation_electrique': {'motif': '   '}})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('derogation_electrique', reponse.data)
        construire.assert_not_called()
        self.assertEqual(self._fil(self.calepinage), [])

    def test_derogation_sans_calepinage_approuver_403(self):
        role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=list(RESPONSABLE_PERMISSIONS))
        self.user_sans.role = role
        self.user_sans.save(update_fields=['role'])
        reponse, construire = self._generer(
            self._client(self.user_sans), self.calepinage,
            {'derogation_electrique': {'motif': MOTIF}})
        self.assertEqual(reponse.status_code, 403, reponse.data)
        self.assertEqual(
            reponse.data['derogation_electrique'],
            'Dérogation réservée aux approbateurs (calepinage_approuver)')
        construire.assert_not_called()
        self.assertEqual(self._fil(self.calepinage), [])

    def test_terre_non_justifiee_bloque(self):
        ParametresCalepinage.objects.create(
            company=self.company,
            norme_electrique={'norme': 'nf_c_15_100'})
        conforme = self._produit(
            nom='Onduleur 45A', type_fiche='onduleur', ond_n_mppt=1,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
            ond_v_max_abs=1100.0, ond_i_max_mppt_a=45.0,
            ond_isc_max_mppt_a=45.0, ond_ac_kw=10.0, ond_phases=3)
        calepinage = self._calepinage(conforme, lead=self.lead_2)
        reponse, construire = self._generer(self.api, calepinage)
        self.assertEqual(reponse.status_code, 422, reponse.data)
        codes = [b['code'] for b in reponse.data['electrique']['bloquants']]
        self.assertIn('TERRE_JUSTIFICATION_MANQUANTE', codes)
        self.assertNotIn(CODE_ISC, codes)
        construire.assert_not_called()

    def test_aucun_devis_cree_en_cas_de_refus(self):
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self.api.post(_url(self.calepinage.pk, 'generer-devis'),
                                {}, format='json')
        self.assertEqual(reponse.status_code, 422, reponse.data)
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        self.calepinage.refresh_from_db()
        self.assertIsNone(self.calepinage.devis_id)
        self.assertEqual(self._fil(self.calepinage), [])
