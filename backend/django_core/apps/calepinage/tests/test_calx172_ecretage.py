# -*- coding: utf-8 -*-
"""CALX172 — l'étape « écrêtage » branchée sur la série horaire.

``ecretage_depuis_serie`` calculait la perte heure par heure depuis CAL127 et
n'a JAMAIS reçu de série : ``ecretage_pct`` valait toujours ``null``. Deux
moitiés sont vérifiées ici :

1. **l'étape** ``services/etapes/ecretage.py`` — testée ISOLÉMENT (jamais le
   total de la chaîne, que d'autres lanes font bouger) :
   * propriété : à puissance AC CROISSANTE l'énergie écrêtée DÉCROÎT de façon
     monotone et atteint 0 dès que la puissance AC dépasse le maximum de la
     série ;
   * la borne vaut ``min(puissance_ac_kw, s_max_kva × cos_phi_impose)`` quand
     le cos φ est SAISI au raccordement, et ``puissance_ac_kw`` avec la
     mention « cos φ non saisi » sinon — jamais un 1,0 supposé ;
   * fiche sans puissance AC ⇒ étape OMISE, série INCHANGÉE, et le motif est
     celui que le dépôt prononce déjà pour cette perte ;
2. **le passage de la série** à ``bloc_ratio_dc_ac`` — un résultat dont la
   simulation persistée décrit encore ce toit publie
   ``ratio_dc_ac.ecretage_methode == « calculée heure par heure… »`` ; une
   fiche sans ``ond_ac_kw`` garde le motif de refus existant.

``SimpleTestCase`` : aucune base.

Run :
    python manage.py test apps.calepinage.tests.test_calx172_ecretage -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services import etapes
from apps.calepinage.services.electrique import (
    METHODE_ECRETAGE_SERIE, MOTIF_ECRETAGE_SANS_SERIE,
)
from apps.calepinage.services.etapes import ecretage
from apps.calepinage.services.etapes.ecretage import (
    CHAMP_PUISSANCE_AC, COLONNE_ECRETAGE, MENTION_COS_PHI_ABSENT,
    MENTION_S_MAX_ABSENTE,
)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}

#: Une journée simplifiée : six heures de puissance continue croissante.
PUISSANCES_KW = (0.0, 2.0, 6.0, 12.0, 9.0, 3.0)
MAXIMUM_KW = max(PUISSANCES_KW)


def _serie():
    return {
        'pas_minutes': 60,
        'colonne_energie': 'p_ac_kw',
        'points': [{'annee': 2020, 'mois': 6, 'jour': 21, 'heure': heure,
                    'p_ac_kw': valeur}
                   for heure, valeur in enumerate(PUISSANCES_KW)],
    }


def _contexte(ac_kw=10.0, nombre=1, s_max_kva=None, raccordement=None):
    fiche = {'ac_kw': ac_kw} if ac_kw is not None else {}
    if s_max_kva is not None:
        fiche['s_max_kva'] = s_max_kva
    return {
        'fiche_onduleur': fiche,
        'electrique': {'onduleurs': [{'reference': 'Onduleur d essai',
                                      'taille_kw': ac_kw or 0.0,
                                      'nombre': nombre}]},
        'raccordement': raccordement,
    }


def _energie_ecretee_kwh(serie_avant, serie_apres):
    """L'énergie RETIRÉE par l'étape, lue sur la seule colonne d'énergie."""
    return (etapes.energie_kwh(serie_avant)
            - etapes.energie_kwh(serie_apres))


