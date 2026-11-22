# -*- coding: utf-8 -*-
"""ACAL155 — ``resultat['raccordement_saisie']`` : L'UNIQUE saisie de
raccordement.

Avant : la simulation lisait ``roof_layout['raccordement']`` (qu'aucun
écrivain ne produit) et le verdict publiable ``entree_electrique
['raccordement']`` (hors ``CHAMPS_ENTREE``) — la saisie de l'écran n'atteignait
ni l'écrêtage, ni le plafond d'injection, ni le verdict.

Ici la saisie passe par la PORTE HTTP réelle (``POST raccordement/``), puis
la simulation et le verdict la lisent par ``services/raccordement.py::
saisie_du_calepinage`` — aucun contexte injecté à la main.
"""
from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, verdict_publiable,
)
from apps.calepinage.services.etapes import autoconsommation
from apps.calepinage.services.raccordement import CLE_SAISIE
from apps.calepinage.services.simulation import (
    construire_contexte, simuler_calepinage,
)
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage, url_detail
from .test_calx190_autoconsommation import contexte_de_test, serie_de_test
from .test_calx205_contrat_raccordement import RACCORDEMENT
from .test_calx5_simulation import (
    LAYOUT, MATERIEL, REGLAGES, _ClientRejoue,
)

SAISIE = {
    'cos_phi_impose': 0.9, 'source_cos_phi': 'contrat',
    'plafond_injection_kw': 3.0,
    'plafond_injection_justification': 'contrat',
}

#: Un onduleur dont la fiche publie sa puissance APPARENTE : c'est elle que
#: le cos φ saisi borne (CALX172).
MATERIEL_S_MAX = dict(MATERIEL, onduleur=dict(MATERIEL['onduleur'],
                                              s_max_kva=10.0))


def url_raccordement(pk):
    return f'{url_detail(pk)}raccordement/'


class Raccordement(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Usine',
            roof_layout=LAYOUT)

    def _poster(self, corps):
        reponse = self.api.post(url_raccordement(self.calepinage.pk), corps,
                                format='json')
        self.calepinage.refresh_from_db()
        return reponse

    def test_contexte_porte_la_saisie(self):
        reponse = self._poster(SAISIE)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        contexte, _meta = construire_contexte(
            self.calepinage, materiel=MATERIEL, reglages=REGLAGES)
        for cle, valeur in SAISIE.items():
            self.assertEqual(contexte['raccordement'][cle], valeur, cle)

    def test_ecretage_applique_cos_phi_saisi(self):
        self.assertEqual(self._poster(SAISIE).status_code, 200)
        rendu = simuler_calepinage(
            self.calepinage, forcer=True, enregistrer=False,
            client=_ClientRejoue(), materiel=MATERIEL_S_MAX,
            reglages=REGLAGES)
        etape = next(etape for etape in rendu['blocs']['cascade']['etapes']
                     if etape['etape'] == 'ecretage')
        self.assertEqual(etape['motif_omission'], '')
        self.assertIn('cos φ 0.9', etape['entree']['mention'])
        self.assertAlmostEqual(etape['entree']['borne_kw'], 9.0)

    def test_plafond_injection_limite_l_export(self):
        self.assertEqual(self._poster(SAISIE).status_code, 200)
        contexte_reel, _meta = construire_contexte(
            self.calepinage, materiel=MATERIEL, reglages=REGLAGES)
        contexte = contexte_de_test(heures=72)
        contexte[autoconsommation.CLE_RACCORDEMENT] = \
            contexte_reel['raccordement']
        suite, bloc = autoconsommation.bloc_autoconsommation(
            serie_de_test(heures=72), contexte)
        self.assertEqual(bloc['plafond']['plafond_kw'], 3.0)
        exports = [point['reseau_export_kwh'] for point in suite['points']]
        self.assertLessEqual(max(exports), 3.0 + 1e-6)

    def test_la_saisie_relue_est_celle_ecrite(self):
        self.assertEqual(self._poster(SAISIE).status_code, 200)
        stockee = dict(self.calepinage.resultat[CLE_SAISIE])
        lu = self.api.get(url_raccordement(self.calepinage.pk))
        for cle, valeur in SAISIE.items():
            self.assertEqual(lu.data['saisie'][cle], valeur, cle)
        # Les champs du contrat (ACAL827/828/829 en ont ajouté).
        self.assertEqual(sorted(lu.data['saisie']),
                         sorted(RACCORDEMENT['exemple']['saisie']))
        self._poster(lu.data['saisie'])
        self.assertEqual(self.calepinage.resultat[CLE_SAISIE], stockee)

    def test_refus_plafond_sans_justification_nomme_le_champ(self):
        reponse = self._poster({'plafond_injection_kw': 3.0})
        # ENF11 : règle liant deux champs (valeur sans source), non dite au schéma = 409
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(list(reponse.data),
                         ['plafond_injection_justification'])
        self.assertNotIn(CLE_SAISIE, self.calepinage.resultat or {})


