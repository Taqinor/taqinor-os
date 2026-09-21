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
from apps.calepinage.services.chaines import empreinte_entree
from apps.calepinage.services.electrique import (
    METHODE_ECRETAGE_SERIE, MOTIF_ECRETAGE_SANS_SERIE, _options_entree,
    temperatures_site,
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


class _Calepinage:
    """Un calepinage dont la simulation persistée décrit ENCORE ce toit."""

    pk = 172
    statut = 'brouillon'

    def __init__(self, materiel, avec_serie=True):
        self.roof_layout = LAYOUT
        self.company = None
        entree = {'temperature_min_c': -5.0, 'temperature_max_c': 70.0}
        self.resultat = {'entree_electrique': entree}
        empreinte = empreinte_entree(
            LAYOUT, module_specs=materiel['module'],
            onduleur_specs=materiel['onduleur'],
            temperatures=temperatures_site(saisie=entree),
            options=_options_entree(entree))
        self.resultat['simulation'] = {'hash_entree': empreinte,
                                       'calcule_le': '2026-09-21T10:00:00'}
        if avec_serie:
            self.resultat['serie_horaire'] = {
                'pas_minutes': 60,
                'points': [{'annee': 2020, 'mois': 6, 'jour': 21,
                            'heure': heure, 'p_dc_kw': valeur}
                           for heure, valeur in enumerate(
                               (0.0, 5.0, 14.0, 20.0, 16.0, 4.0))],
            }


class SerieServieAuRatioTest(SimpleTestCase):
    """Le bloc ratio reçoit enfin une série, et le DIT."""

    def test_un_resultat_simule_publie_la_methode_horaire(self):
        from apps.calepinage.services.electrique import resultat_calepinage

        materiel = _materiel()
        resultat = resultat_calepinage(_Calepinage(materiel),
                                       materiel=materiel)

        self.assertEqual(resultat['ratio_dc_ac']['ecretage_methode'],
                         METHODE_ECRETAGE_SERIE)
        self.assertIsNotNone(resultat['ratio_dc_ac']['ecretage_pct'])

    def test_sans_serie_persistee_le_motif_de_refus_est_conserve(self):
        from apps.calepinage.services.electrique import resultat_calepinage

        materiel = _materiel()
        resultat = resultat_calepinage(
            _Calepinage(materiel, avec_serie=False), materiel=materiel)

        self.assertEqual(resultat['ratio_dc_ac']['ecretage_methode'],
                         MOTIF_ECRETAGE_SANS_SERIE)
        self.assertIsNone(resultat['ratio_dc_ac']['ecretage_pct'])

    def test_une_fiche_sans_ond_ac_kw_garde_le_motif_de_refus_existant(self):
        from apps.calepinage.services.electrique import resultat_calepinage

        materiel = _materiel()
        materiel['onduleur'] = {cle: valeur
                                for cle, valeur in materiel['onduleur'].items()
                                if cle != 'ac_kw'}
        resultat = resultat_calepinage(_Calepinage(materiel),
                                       materiel=materiel)

        self.assertEqual(resultat['ratio_dc_ac']['ecretage_methode'],
                         MOTIF_ECRETAGE_SANS_SERIE)
        self.assertIsNone(resultat['ratio_dc_ac']['ecretage_pct'])