class ProprieteMonotoneTest(SimpleTestCase):
    """À puissance AC croissante, l'énergie écrêtée décroît — et atteint 0."""

    def test_l_energie_ecretee_decroit_de_facon_monotone(self):
        avant = _serie()
        ecretees = []
        for ac_kw in (2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0):
            apres, etape = ecretage.appliquer(avant, _contexte(ac_kw=ac_kw))
            self.assertEqual(etape['motif_omission'], '')
            ecretees.append(_energie_ecretee_kwh(avant, apres))

        for precedente, suivante in zip(ecretees, ecretees[1:]):
            self.assertLessEqual(suivante, precedente + 1e-9)

    def test_l_ecretage_atteint_zero_au_dessus_du_maximum_de_la_serie(self):
        avant = _serie()
        apres, etape = ecretage.appliquer(
            avant, _contexte(ac_kw=MAXIMUM_KW + 1.0))

        self.assertAlmostEqual(_energie_ecretee_kwh(avant, apres), 0.0,
                               places=9)
        self.assertEqual(etape['entree']['heures_ecretees'], 0)
        self.assertAlmostEqual(etape['entree']['ecretage_pct'], 0.0,
                               places=9)

    def test_l_energie_est_retiree_heure_par_heure(self):
        avant = _serie()
        apres, _etape = ecretage.appliquer(avant, _contexte(ac_kw=6.0))

        plafonnees = [point['p_ac_kw'] for point in apres['points']]
        self.assertEqual(plafonnees, [0.0, 2.0, 6.0, 6.0, 6.0, 3.0])

    def test_la_colonne_ecretage_est_ecrite_sur_chaque_point(self):
        apres, _etape = ecretage.appliquer(_serie(), _contexte(ac_kw=6.0))

        ecretes = [point[COLONNE_ECRETAGE] for point in apres['points']]
        self.assertEqual(ecretes, [0.0, 0.0, 0.0, 6.0, 3.0, 0.0])

    def test_la_serie_d_entree_n_est_jamais_mutee(self):
        avant = _serie()
        ecretage.appliquer(avant, _contexte(ac_kw=6.0))

        self.assertEqual([point['p_ac_kw'] for point in avant['points']],
                         list(PUISSANCES_KW))
        self.assertNotIn(COLONNE_ECRETAGE, avant['points'][0])


class BorneDEcretageTest(SimpleTestCase):
    """``min(puissance_ac_kw, s_max_kva × cos φ)`` — et jamais un 1,0 supposé."""

    def test_sans_cos_phi_la_borne_est_la_puissance_active(self):
        _apres, etape = ecretage.appliquer(
            _serie(), _contexte(ac_kw=8.0, s_max_kva=6.0))

        self.assertAlmostEqual(etape['entree']['borne_kw'], 8.0, places=3)
        self.assertEqual(etape['entree']['base_borne'], CHAMP_PUISSANCE_AC)
        self.assertEqual(etape['entree']['mention'], MENTION_COS_PHI_ABSENT)

    def test_avec_cos_phi_saisi_la_borne_apparente_peut_l_emporter(self):
        _apres, etape = ecretage.appliquer(_serie(), _contexte(
            ac_kw=10.0, s_max_kva=10.0,
            raccordement={'cos_phi_impose': 0.8,
                          'source_cos_phi': 'contrat de raccordement'}))

        # min(10 kW, 10 kVA × 0,8) = 8 kW.
        self.assertAlmostEqual(etape['entree']['borne_kw'], 8.0, places=3)
        self.assertIn('cos φ', etape['entree']['mention'])
        self.assertIn('contrat de raccordement', etape['entree']['mention'])

    def test_un_cos_phi_saisi_sans_source_ne_s_applique_pas(self):
        _apres, etape = ecretage.appliquer(_serie(), _contexte(
            ac_kw=10.0, s_max_kva=10.0,
            raccordement={'cos_phi_impose': 0.8}))

        self.assertAlmostEqual(etape['entree']['borne_kw'], 10.0, places=3)
        self.assertEqual(etape['entree']['mention'], MENTION_COS_PHI_ABSENT)

    def test_sans_s_max_publiee_la_borne_reste_la_puissance_active(self):
        _apres, etape = ecretage.appliquer(_serie(), _contexte(
            ac_kw=10.0,
            raccordement={'cos_phi_impose': 0.8,
                          'source_cos_phi': 'contrat de raccordement'}))

        self.assertAlmostEqual(etape['entree']['borne_kw'], 10.0, places=3)
        self.assertEqual(etape['entree']['mention'], MENTION_S_MAX_ABSENTE)

    def test_la_borne_suit_le_nombre_d_onduleurs(self):
        _apres, etape = ecretage.appliquer(
            _serie(), _contexte(ac_kw=5.0, nombre=2))

        self.assertAlmostEqual(etape['entree']['borne_kw'], 10.0, places=3)
        self.assertEqual(etape['entree']['nombre_onduleurs'], 2)


