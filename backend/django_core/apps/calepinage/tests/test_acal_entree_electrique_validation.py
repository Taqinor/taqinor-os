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

import json
import pathlib
from decimal import Decimal

from django.test import SimpleTestCase

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

    def test_caractere_nul_est_un_conflit_409_et_n_ecrit_rien(self):
        """ENF11 (api-fuzz-full 24/10) : un NUL (clé OU valeur, à toute
        profondeur) ne se range pas en JSONB et un sous-objet libre ne peut
        pas le dire au schéma : 409, jamais 400 « conforme » ni 500."""
        for saisie in ({'regime': 'T\x00T'}, {'exigence_marche': {'a\x00': 1}},
                       {'cheminement': {'pans': {'x': {'note': 'a\x00'}}}}):
            with self.subTest(saisie=saisie):
                reponse = self.api.post(url_entree(self.calepinage.pk),
                                        saisie, format='json')
                self.assertEqual(reponse.status_code, 409, reponse.data)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.resultat[CLE_ENTREE],
                         self.entree_initiale)

    def test_corps_publie_type_chaque_champ_et_ce_qu_il_publie_est_accepte(self):
        """Le corps du schéma type CHAQUE champ de l'entrée (plus de ``{}``
        libre : ``temperature_max_c: []`` était « conforme » puis refusé) et
        un représentant de chaque forme publiée est accepté par le serveur."""
        from apps.calepinage.champs_entree import corps_entree_resserre
        from apps.calepinage.services.electrique import CHAMPS_ENTREE

        regle = corps_entree_resserre()
        self.assertEqual(set(regle['properties']), set(CHAMPS_ENTREE))
        self.assertFalse(regle['additionalProperties'])
        for cle, forme in regle['properties'].items():
            self.assertTrue(forme, f'{cle} est publié libre ({{}})')
        accepte = {
            'temperature_min_c': -10, 'temperature_max_c': 55, 'dc_m': 12.5,
            'ac_m': 3, 'phases': 3, 'regime': 'TN', 'zone_keraunique': True,
            'inclure_prise_terre': False, 'longueur_chaine_forcee': 12,
            'plafond_kwc_par_onduleur': 8.5, 'cheminement': {},
            'transformateur': {'declare': False},
            'batterie': {'strategie': 'autoconso', 'couplage': 'ac',
                         'packs': 2, 'heures_charge': [10, 11]},
            'hors_reseau': {'actif': False, 'jours_autonomie': 2},
        }
        entree = enregistrer_entree(self.calepinage, accepte)
        self.assertEqual(entree['regime'], 'TN')
        self.assertEqual(entree['batterie']['packs'], 2)
        # ACAL786 — les cinq clés de secours et de commande sont typées, et
        # les deux corps d'essai du contrat sont acceptés (200).
        batterie = regle['properties']['batterie']['properties']
        for cle in ('appareils', 'duree_secours_h', 'fenetres',
                    'part_effacable_pct', 'plafond_effacable_kw',
                    'coupures'):  # coupures : ACAL796
            self.assertTrue(batterie[cle], cle)
        contrat = json.loads((pathlib.Path(__file__).resolve().parents[1]
                              / 'contract_samples'
                              / 'calepinage_entree_electrique.json')
                             .read_text(encoding='utf-8'))
        # ACAL790 — les seuils hors réseau sont publiés et leur corps accepté.
        self.assertTrue(regle['properties']['hors_reseau']['properties'][
            'seuils'])
        self.assertTrue(regle['properties']['hors_reseau']['properties'][
            'groupe'])  # ACAL800
        for cle in ('exemple_secours', 'exemple_commande_avancee',
                    'exemple_hors_reseau_avance'):
            with self.subTest(corps=cle):
                reponse = self.api.post(url_entree(self.calepinage.pk),
                                        contrat[cle], format='json')
                self.assertEqual(reponse.status_code, 200, reponse.data)


