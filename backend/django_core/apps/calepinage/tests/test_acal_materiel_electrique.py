# -*- coding: utf-8 -*-
"""ACAL56 — module, onduleur, optimiseur du calcul électrique (D-ACAL-10).

Désignation EXPLICITE d'abord ; sinon les LIGNES DU DEVIS LIÉ (provenance
« devis », recalculée à chaque lecture, jamais persistée) ; sinon un refus
NOMMÉ qui dit le geste. Et ``GET entree-electrique/`` relit l'entrée stockée.

Produit / FicheTechnique / Devis / LigneDevis RÉELS en base :
``resoudre_materiel`` n'est jamais patché, la conception n'est jamais doublée.
"""
from __future__ import annotations

import json
import pathlib
from decimal import Decimal

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, PROVENANCE_DEVIS, PROVENANCE_EXPLICITE,
    conception_du_calepinage,
)
from apps.calepinage.services.simulation import construire_contexte
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.models import Devis, LigneDevis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = (pathlib.Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'calepinage_entree_electrique.json')

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [{
        'id': 'z1', 'label': 'Sud', 'neededPanels': 12,
        'result': {'count': 12},
        'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0,
    }],
}

#: Températures SAISIES : aucun appel réseau (TMY) pendant les tests.
TEMPERATURES = {'temperature_min_c': -5.0, 'temperature_max_c': 70.0}


def url_entree(pk):
    return f'{url_detail(pk)}entree-electrique/'


class BaseMateriel(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.module_devis = self._produit(
            nom='Module devis 710', type_fiche='module', vmp_v=41.4,
            voc_v=49.3, isc_a=18.59, imp_a=17.59, pmax_wc=710.0)
        self.module_explicite = self._produit(
            nom='Module explicite 580', type_fiche='module', vmp_v=44.0,
            voc_v=52.0, isc_a=14.0, imp_a=13.2, pmax_wc=580.0)
        self.onduleur = self._produit(
            nom='Onduleur 10 kW', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
            ond_v_max_abs=1100.0, ond_i_max_mppt_a=26.0, ond_ac_kw=10.0,
            ond_phases=3)

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL56-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def _devis(self, *produits):
        devis = Devis.objects.create(company=self.company,
                                     client=self.client_a,
                                     reference='DEV-ACAL56-1')
        for produit in produits:
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal('1'), prix_unitaire=Decimal('100'),
                type_ligne='produit', variante='')
        return devis

    def _calepinage(self, *, devis=None, entree=None):
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk,
            client=self.client_a, devis=devis, titre='Villa Anfa',
            roof_layout=LAYOUT,
            resultat={CLE_ENTREE: dict(TEMPERATURES, **(entree or {}))})


class MaterielDuDevis(BaseMateriel):

    def test_defaut_ligne_du_devis_provenance_devis(self):
        calepinage = self._calepinage(
            devis=self._devis(self.module_devis, self.onduleur))
        conception, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual(materiel['provenances']['module'], PROVENANCE_DEVIS)
        self.assertEqual(materiel['provenances']['onduleur'],
                         PROVENANCE_DEVIS)
        self.assertEqual(materiel['produits']['module'],
                         self.module_devis.pk)
        self.assertFalse(conception.fiche_incomplete, conception.manquantes)
        self.assertTrue(conception.chaines)
        self.assertEqual(materiel['absents'], ())

    def test_la_provenance_devis_n_est_pas_persistee(self):
        calepinage = self._calepinage(
            devis=self._devis(self.module_devis, self.onduleur))
        avant = dict(calepinage.resultat[CLE_ENTREE])
        reponse = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['materiel']['module']['provenance'],
                         PROVENANCE_DEVIS)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat[CLE_ENTREE], avant)
        self.assertNotIn('module_produit', calepinage.resultat[CLE_ENTREE])


class MaterielExplicite(BaseMateriel):

    def test_designation_gagne_sur_le_devis(self):
        calepinage = self._calepinage(
            devis=self._devis(self.module_devis, self.onduleur),
            entree={'module_produit': self.module_explicite.pk})
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual(materiel['produits']['module'],
                         self.module_explicite.pk)
        self.assertEqual(materiel['provenances']['module'],
                         PROVENANCE_EXPLICITE)
        # L'onduleur, non désigné, reste celui du devis.
        self.assertEqual(materiel['provenances']['onduleur'],
                         PROVENANCE_DEVIS)


class SansDevis(BaseMateriel):

    def test_absent_nomme_le_geste(self):
        calepinage = self._calepinage()
        conception, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertIn("module PV non désigné — désignez-le dans l'onglet "
                      'Matériel électrique', materiel['absents'])
        self.assertTrue(conception.fiche_incomplete)
        self.assertFalse(conception.chaines)
        self.assertFalse(conception.bloquants)


