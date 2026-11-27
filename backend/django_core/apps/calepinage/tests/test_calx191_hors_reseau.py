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

    def test_acal1960_les_heures_sont_comptees_par_an(self):
        # Deux ans de fenêtre : ``heures`` dit l'année moyenne (720 h), pas la
        # longueur de la série (1 440 h) ; un an : inchangé. Mutant : ne pas
        # diviser ⇒ 1 440.
        serie = serie_de_test(heures=1440)
        contexte = contexte_de_test(heures=1440, jours=1.0)
        self.assertEqual(bloc.bloc_hors_reseau(serie, contexte)[1]['heures'], 1440)
        contexte[chaine_pertes.CLE_ANNEES_FENETRE] = 2
        rendu = bloc.bloc_hors_reseau(serie, contexte)[1]
        self.assertEqual(rendu['heures'], 720)
        # Revue lot 6 — la portée est DITE ; un bloc omis la laisse nulle.
        self.assertEqual(rendu['portee_heures'], 'annee_moyenne')
        omis = bloc.bloc_hors_reseau(serie, contexte_de_test(heures=1440))[1]
        self.assertIsNone(omis['portee_heures'])

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

    def _bloc_saisonnier(self, serie=None):
        # Décembre (744 h) à 2 kWh/h, le reste de 2021 à 1 kWh/h.
        serie = serie or serie_de_test()
        contexte = contexte_de_test(jours=2.0)
        contexte['consommation']['import_intervalle']['valeurs'] = [
            2.0 if point['mois'] == 12 else CONSO_KWH
            for point in serie['points']]
        return bloc.bloc_hors_reseau(serie, contexte)[1]

    def test_acal802_la_banque_du_mois_charge_est_au_moins_la_moyenne(self):
        resultat = self._bloc_saisonnier()
        moyenne = resultat['banque']
        charge = resultat['banque_mois_charge']
        self.assertEqual(resultat['motif_banque_mois_charge'], '')
        # Décembre : 31 jours × 48 kWh = 1 488 kWh ; 744 h ÷ 24 = 31 jours.
        self.assertEqual(charge['mois'], 12)
        self.assertEqual(charge['consommation_journaliere_kwh'], 48.0)
        # Même règle que la banque moyenne : conso × jours ÷ rendement 0,9.
        self.assertAlmostEqual(charge['capacite_utile_kwh'],
                               48.0 * 2.0 / 0.9, delta=0.1)
        self.assertGreater(charge['capacite_utile_kwh'],
                           moyenne['capacite_utile_kwh'])
        self.assertEqual(charge['jours_autonomie'], moyenne['jours_autonomie'])
        self.assertGreaterEqual(charge['capacite_nominale_kwh'],
                                charge['capacite_utile_kwh'])
        self.assertIsNotNone(charge['defaillance_kwh'])
        self.assertIsNotNone(charge['taux_defaillance'])
        # La banque moyenne reste publiée telle quelle : conso moyenne
        # (8 760 + 744) ÷ 365 jours = 26,04 kWh/jour.
        self.assertAlmostEqual(moyenne['capacite_utile_kwh'],
                               (9504.0 / 365.0) * 2.0 / 0.9, delta=0.1)

    def test_acal802_sans_mois_le_motif_est_nomme(self):
        serie = serie_de_test(heures=72)
        for point in serie['points']:
            del point['mois']
        _suite, resultat = bloc.bloc_hors_reseau(
            serie, contexte_de_test(heures=72, jours=1.0))
        self.assertEqual(resultat['motif_absence'], '')
        self.assertIsNone(resultat['banque_mois_charge'])
        self.assertIn('Aucun mois', resultat['motif_banque_mois_charge'])

    def test_aucune_colonne_reseau_n_est_ecrite(self):
        serie = serie_de_test(heures=72)
        suite, _resultat = bloc.bloc_hors_reseau(
            serie, contexte_de_test(heures=72, jours=1.0))

        for point in suite['points']:
            self.assertNotIn('reseau_import_kwh', point)
            self.assertNotIn('reseau_export_kwh', point)
            self.assertIn('batterie_soc_pct', point)


GROUPE = {'actif': True, 'puissance_kw': 5.0, 'soc_demarrage_pct': 20,
          'soc_arret_pct': 80, 'heures_max_par_jour': 6}
SEUILS = {'veille_pct': 30, 'entretien_pct': 20, 'arret_pct': 10}