class VerdictPublie(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        ParametresCalepinage.objects.create(
            company=self.company,
            norme_electrique={'norme': 'nf_c_15_100'})
        module = self._produit(
            nom='Module 710', type_fiche='module', vmp_v=41.4, voc_v=49.3,
            isc_a=18.59, imp_a=17.59, pmax_wc=710.0)
        onduleur = self._produit(
            nom='Onduleur 10 kW tri', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
            ond_v_max_abs=1100.0, ond_i_max_mppt_a=26.0, ond_ac_kw=10.0,
            ond_phases=3)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Usine',
            roof_layout={'pin': {'lat': 33.57, 'lng': -7.59},
                         'zones': [{'id': 'z1', 'label': 'Sud',
                                    'result': {'count': 12},
                                    'facingAzimuthDeg': 180.0,
                                    'pitchDeg': 15.0}]},
            resultat={CLE_ENTREE: {
                'module_produit': module.pk, 'onduleur_produit': onduleur.pk,
                'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
                'phases': 3}})

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL155-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def test_verdict_publiable_voit_les_bloquants_de_l_ecran(self):
        reponse = self.api.post(url_raccordement(self.calepinage.pk),
                                {'phases': 1, 'tension_nominale_v': 230.0},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        statuts = {verdict['code']: verdict['statut']
                   for verdict in reponse.data['verdicts']}
        self.assertEqual(statuts['regime_phases'], 'bloquant')
        self.assertEqual(statuts['tension_nominale'], 'bloquant')
        self.calepinage.refresh_from_db()
        verdict = verdict_publiable(self.calepinage)
        par_code = {motif['code']: motif for motif in verdict['motifs']}
        for code in ('regime_phases', 'tension_nominale'):
            self.assertIn(code, par_code)
            self.assertIn(par_code[code]['statut'],
                          ('bloquant', 'sans_source'))
        self.assertFalse(verdict['publiable'])


class PhasesDeSaisiesElectriquesTest(SimpleTestCase):
    """ACAL687 — les phases saisies dans « Saisies électriques » ne sont plus
    ignorées par le verdict de raccordement quand l'écran Raccordement ne les
    porte pas ; la saisie de l'écran reste prioritaire (ACAL155)."""

    @staticmethod
    def _conception():
        from apps.calepinage.services.chaines import concevoir_par_pan
        from apps.calepinage.services.electrique import temperatures_site

        return concevoir_par_pan(
            {'version': 2, 'zones': [{'id': 'z1', 'label': 'PAN-1',
                                      'geometry': {'count': 12,
                                                   'azimuthDeg': 180.0,
                                                   'tiltDeg': 15.0}}]},
            module_specs={
                'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
                'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
                'temp_coeff_pmax_pct_c': -0.35},
            onduleur_specs={
                'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
                'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0,
                'phases': 3},
            temperatures=temperatures_site(saisie={
                'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
            onduleur_designation='Onduleur d essai')

    def _verdict_phases(self, saisie, donnees):
        from apps.calepinage.services.electrique import (
            _phases_du_raccordement)
        from apps.calepinage.services.raccordement import (
            CODE_REGIME_PHASES, verdicts_raccordement)

        complete = _phases_du_raccordement(saisie, donnees)
        bloc = verdicts_raccordement(self._conception(), complete)
        return [v for v in bloc['verdicts']
                if v.code == CODE_REGIME_PHASES][0]

    def test_une_phase_saisie_ailleurs_est_jugee_et_sa_source_citee(self):
        verdict = self._verdict_phases({}, {'phases': 1})

        self.assertEqual(verdict.statut, 'bloquant')
        self.assertEqual(verdict.source,
                         'saisie — phases (Saisies électriques)')

    def test_la_saisie_de_raccordement_l_emporte_et_le_dit(self):
        verdict = self._verdict_phases({'phases': 3}, {'phases': 1})

        self.assertEqual(verdict.statut, 'ok')
        self.assertIn('prioritaire', verdict.source)

    def test_aucune_des_deux_saisies_garde_le_motif_d_aujourd_hui(self):
        from apps.calepinage.services.raccordement import MOTIF_SANS_PHASES

        verdict = self._verdict_phases({}, {})

        self.assertEqual(verdict.libelle, MOTIF_SANS_PHASES)

    def test_la_saisie_stockee_n_est_pas_modifiee(self):
        from apps.calepinage.services.electrique import (
            _phases_du_raccordement)

        saisie = {}
        _phases_du_raccordement(saisie, {'phases': 1})

        self.assertEqual(saisie, {})