class GetEntree(BaseMateriel):

    def test_forme_du_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        calepinage = self._calepinage(
            devis=self._devis(self.module_devis, self.onduleur))
        reponse = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        donnees = reponse.data
        self.assertEqual(sorted(donnees), sorted(contrat['exemple']))
        self.assertEqual(sorted(donnees['entree']),
                         sorted(contrat['exemple']['entree']))
        self.assertEqual(sorted(donnees['materiel']),
                         sorted(contrat['exemple']['materiel']))
        self.assertEqual(sorted(donnees['materiel']['module']),
                         sorted(contrat['exemple']['materiel']['module']))
        self.assertEqual(sorted(donnees['candidats']),
                         sorted(contrat['exemple']['candidats']))
        attendu = sorted(contrat['exemple']['candidats']['modules'][0])
        self.assertTrue(donnees['candidats']['modules'])
        for ligne in donnees['candidats']['modules']:
            self.assertEqual(sorted(ligne), attendu)
        self.assertEqual(donnees['absents'], ['optimiseur'])
        self.assertNotIn('prix', json.dumps(donnees, default=str))

    def test_post_puis_get_relit_l_entree_ecrite(self):
        calepinage = self._calepinage()
        corps = {'module_produit': self.module_explicite.pk,
                 'onduleur_produit': self.onduleur.pk, 'dc_m': 25.0,
                 'phases': 3}
        poste = self.api.post(url_entree(calepinage.pk), corps,
                              format='json')
        self.assertEqual(poste.status_code, 200, poste.data)
        calepinage.refresh_from_db()
        stockee = dict(calepinage.resultat[CLE_ENTREE])
        lu = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(lu.status_code, 200, lu.data)
        for cle, valeur in corps.items():
            self.assertEqual(lu.data['entree'][cle], valeur, cle)
        # Ré-enregistrer sans rien toucher : entrée octet-identique.
        self.api.post(url_entree(calepinage.pk), corps, format='json')
        calepinage.refresh_from_db()
        self.assertEqual(
            json.dumps(calepinage.resultat[CLE_ENTREE], sort_keys=True),
            json.dumps(stockee, sort_keys=True))

    def test_une_autre_societe_ne_voit_rien(self):
        calepinage = self._calepinage()
        reponse = self.api_autre.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.status_code, 404)


class Simulation(BaseMateriel):

    def test_construire_contexte_fiche_module_non_vide(self):
        calepinage = self._calepinage(
            devis=self._devis(self.module_devis, self.onduleur))
        contexte, meta = construire_contexte(calepinage)
        self.assertEqual(contexte['fiche_module'].get('pmax_wc'), 710.0)
        self.assertIsNotNone(meta['kwc'])


class MaterielRetenuParLeDevis(BaseMateriel):
    """ACAL1952 — sans saisie, l'onduleur, leur nombre et la longueur de chaîne
    sont ceux du DEVIS (option retenue), servis avec la provenance « devis » ;
    une saisie contraire reste permise et est dite comme écart."""

    def setUp(self):
        super().setUp()
        self.hybride = self._produit(
            nom='Onduleur hybride 10 kW', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0, ond_v_max_abs=1100.0,
            ond_i_max_mppt_a=26.0, ond_ac_kw=10.0, ond_phases=3)
        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie Dyness 10 kWh', sku='ACAL1952-BAT',
            prix_vente=Decimal('1500'), quantite_stock=1)

    def _devis_deux_options(self, recommandee):
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, reference='DEV-ACAL1952-10',
            statut='envoye', etude_params={'scenario': 'Les deux (Sans + Avec)',
                                           'recommended_option': recommandee})
        for produit, variante in ((self.module_devis, ''), (self.onduleur, 'sans'),
                                  (self.hybride, 'avec'), (self.batterie, 'avec')):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom, quantite=Decimal('1'),
                prix_unitaire=Decimal('100'), type_ligne='produit', variante=variante)
        return devis

    def test_devis_a_un_onduleur_sert_l_onduleur_le_nombre_et_la_provenance(self):
        calepinage = self._calepinage(devis=self._devis(self.module_devis, self.onduleur))
        reponse = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        bloc = reponse.data['devis_retenu']
        self.assertEqual((bloc['onduleur']['produit_id'], bloc['nombre_onduleurs'], bloc['provenance']),
                         (self.onduleur.pk, 1, 'devis'))
        self.assertEqual(bloc['ecarts'], [])
        self.assertEqual(reponse.data['materiel']['onduleur']['provenance'], PROVENANCE_DEVIS)
        self.assertEqual(sorted(bloc), sorted(json.loads(CONTRAT.read_text(encoding='utf-8'))
                                              ['exemple']['devis_retenu']))

    def test_option_avec_retenue_sert_l_onduleur_hybride(self):
        calepinage = self._calepinage(devis=self._devis_deux_options('Avec batterie'))
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual((materiel['produits']['onduleur'], materiel['provenances']['onduleur']),
                         (self.hybride.pk, PROVENANCE_DEVIS))

    def test_saisie_contraire_servie_et_ecart_nomme(self):
        calepinage = self._calepinage(
            devis=self._devis(self.module_devis, self.onduleur),
            entree={'onduleur_produit': self.hybride.pk, 'nombre_onduleurs': 2})
        reponse = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.data['materiel']['onduleur']['produit_id'], self.hybride.pk)
        self.assertEqual(reponse.data['materiel']['onduleur']['provenance'], PROVENANCE_EXPLICITE)
        ecarts = reponse.data['devis_retenu']['ecarts']
        self.assertEqual(len(ecarts), 2, ecarts)
        self.assertIn('au devis DEV-ACAL56-1', ecarts[0])
        self.assertIn('Onduleur hybride 10 kW', ecarts[0])

    def test_sans_devis_inchange(self):
        reponse = self.api.get(url_entree(self._calepinage().pk))
        self.assertIsNone(reponse.data['devis_retenu'])