class DistributionTest(SimpleTestCase):
    """ACAL736 — l'histogramme de l'énergie par classe de puissance DEMANDÉE
    (avant plafonnement), référence calculée ICI par ``floor(p / 0,25)``."""

    PUISSANCES = (1.0, 4.9, 5.0, 5.2, 7.0)

    def _serie(self, puissances):
        return {'pas_minutes': 60, 'colonne_energie': 'p_ac_kw',
                'points': [{'heure': h, 'p_ac_kw': p}
                           for h, p in enumerate(puissances)]}

    def test_classes_energie_ecretee_et_part(self):
        import math

        _apres, etape = ecretage.appliquer(self._serie(self.PUISSANCES),
                                           _contexte(ac_kw=5.0))
        servie = etape['entree']['distribution']
        largeur = 5.0 / 20
        attendues = {}
        for p in self.PUISSANCES:
            rang = math.floor(p / largeur)
            attendues[rang] = attendues.get(rang, 0.0) + p
        self.assertEqual(servie['borne_kw'], 5.0)
        self.assertEqual(servie['largeur_kw'], 0.25)
        self.assertEqual(
            [(c['de_kw'], c['a_kw'], c['energie_kwh'])
             for c in servie['classes']],
            [(round(r * largeur, 3), round((r + 1) * largeur, 3), round(e, 3))
             for r, e in sorted(attendues.items())])
        # 5,0 kW (la borne) ouvre la classe [5,0 ; 5,25[.
        self.assertIn((5.0, 5.25), [(c['de_kw'], c['a_kw'])
                                    for c in servie['classes']])
        self.assertEqual(servie['energie_totale_kwh'], 23.1)
        self.assertEqual(servie['energie_ecretee_kwh'], 2.2)
        self.assertEqual(servie['part_ecretee_pct'], 9.524)
        self.assertEqual(servie['part_ecretee_pct'],
                         etape['entree']['ecretage_pct'])

    def test_les_heures_a_zero_ne_comptent_pas(self):
        _apres, etape = ecretage.appliquer(
            self._serie((0.0,) + self.PUISSANCES), _contexte(ac_kw=5.0))
        self.assertNotIn(0.0, [c['de_kw'] for c in
                               etape['entree']['distribution']['classes']])

    def test_sans_production_distribution_nulle_avec_motif(self):
        _apres, etape = ecretage.appliquer(self._serie((0.0, 0.0)),
                                           _contexte(ac_kw=5.0))
        self.assertIsNone(etape['entree']['distribution'])
        self.assertTrue(etape['entree']['motif_distribution'])

    def test_contrat_porte_la_distribution(self):
        import json
        import pathlib

        chemin = (pathlib.Path(__file__).resolve().parent.parent
                  / 'contract_samples' / 'calepinage_pertes_cascade.json')
        exemple = json.loads(chemin.read_text(encoding='utf-8'))[
            'exemple_entrees_onduleur']['ecretage']['distribution']
        _apres, etape = ecretage.appliquer(self._serie(self.PUISSANCES),
                                           _contexte(ac_kw=5.0))
        self.assertEqual(exemple, etape['entree']['distribution'])


class FicheSansPuissanceAcTest(SimpleTestCase):
    """Pas de plafond publié ⇒ étape OMISE, série intacte, motif EXISTANT."""

    def test_l_etape_est_omise_avec_le_motif_du_depot(self):
        avant = _serie()
        apres, etape = ecretage.appliquer(avant, _contexte(ac_kw=None))

        self.assertIn(MOTIF_ECRETAGE_SANS_SERIE, etape['motif_omission'])
        self.assertIn(CHAMP_PUISSANCE_AC, etape['motif_omission'])
        self.assertIs(apres, avant)

    def test_une_serie_sans_colonne_lisible_omet_aussi(self):
        avant = {'pas_minutes': 60, 'points': [{'annee': 2020}]}
        apres, etape = ecretage.appliquer(avant, _contexte())

        self.assertTrue(etape['motif_omission'])
        self.assertIs(apres, avant)

    def test_sans_bloc_onduleur_l_etape_s_omet_en_le_nommant(self):
        avant = _serie()
        apres, etape = ecretage.appliquer(avant, {'fiche_onduleur': {}})

        self.assertIn('electrique.onduleurs', etape['motif_omission'])
        self.assertIs(apres, avant)


