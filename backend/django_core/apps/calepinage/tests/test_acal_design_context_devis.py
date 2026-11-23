"""ACAL36 (C-ACAL-115/114) — le contexte de conception du calepinage sert
``revision_possible`` et le devis lié (référence, statut, client) selon le
contrat ``calepinage_design_context.json``.

``revision_possible`` est LU sur ventes (``devis_modifiabilite`` →
``domain.modifiabilite.verdict``, réel) ; ``calepinage.devis_lie`` reprend le
bloc ``devis`` du contexte ventes. Aucun mock : APIClient réel, base réelle.
"""
from __future__ import annotations

import json
from pathlib import Path

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'calepinage_design_context.json').read_text(encoding='utf-8'))

LAYOUT = {'schema_version': 2, 'result': {'panels': 12, 'kwc': 8.64}}


def url_contexte(pk):
    return f'{url_detail(pk)}design-context/'


class ContexteDevisLieTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.client_lie = Client.objects.create(company=self.company,
                                                nom='Client ACAL36')
        self.lead_lie = Lead.objects.create(company=self.company,
                                            nom='Lead ACAL36')

    def _calepinage_lie(self, statut):
        devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference=f'DEV-ACAL36-{statut}', statut=statut)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, devis=devis,
            titre=f'QA-ACAL36-{statut}', roof_layout=LAYOUT)
        return calepinage, devis

    def _contexte(self, calepinage):
        reponse = self.api.get(url_contexte(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_accepte_revision_possible_et_devis_lie(self):
        attendu = CONTRAT['exemple_accepte']
        calepinage, devis = self._calepinage_lie(Devis.Statut.ACCEPTE)
        contexte = self._contexte(calepinage)
        self.assertIs(contexte['revision_possible'], True)
        self.assertEqual(attendu['revision_possible'], True)
        devis_lie = contexte['calepinage']['devis_lie']
        self.assertEqual(sorted(devis_lie),
                         sorted(attendu['calepinage']['devis_lie']))
        self.assertEqual(devis_lie['id'], devis.pk)
        self.assertEqual(devis_lie['reference'], devis.reference)
        self.assertEqual(devis_lie['statut'], 'accepte')
        self.assertTrue(devis_lie['client_nom'])

    def test_brouillon_revision_impossible(self):
        calepinage, _devis = self._calepinage_lie(Devis.Statut.BROUILLON)
        contexte = self._contexte(calepinage)
        self.assertIs(contexte['revision_possible'],
                      CONTRAT['exemple']['revision_possible'])
        self.assertEqual(contexte['calepinage']['devis_lie']['statut'],
                         'brouillon')

    def test_sans_devis_cles_presentes_a_null(self):
        attendu = CONTRAT['exemple_sans_devis']
        nu = Calepinage.objects.create(company=self.company,
                                       client=self.client_lie,
                                       titre='QA-ACAL36-nu')
        contexte = self._contexte(nu)
        self.assertIn('revision_possible', contexte)
        self.assertIs(contexte['revision_possible'],
                      attendu['revision_possible'])
        self.assertIn('devis_lie', contexte['calepinage'])
        self.assertIsNone(contexte['calepinage']['devis_lie'])
        # Les sept clés historiques restent toutes présentes.
        for cle in ('calepinage', 'geometrie', 'cible', 'carte', 'modifiable',
                    'raison_lecture_seule', 'avertissements'):
            self.assertIn(cle, contexte)


def _contrat_retenue():
    return json.loads((Path(__file__).resolve().parent.parent / 'contract_samples'
                       / 'calepinage_conception_retenue.json').read_text(encoding='utf-8'))


class _DevisDeuxOptions(BaseApiCalepinage):
    """ACAL1950 — un devis « Les deux » à deux comptes de panneaux : onduleur
    réseau dans l'option sans, hybride + batterie dans l'option avec (même
    fabrique que ``apps/ventes/tests/test_ctx3d_cible_avec.py``)."""

    PRODUITS = (('PAN', 'Panneau Jinko 715W'),
                ('ONDR', 'Onduleur réseau Huawei 20kW Triphasé'),
                ('ONDH', 'Onduleur hybride Deye 20kW Triphasé'),
                ('BAT', 'Batterie Dyness 10 kWh'))

    def setUp(self):
        from decimal import Decimal

        from apps.stock.models import Produit

        super().setUp()
        self.client_lie = Client.objects.create(company=self.company, nom='Client ACAL1950')
        self.lead_lie = Lead.objects.create(company=self.company, nom='Lead ACAL1950')
        self.produits = {cle: Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL1950-{cle}',
            prix_vente=Decimal('1100'), quantite_stock=50)
            for cle, nom in self.PRODUITS}
        self.compteur = 0

    def _devis(self, lignes, statut='envoye', mode='residentiel', **extra):
        from decimal import Decimal

        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference=f'DEV-ACAL1950-{self.compteur * 10}', statut=statut,
            mode_installation=mode, **extra)
        for cle, quantite, variante in lignes:
            produit = self.produits[cle]
            devis.lignes.create(produit=produit, designation=produit.nom,
                                quantite=Decimal(str(quantite)),
                                prix_unitaire=Decimal('1100'), variante=variante)
        return devis

    def _les_deux(self, recommandee=None, etude=None, **extra):
        params = {'scenario': 'Les deux (Sans + Avec)', **(etude or {})}
        if recommandee:
            params['recommended_option'] = recommandee
        return self._devis(
            [('PAN', 35, 'sans'), ('PAN', 48, 'avec'), ('ONDR', 1, 'sans'),
             ('ONDH', 1, 'avec'), ('BAT', 1, 'avec')],
            etude_params=params, **extra)