class AffectationManuelleEcrite(BaseValidation):
    """ACAL1627 — un drapeau « optimiseur » non booléen est refusé à
    l'ÉCRITURE (400 nommant le champ et le module), rien n'est stocké ;
    ``true`` / ``false`` / absent sont acceptés."""

    def _ligne(self, **extra):
        return dict({'module': 'z1#2', 'chaine': 1, 'mppt': 1,
                     'onduleur': 1}, **extra)

    def test_optimiseur_oui_400_et_rien_n_est_stocke(self):
        avant = dict(self.calepinage.resultat[CLE_ENTREE])
        reponse = self.api.post(url_entree(self.calepinage.pk), {
            'affectation_manuelle': [self._ligne(optimiseur='oui')]},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('optimiseur', reponse.data)
        self.assertIn('z1#2', reponse.data['optimiseur'])
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.resultat[CLE_ENTREE], avant)

    def test_vrai_faux_ou_absent_acceptes(self):
        for extra in ({'optimiseur': True}, {'optimiseur': False}, {}):
            with self.subTest(extra=extra):
                reponse = self.api.post(url_entree(self.calepinage.pk), {
                    'affectation_manuelle': [self._ligne(**extra)]},
                    format='json')
                self.assertEqual(reponse.status_code, 200, reponse.data)


class AffectationManuelleEcriteSansBase(SimpleTestCase):
    """ACAL1627 — la même règle, jugée par ``_valider_entree`` seul."""

    def test_le_refus_nomme_le_champ_et_le_module(self):
        from apps.calepinage.services.electrique import _valider_entree

        lignes = [{'module': 'area-2#48', 'chaine': 1, 'optimiseur': 'oui'}]
        saisie = {'temperature_min_c': -5.0, 'temperature_max_c': 70.0}
        with self.assertRaises(EntreeInvalide) as refus:
            _valider_entree(None, dict(saisie, affectation_manuelle=lignes),
                            {'affectation_manuelle': lignes})
        self.assertEqual(refus.exception.champ, 'optimiseur')
        self.assertIn('area-2#48', str(refus.exception))
        lignes[0]['optimiseur'] = True
        _valider_entree(None, dict(saisie, affectation_manuelle=lignes),
                        {'affectation_manuelle': lignes})


class EvaluationAChaud(BaseValidation):
    """ACAL615 — un onduleur désigné À CHAUD (``evaluer-electrique``) est
    validé comme à l'enregistrement, rend SON verdict et n'écrit rien."""

    def test_onduleur_b_rend_son_verdict_sans_rien_ecrire(self):
        # B : onduleur de la société dont la fiche est incomplète (pas de
        # tension maximale absolue) — son verdict ne peut être que
        # « indéterminé », celui de A non.
        onduleur_b = self._produit(
            nom='Onduleur B', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0, ond_ac_kw=10.0,
            ond_phases=3)
        url = f'{url_detail(self.calepinage.pk)}evaluer-electrique/'
        self.calepinage.refresh_from_db()
        avant = self.calepinage.resultat
        avec_a = self.api.post(url, {}, format='json')
        self.assertEqual(avec_a.status_code, 200, avec_a.data)
        avec_b = self.api.post(url, {'entree_electrique': {
            'onduleur_produit': onduleur_b.pk}}, format='json')
        self.assertEqual(avec_b.status_code, 200, avec_b.data)
        self.assertNotEqual(avec_a.data['verdict'], 'indetermine')
        self.assertEqual(avec_b.data['verdict'], 'indetermine')
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.resultat, avant)

    def test_id_illisible_ou_absent_404_nomme_jamais_500(self):
        url = f'{url_detail(self.calepinage.pk)}evaluer-electrique/'
        for valeur in ('abc', 999999):
            with self.subTest(valeur=valeur):
                r = self.api.post(url, {'entree_electrique': {
                    'onduleur_produit': valeur}}, format='json')
                self.assertEqual(r.status_code, 404, r.data)
                self.assertEqual(
                    r.data['onduleur_produit'],
                    'Produit introuvable dans votre catalogue (#%s).' % valeur)
        for vide in ('', None):
            with self.subTest(vide=vide):
                r = self.api.post(url, {'entree_electrique': {
                    'onduleur_produit': vide}}, format='json')
                self.assertEqual(r.status_code, 200, r.data)


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