# ══════════════════════════════════════════════════════════════════════════
# Le PASSAGE de la série à ``bloc_ratio_dc_ac`` (même tâche, CALX172)
# ══════════════════════════════════════════════════════════════════════════

LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-SUD', 'geometry': {'count': 24, 'azimuthDeg': 180.0,
                                      'tiltDeg': 15.0}}]}


def _materiel(**onduleur):
    return {
        'module': MODULE, 'onduleur': dict(ONDULEUR, **onduleur),
        'optimiseur': None,
        'designations': {'module': 'Module d essai',
                         'onduleur': 'Onduleur d essai', 'optimiseur': ''},
        'absents': (),
    }


def _simule(materiel, *, simuler=True):
    """ACAL141 — un pivot SIMULÉ par la vraie chaîne (client rejoué, crête
    1 000 W/m²) : l'écrêtage du ratio vient de l'étape « ecretage » de la
    cascade fraîche, plus d'une colonne ``p_dc_kw`` écrite à la main."""
    from apps.calepinage.services.simulation import simuler_calepinage

    from .test_acal_multi_pans import _ClientParOrientation
    from .test_calx5_simulation import REGLAGES, _Calepinage

    pivot = _Calepinage(layout={'version': 2, 'pin': {'lat': 33.5731,
                                                      'lng': -7.5898},
                                'zones': LAYOUT['zones']})
    if simuler:
        simuler_calepinage(pivot, client=_ClientParOrientation(1000.0),
                           materiel=materiel, reglages=REGLAGES,
                           enregistrer=True)
    return pivot


class SerieServieAuRatioTest(SimpleTestCase):
    """Le bloc ratio lit l'écrêtage de la cascade FRAÎCHE, et le DIT."""

    def _servi(self, materiel, **kwargs):
        from apps.calepinage.services.electrique import resultat_calepinage

        from .test_calx5_simulation import REGLAGES

        pivot = _simule(materiel, **kwargs)
        return pivot, resultat_calepinage(pivot, materiel=materiel,
                                          reglages=REGLAGES)

    def test_un_resultat_simule_publie_la_methode_horaire(self):
        pivot, resultat = self._servi(_materiel(ac_kw=5.0))

        etape = next(e for e in pivot.resultat['cascade']['etapes']
                     if e['etape'] == 'ecretage')
        self.assertEqual(resultat['ratio_dc_ac']['ecretage_methode'],
                         METHODE_ECRETAGE_SERIE)
        self.assertEqual(resultat['ratio_dc_ac']['ecretage_pct'],
                         etape['entree']['ecretage_pct'])
        self.assertGreater(resultat['ratio_dc_ac']['ecretage_pct'], 0.0)

    def test_sans_serie_persistee_le_motif_de_refus_est_conserve(self):
        _pivot, resultat = self._servi(_materiel(ac_kw=5.0), simuler=False)

        self.assertEqual(resultat['ratio_dc_ac']['ecretage_methode'],
                         MOTIF_ECRETAGE_SANS_SERIE)
        self.assertIsNone(resultat['ratio_dc_ac']['ecretage_pct'])

    def test_une_fiche_sans_ond_ac_kw_garde_le_motif_de_refus_existant(self):
        materiel = _materiel()
        materiel['onduleur'] = {cle: valeur
                                for cle, valeur in materiel['onduleur'].items()
                                if cle != 'ac_kw'}
        # Sans puissance AC, aucun onduleur n'est dimensionné : rien à
        # simuler, et le ratio garde son motif de refus.
        _pivot, resultat = self._servi(materiel, simuler=False)

        self.assertEqual(resultat['ratio_dc_ac']['ecretage_methode'],
                         MOTIF_ECRETAGE_SANS_SERIE)
        self.assertIsNone(resultat['ratio_dc_ac']['ecretage_pct'])