class ConceptionRetenueTest(_DevisDeuxOptions):
    """ACAL1950 — le devis dit sa conception retenue (sélecteur ventes réel)."""

    @staticmethod
    def _lire(devis):
        from apps.ventes.selectors_calepinage import conception_retenue_du_devis

        return conception_retenue_du_devis(devis)

    def test_recommandee_sans_rend_l_option_sans_et_ses_quantites(self):
        devis = self._les_deux('Sans batterie', etude={
            'etude_horaire': {'annuel': {'production_kwh': 60000}},
            'etude_horaire_sans': {'annuel': {'production_kwh': 41250}}})
        lu = self._lire(devis)
        self.assertEqual(sorted(lu), sorted(_contrat_retenue()['exemple']))
        self.assertEqual((lu['option'], lu['deux_options'], lu['recu']), ('sans', True, True))
        self.assertEqual(lu['module']['quantite'], 35)
        self.assertEqual(lu['module']['produit'], self.produits['PAN'].pk)
        self.assertEqual(lu['module']['watt'], 715.0)
        self.assertEqual([(o['produit'], o['quantite']) for o in lu['onduleurs']],
                         [(self.produits['ONDR'].pk, 1)])
        # La conception électrique rangée décrit l'option « avec » : jamais servie pour « sans ».
        self.assertIsNone(lu['chaines'])
        self.assertEqual((lu['production_annuelle_kwh'], lu['production_origine']),
                         (41250.0, 'etude_horaire_sans'))

    def test_recommandee_avec_rend_l_option_avec(self):
        devis = self._les_deux('Avec batterie', electrical_design={'chaines': [
            {'nb_modules': 12}, {'nb_modules': 12}, {'nb_modules': 12}, {'nb_modules': 12}]})
        lu = self._lire(devis)
        self.assertEqual((lu['option'], lu['module']['quantite']), ('avec', 48))
        self.assertEqual([o['produit'] for o in lu['onduleurs']], [self.produits['ONDH'].pk])
        self.assertEqual(lu['chaines'], {'nombre': 4, 'longueurs': [12, 12, 12, 12], 'longueur': 12})

    def test_option_unique_et_cle_absente_rend_null(self):
        devis = self._devis([('PAN', 10, ''), ('ONDR', 1, '')], statut='brouillon')
        lu = self._lire(devis)
        self.assertEqual((lu['option'], lu['deux_options'], lu['recu']), ('sans', False, False))
        self.assertEqual(lu['module']['quantite'], 10)
        self.assertIsNone(lu['chaines'])
        self.assertIsNone(lu['production_annuelle_kwh'])
        self.assertIsNone(lu['production_origine'])
        self.assertIsNone(self._lire(None))
        self.assertIsNone(_contrat_retenue()['exemple_vide'])

    def test_c_i_lit_le_bilan_du_moteur(self):
        devis = self._devis([('PAN', 35, ''), ('ONDR', 1, '')], mode='commercial',
                            etude_params={'etude_ci': {'bilan': {'production_kwh': 95425}}})
        lu = self._lire(devis)
        self.assertEqual((lu['production_annuelle_kwh'], lu['production_origine']),
                         (95425.0, 'etude_ci'))