class GroupeDAppointTest(SimpleTestCase):
    """ACAL801 — le groupe d'appoint : marche, énergie, défaillance."""

    def _bloc(self, groupe=None, seuils=None, heures=720, jours=0.1):
        contexte = contexte_de_test(heures=heures, jours=jours)
        if groupe is not None:
            contexte[bloc.CLE_CONTEXTE]['groupe'] = groupe
        if seuils is not None:
            contexte[bloc.CLE_CONTEXTE]['seuils'] = seuils
        return bloc.bloc_hors_reseau(serie_de_test(heures=heures),
                                     contexte)[1]

    def test_un_groupe_de_5_kw_reduit_la_defaillance_et_publie_ses_heures(self):
        sans = self._bloc()
        avec = self._bloc(GROUPE)
        self.assertLessEqual(avec['defaillance_kwh'], sans['defaillance_kwh'])
        self.assertLess(avec['defaillance_kwh'], sans['defaillance_kwh'])
        groupe = avec['groupe']
        self.assertGreater(groupe['heures_de_marche'], 0)
        self.assertGreater(groupe['energie_fournie_kwh'], 0)
        # Budget : au plus 6 h par jour sur 30 jours.
        self.assertLessEqual(groupe['heures_de_marche'], 6 * 30)
        self.assertEqual([ligne['mois'] for ligne in groupe['par_mois']], [1])
        self.assertAlmostEqual(
            sum(ligne['heures_de_marche'] for ligne in groupe['par_mois']),
            groupe['heures_de_marche'], places=2)
        self.assertIn('courant de démarrage', groupe['mention'])
        # Le bilan ferme : servi + défaillance = consommation.
        self.assertAlmostEqual(avec['servi_kwh'] + avec['defaillance_kwh'],
                               avec['consommation_kwh'], places=2)
        for cle in ('puissance_kw', 'soc_demarrage_pct', 'soc_arret_pct',
                    'heures_max_par_jour'):
            self.assertEqual(groupe[cle], GROUPE[cle])

    def test_acal1932_demarrage_sous_la_veille_dit_pourquoi_le_groupe_ne_tourne_pas(self):
        # Veille 30 % / démarrage 20 % : la banque ne descend jamais à 20 %.
        groupe = self._bloc(GROUPE, seuils=SEUILS)['groupe']
        self.assertEqual(groupe['heures_de_marche'], 0)
        self.assertIn('le groupe ne démarre jamais : seuil de démarrage '
                      'sous la veille', groupe['cause_inactif'])
        self.assertIn('20 %', groupe['cause_inactif'])
        self.assertIn('30 %', groupe['cause_inactif'])
        # Sans seuils saisis, ou groupe qui a tourné : aucune cause inventée.
        self.assertIsNone(self._bloc(GROUPE)['groupe']['cause_inactif'])
        self.assertIsNone(self._bloc(
            GROUPE, seuils=dict(SEUILS, veille_pct=20))['groupe']['cause_inactif'])

    def test_actif_faux_ou_sans_groupe_rend_le_resultat_d_aujourd_hui(self):
        sans = self._bloc()
        self.assertIsNone(sans['groupe'])
        self.assertEqual(self._bloc(dict(GROUPE, actif=False)), sans)

    def test_la_mention_d_entretien_sans_source_ac_disparait_avec_un_groupe(
            self):
        from apps.calepinage.services.hors_reseau import (
            MENTION_ENTRETIEN_SANS_SOURCE_AC,
        )

        self.assertIn(MENTION_ENTRETIEN_SANS_SOURCE_AC,
                      self._bloc(seuils=SEUILS)['mentions'])
        self.assertNotIn(MENTION_ENTRETIEN_SANS_SOURCE_AC,
                         self._bloc(GROUPE, seuils=SEUILS)['mentions'])

    def test_machine_d_etats_demarrage_arret_et_budget_du_jour(self):
        from apps.calepinage.services.groupe_appoint import Groupe

        # Capacité 10 kWh : démarre à 2 kWh, s'arrête à 8 kWh, 3 h par jour.
        groupe = Groupe(dict(GROUPE, heures_max_par_jour=3), 10.0, 1.0)
        etats = [1.0, 5.0, 9.0, 1.0, 1.0]
        # 0 : 1 ≤ 2 démarre ; 1 : en marche (5 < 8) ; 2 : 9 ≥ 8 ARRÊT ;
        # 3 : 1 ≤ 2 redémarre (3e heure du jour) ; 4 : budget épuisé.
        self.assertEqual([groupe.marcher(rang, etat)
                          for rang, etat in enumerate(etats)],
                         [5.0, 5.0, 0.0, 5.0, 0.0])
        self.assertEqual(groupe.heures_de_marche, 3.0)

    def test_le_budget_du_jour_se_renouvelle_toutes_les_24_heures(self):
        from apps.calepinage.services.groupe_appoint import Groupe

        groupe = Groupe(dict(GROUPE, heures_max_par_jour=1), 10.0, 1.0)
        energies = [groupe.marcher(rang, 1.0) for rang in (0, 1, 24, 25)]
        self.assertEqual(energies, [5.0, 0.0, 5.0, 0.0])


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