def _client_en_cache_classe():
    from .test_acal_multi_pans import _ClientParOrientation

    class _ClientEnCache(_ClientParOrientation):
        """Rejoue la série ENREGISTRÉE ; compte seulement les défauts de
        cache (un appel réseau réel par orientation distincte)."""

        def __init__(self, crete):
            super().__init__(crete)
            self.urls_appelees = []
            self._vues = {}

        def serie_irradiance(self, **parametres):
            cle = repr(sorted(parametres.items()))
            if cle not in self._vues:
                self.urls_appelees.append('/seriescalc?' + cle)
                self._vues[cle] = super().serie_irradiance(**parametres)
            return self._vues[cle]

    return _ClientEnCache


class BalayageRatioDcAcTest(SimpleTestCase):
    """ACAL477 — l'axe ``ratio_dc_ac`` du balayage : l'écrêtage CROÎT avec le
    ratio, sur la MÊME série (aucun appel PVGIS de plus)."""

    CORPS = {'pan': 1, 'axes': [{'nom': 'ratio_dc_ac', 'min': 1.0,
                                 'max': 1.6, 'pas': 0.3}]}

    def _balayer(self, materiel, corps=None, mutant=False):
        from apps.calepinage.services.balayage import balayer
        from apps.calepinage.services.simulation import simuler_calepinage

        from .test_calx5_simulation import REGLAGES, _Calepinage

        pivot = _Calepinage(layout={'version': 2, 'pin': {
            'lat': 33.5731, 'lng': -7.5898}, 'zones': LAYOUT['zones']})
        client = _client_en_cache_classe()(1000.0)

        def simuler(cal, *, variante, client, materiel=None):
            if mutant:  # puissance AC figée : le ratio ne change plus rien
                materiel = None
            return simuler_calepinage(
                cal, forcer=True, client=client, enregistrer=False,
                variante=variante, materiel=materiel or base,
                reglages=REGLAGES)

        base = materiel
        return balayer(pivot, corps or self.CORPS, client=client,
                       simuler=simuler, materiel=materiel)

    def test_l_ecretage_croit_avec_le_ratio_sans_appel_de_plus(self):
        sortie = self._balayer(_materiel(ac_kw=5.0))
        grille = sortie['grille']
        self.assertEqual([ligne['ratio_dc_ac'] for ligne in grille],
                         [1.0, 1.3, 1.6])
        ecretages = [ligne['ecretage_pct'] for ligne in grille]
        self.assertTrue(all(isinstance(e, float) for e in ecretages))
        self.assertLess(ecretages[0], ecretages[1])
        self.assertLess(ecretages[1], ecretages[2])
        self.assertTrue(all(ligne['mention_ratio'].endswith('hypothèse')
                            for ligne in grille))
        # deux défauts de cache pour trois ratios : la série du plan et la
        # série horizontale d'ACAL706 ; le balayage n'en ajoute AUCUN.
        self.assertEqual(sortie['appels_pvgis'], 2)

    def test_mutant_puissance_ac_figee_est_detecte(self):
        sortie = self._balayer(_materiel(ac_kw=5.0), mutant=True)
        ecretages = [ligne['ecretage_pct'] for ligne in sortie['grille']]
        self.assertEqual(len(set(ecretages)), 1)

    def test_sans_onduleur_l_axe_est_refuse_en_nommant_le_bloc(self):
        from apps.calepinage.services.balayage import BalayageInvalide

        materiel = _materiel()
        materiel['onduleur'] = {cle: valeur
                                for cle, valeur in materiel['onduleur'].items()
                                if cle != 'ac_kw'}
        with self.assertRaises(BalayageInvalide) as capture:
            self._balayer(materiel)
        self.assertEqual(capture.exception.champ, 'electrique.onduleurs')
