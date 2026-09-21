"""CALX191 — le défaut d'alimentation hors réseau sur la série réelle.

Ce qui est tenu ici :

* propriété : à capacité CROISSANTE (jours d'autonomie saisis croissants) le
  taux de défaillance DÉCROÎT de façon monotone, et atteint 0 pour une banque
  surdimensionnée ;
* un calepinage hors réseau ne publie AUCUN quantile (ni P50, ni P90) : le
  bloc le dit avec son motif, et l'autoconsommation réseau s'omet dans ce
  mode ;
* une autonomie NON SAISIE omet le bloc en NOMMANT le champ ;
* un calepinage raccordé n'a pas de bloc hors réseau, et la série ressort
  inchangée à chaque omission.

Série de test : une année 2021 SYNTHÉTIQUE, fabriquée pour le test et ne
décrivant AUCUNE installation réelle. Test PUR : aucune base, aucun réseau.
"""
from __future__ import annotations

import datetime

from django.test import SimpleTestCase

from apps.calepinage.services import chaine_pertes
from apps.calepinage.services.etapes import autoconsommation as bloc_conso
from apps.calepinage.services.etapes import batterie as bloc_bat
from apps.calepinage.services.etapes import hors_reseau as bloc

HEURES_DE_PRODUCTION = range(8, 18)

P_AC_KW = 4.0

CONSO_KWH = 1.0


def serie_de_test(*, annee=2021, heures=8760):
    """Une année horaire SYNTHÉTIQUE au format CALX142, côté ALTERNATIF."""
    depart = datetime.datetime(annee, 1, 1)
    points = []
    for rang in range(heures):
        moment = depart + datetime.timedelta(hours=rang)
        points.append({
            'annee': moment.year,
            'mois': moment.month,
            'jour': moment.day,
            'heure': moment.hour,
            'p_ac_kw': (P_AC_KW if moment.hour in HEURES_DE_PRODUCTION
                        else 0.0),
        })
    return {'points': points, 'pas_minutes': 60,
            'colonne_energie': 'p_ac_kw'}


def specs_de_test(*, capacite=10.0, puissance=50.0, rendement=90.0, dod=90.0):
    """La forme EXACTE que rend ``services/batterie.py::specs_batterie``."""
    def ligne(valeur):
        return {'valeur': valeur, 'source': 'fiche',
                'mention': 'Lu sur la fiche produit.'}

    return {
        'grandeurs': {
            'kwh_nominal': ligne(capacite / (dod / 100.0)),
            'kwh_usable': ligne(capacite),
            'dod_pct': ligne(dod),
            'rendement_ar_pct': ligne(rendement),
            'cycles_publies': ligne(6000.0),
            'max_charge_kw': ligne(puissance),
            'max_decharge_kw': ligne(puissance),
        },
        'nb_packs': 1,
        'capacite_utile_kwh': capacite,
        'capacite_utile_source': 'fiche',
        'puissance_charge_kw': puissance,
        'puissance_decharge_kw': puissance,
        'borne_onduleur': {'charge_kw': None, 'decharge_kw': None},
        'avertissements': [],
    }


def contexte_de_test(*, heures=8760, jours=None, actif=True):
    """Un contexte minimal : consommation importée + pack de fiche."""
    hors = {'actif': actif}
    if jours is not None:
        hors['jours_autonomie'] = jours
    return {
        'consommation': {
            'import_intervalle': {'valeurs': [CONSO_KWH] * heures,
                                  'origine': 'Relevé SYNTHÉTIQUE de test'},
        },
        bloc_bat.CLE_CONTEXTE: {
            'groupes': [{'groupe': 'BAT-TEST-1', 'specs': specs_de_test()}],
        },
        bloc.CLE_CONTEXTE: hors,
    }


class MonotonieTest(SimpleTestCase):
    """À banque croissante, le défaut décroît — et finit par disparaître."""

    def test_le_taux_de_defaillance_decroit_avec_l_autonomie(self):
        serie = serie_de_test(heures=720)
        taux = []
        for jours in (0.05, 0.1, 0.25, 0.5, 1.0, 2.0):
            _suite, resultat = bloc.bloc_hors_reseau(
                serie, contexte_de_test(heures=720, jours=jours))
            self.assertEqual(resultat['motif_absence'], '')
            taux.append(resultat['taux_defaillance'])

        for avant, apres in zip(taux, taux[1:]):
            self.assertLessEqual(apres, avant + 1e-9)
        self.assertGreater(taux[0], 0.0)

    def test_une_banque_surdimensionnee_ne_defaille_jamais(self):
        serie = serie_de_test(heures=720)
        _suite, resultat = bloc.bloc_hors_reseau(
            serie, contexte_de_test(heures=720, jours=30.0))

        self.assertEqual(resultat['taux_defaillance'], 0.0)
        self.assertEqual(resultat['heures_defaillantes'], 0)


class AucunQuantileTest(SimpleTestCase):
    """Hors réseau : aucun P50/P90, et pas d'autoconsommation réseau."""

    def test_le_bloc_ne_publie_aucun_quantile(self):
        serie = serie_de_test(heures=720)
        _suite, resultat = bloc.bloc_hors_reseau(
            serie, contexte_de_test(heures=720, jours=1.0))

        self.assertFalse(resultat['quantiles_publiables'])
        self.assertTrue(resultat['motif_quantiles'])
        for cle in resultat:
            self.assertNotIn('p50', cle)
            self.assertNotIn('p90', cle)

    def test_l_autoconsommation_reseau_s_omet_dans_ce_mode(self):
        serie = serie_de_test(heures=720)
        contexte = contexte_de_test(heures=720, jours=1.0)
        _suite, resultat = bloc_conso.bloc_autoconsommation(serie, contexte)

        self.assertIsNone(resultat['energie'])
        self.assertEqual(resultat['motif_absence'],
                         bloc_conso.MOTIF_HORS_RESEAU)


