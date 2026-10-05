# -*- coding: utf-8 -*-
"""ACAL150 — l'entrée électrique validée À L'ÉCRITURE, lue sans jamais 500.

Avant : ``enregistrer_entree`` ÉCRIVAIT d'abord, puis le recalcul levait —
400 ou 500, mais la saisie fautive restait en base et cassait toutes les
lectures suivantes. Désormais chaque saisie est jugée par les validateurs DU
CALCUL (températures ``_saisie``, check-list de protections, check-list de
terre, polystring) AVANT tout enregistrement ; et une décision stockée devenue
périmée devient un avertissement nommé à la lecture.

Base RÉELLE : Produit / FicheTechnique / réglages société créés, aucune
source mockée.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, EntreeInvalide, enregistrer_entree,
)
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [{
        'id': 'z1', 'label': 'Sud', 'neededPanels': 12,
        'result': {'count': 12},
        'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0,
    }],
}

#: Les huit saisies refusées, et le champ que le refus doit NOMMER.
SAISIES_REFUSEES = (
    ({'temperature_min_c': -10}, 'temperature_max_c'),
    ({'terre': {'continuite_structure_barrette_ohm': 0.2}},
     'terre.date_continuite_structure_barrette'),
    ({'protections': 'oops'}, 'protections'),
    ({'exigence_marche': 'x'}, 'exigence_marche'),
    ({'phases': 7}, 'phases'),
    ({'dc_m': -5}, 'dc_m'),
    ({'dc_m': 'NaN'}, 'dc_m'),
    ({'protections': {'ecartes': [{'repere': 'ZZ9', 'motif': 'm'}]}},
     'protections.ecartes.repere'),
)


def url_entree(pk):
    return f'{url_detail(pk)}entree-electrique/'


def url_resultat(pk):
    return f'{url_detail(pk)}resultat/'


class BaseValidation(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        ParametresCalepinage.objects.create(
            company=self.company,
            norme_electrique={'norme': 'nf_c_15_100'})
        module = self._produit(
            nom='Module 710', type_fiche='module', vmp_v=41.4, voc_v=49.3,
            isc_a=18.59, imp_a=17.59, pmax_wc=710.0)
        onduleur = self._produit(
            nom='Onduleur 10 kW', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
            ond_v_max_abs=1100.0, ond_i_max_mppt_a=26.0, ond_ac_kw=10.0,
            ond_phases=3)
        self.entree_initiale = {
            'module_produit': module.pk, 'onduleur_produit': onduleur.pk,
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
            'phases': 3,
        }
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT,
            resultat={CLE_ENTREE: dict(self.entree_initiale)})

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL150-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit


class Ecriture(BaseValidation):

    def test_refus_nomme_le_champ_et_n_ecrit_rien(self):
        for saisie, champ in SAISIES_REFUSEES:
            with self.subTest(saisie=saisie):
                # Une saisie de température partielle : on retire d'abord la
                # paire stockée pour que le minimum posté soit SEUL.
                if 'temperature_min_c' in saisie:
                    stocke = {cle: valeur for cle, valeur
                              in self.entree_initiale.items()
                              if not cle.startswith('temperature_')}
                    Calepinage.objects.filter(pk=self.calepinage.pk).update(
                        resultat={CLE_ENTREE: stocke})
                else:
                    Calepinage.objects.filter(pk=self.calepinage.pk).update(
                        resultat={CLE_ENTREE: dict(self.entree_initiale)})
                self.calepinage.refresh_from_db()
                avant = dict(self.calepinage.resultat[CLE_ENTREE])
                reponse = self.api.post(url_entree(self.calepinage.pk),
                                        saisie, format='json')
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertIn(champ, reponse.data)
                self.calepinage.refresh_from_db()
                self.assertEqual(self.calepinage.resultat[CLE_ENTREE], avant)
                lecture = self.api.get(url_resultat(self.calepinage.pk))
                self.assertEqual(lecture.status_code, 200)

    def test_nan_inf_refuses(self):
        for valeur in (float('nan'), float('inf'), float('-inf')):
            for cle in ('dc_m', 'ac_m'):
                with self.subTest(cle=cle, valeur=valeur):
                    with self.assertRaises(EntreeInvalide) as refus:
                        enregistrer_entree(self.calepinage, {cle: valeur})
                    self.assertEqual(refus.exception.champ, cle)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.resultat[CLE_ENTREE],
                         self.entree_initiale)

    def test_un_accord_se_relit_a_l_identique(self):
        reponse = self.api.post(url_entree(self.calepinage.pk),
                                {'dc_m': 25.0, 'phases': 3}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.resultat[CLE_ENTREE]['dc_m'], 25.0)


class Lecture(BaseValidation):

    def test_decision_perimee_devient_avertissement(self):
        entree = dict(self.entree_initiale, protections={
            'ecartes': [{'repere': 'ZZ9', 'motif': 'organe retiré'}]})
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            resultat={CLE_ENTREE: entree})
        reponse = self.api.get(url_resultat(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIn('décision périmée : organe ZZ9',
                      reponse.data['avertissements'])
        # La décision reste STOCKÉE : elle reviendra avec l'organe.
        self.calepinage.refresh_from_db()
        self.assertEqual(
            self.calepinage.resultat[CLE_ENTREE]['protections']['ecartes'][0]
            ['repere'], 'ZZ9')

    def test_resultat_reste_200_apres_saisie_ancienne(self):
        entree = dict(self.entree_initiale, protections='oops',
                      terre={'continuite_structure_barrette_ohm': 0.2})
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            resultat={CLE_ENTREE: entree})
        reponse = self.api.get(url_resultat(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        textes = ' '.join(reponse.data['avertissements'])
        self.assertIn('décision illisible', textes)
        self.assertIn('terre', textes)