class ContenuPublieTest(SimpleTestCase):
    """Le mois le plus défavorable, le SOC minimal et la banque dimensionnée."""

    def test_le_mois_le_plus_defavorable_est_un_numero(self):
        serie = serie_de_test()
        _suite, resultat = bloc.bloc_hors_reseau(
            serie, contexte_de_test(jours=0.1))

        self.assertIn(resultat['mois_le_plus_defavorable'], range(1, 13))
        self.assertTrue(resultat['par_mois'])

    def test_le_soc_minimal_est_publie_et_borne(self):
        serie = serie_de_test(heures=720)
        suite, resultat = bloc.bloc_hors_reseau(
            serie, contexte_de_test(heures=720, jours=1.0))

        socs = [point['batterie_soc_pct'] for point in suite['points']]
        self.assertEqual(resultat['soc_minimal_pct'], min(socs))
        self.assertGreaterEqual(min(socs), 0.0)
        self.assertLessEqual(max(socs), 100.0)

    def test_la_banque_vient_des_jours_saisis_et_de_la_fiche(self):
        serie = serie_de_test(heures=720)
        _suite, resultat = bloc.bloc_hors_reseau(
            serie, contexte_de_test(heures=720, jours=2.0))

        banque = resultat['banque']
        self.assertEqual(banque['jours_autonomie'], 2.0)
        self.assertEqual(banque['dod_pct'], 90.0)
        self.assertEqual(banque['source_dod'], 'fiche')
        # 24 kWh/jour × 2 jours, majorés du rendement aller-retour publié.
        self.assertAlmostEqual(banque['capacite_utile_kwh'],
                               24.0 * 2.0 / 0.9, delta=0.1)

    def test_aucune_colonne_reseau_n_est_ecrite(self):
        serie = serie_de_test(heures=72)
        suite, _resultat = bloc.bloc_hors_reseau(
            serie, contexte_de_test(heures=72, jours=1.0))

        for point in suite['points']:
            self.assertNotIn('reseau_import_kwh', point)
            self.assertNotIn('reseau_export_kwh', point)
            self.assertIn('batterie_soc_pct', point)


class OmissionsTest(SimpleTestCase):
    """Chaque absence OMET le bloc en nommant le champ, série inchangée."""

    def test_autonomie_non_saisie_omet_en_nommant_le_champ(self):
        serie = serie_de_test(heures=72)
        suite, resultat = bloc.bloc_hors_reseau(
            serie, contexte_de_test(heures=72))

        self.assertIsNone(resultat['taux_defaillance'])
        self.assertIn('jours_autonomie', resultat['motif_absence'])
        self.assertIs(suite, serie)

    def test_un_calepinage_raccorde_n_a_pas_de_bloc(self):
        serie = serie_de_test(heures=72)
        suite, resultat = bloc.bloc_hors_reseau(
            serie, contexte_de_test(heures=72, jours=1.0, actif=False))

        self.assertIsNone(resultat['taux_defaillance'])
        self.assertIn('actif', resultat['motif_absence'])
        self.assertIs(suite, serie)

    def test_sans_dod_de_fiche_le_bloc_est_omis_en_nommant_le_champ(self):
        serie = serie_de_test(heures=72)
        contexte = contexte_de_test(heures=72, jours=1.0)
        contexte[bloc_bat.CLE_CONTEXTE]['groupes'] = []
        _suite, resultat = bloc.bloc_hors_reseau(serie, contexte)

        self.assertIsNone(resultat['taux_defaillance'])
        self.assertIn('dod_pct', resultat['motif_absence'])

    def test_sans_courbe_de_charge_le_bloc_est_omis(self):
        serie = serie_de_test(heures=72)
        contexte = contexte_de_test(heures=72, jours=1.0)
        contexte['consommation'] = {}
        suite, resultat = bloc.bloc_hors_reseau(serie, contexte)

        self.assertIsNone(resultat['taux_defaillance'])
        self.assertEqual(resultat['motif_absence'], bloc.MOTIF_SANS_COURBE)
        self.assertIs(suite, serie)

    def test_sans_fuseau_le_bloc_est_omis_avec_le_motif_de_calx59(self):
        serie = serie_de_test(heures=72)
        contexte = contexte_de_test(heures=72, jours=1.0)
        contexte[chaine_pertes.CLE_CROISEMENT_HORAIRE] = {
            'possible': False,
            'motif': chaine_pertes.MOTIF_FUSEAU_ABSENT,
            'champ': 'site.fuseau',
            'blocs_omis': list(chaine_pertes.BLOCS_HORAIRES_OMIS),
        }
        _suite, resultat = bloc.bloc_hors_reseau(serie, contexte)

        self.assertEqual(resultat['motif_absence'],
                         chaine_pertes.MOTIF_FUSEAU_ABSENT)

    def test_sans_colonne_d_energie_le_bloc_est_omis(self):
        muette = {'points': [{'annee': 2021, 'mois': 1, 'jour': 1,
                              'heure': rang % 24} for rang in range(72)],
                  'pas_minutes': 60}
        _suite, resultat = bloc.bloc_hors_reseau(
            muette, contexte_de_test(heures=72, jours=1.0))

        self.assertIsNone(resultat['taux_defaillance'])
        self.assertTrue(resultat['motif_absence'])
