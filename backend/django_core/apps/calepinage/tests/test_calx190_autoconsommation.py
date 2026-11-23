"""CALX190 — l'autoconsommation et le plafond d'injection sur la vraie série.

Ce qui est tenu ici :

* les DEUX taux ne sont jamais confondus — un cas où ils diffèrent de plus de
  20 points est vérifié (règle fondateur COUV-AUTO) ;
* un plafond d'injection SAISI SANS justification OMET le bloc en NOMMANT le
  champ (on ne bride pas la production d'un client sur un chiffre que
  personne ne peut défendre) ;
* propriété : ``autoconsommé ≤ min(Σ production, Σ consommation)``, sur
  l'année ET à chaque heure ;
* le plafond appliqué publie une étape DÉCLARÉE (six clés, ``gain: False``,
  source = la justification saisie) et aucun export ne dépasse le plafond ;
* hors réseau, ou sans courbe de charge, ou sans fuseau : bloc OMIS, chacun
  avec SON motif, série INCHANGÉE.

Série de test : une année 2021 SYNTHÉTIQUE, fabriquée pour le test et ne
décrivant AUCUNE installation réelle. Test PUR : aucune base, aucun réseau.
"""
from __future__ import annotations

import datetime

from django.test import SimpleTestCase

from apps.calepinage.services import chaine_pertes, etapes
from apps.calepinage.services.etapes import autoconsommation as bloc
from apps.calepinage.services.etapes import batterie as bloc_bat

HEURES_DE_PRODUCTION = range(8, 18)

#: Une puissance alternative de test, choisie pour que les deux taux
#: divergent franchement (placeholder assumé, aucune installation réelle).
P_AC_KW = 6.0

CONSO_KWH = 1.0

JUSTIFICATION = ('Contrat de raccordement ONEE n° SYNTHÉTIQUE-TEST, '
                 'puissance injectable.')


def serie_de_test(*, annee=2021, heures=8760, p_ac=P_AC_KW):
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
            'p_ac_kw': p_ac if moment.hour in HEURES_DE_PRODUCTION else 0.0,
        })
    return {'points': points, 'pas_minutes': 60,
            'colonne_energie': 'p_ac_kw'}


def contexte_de_test(*, heures=8760, plafond=None, justification=None):
    """Un contexte minimal : une consommation importée, un raccordement."""
    raccordement = {}
    if plafond is not None:
        raccordement[bloc.CHAMP_PLAFOND] = plafond
    if justification is not None:
        raccordement[bloc.CHAMP_JUSTIFICATION] = justification
    return {
        'consommation': {
            'import_intervalle': {'valeurs': [CONSO_KWH] * heures,
                                  'origine': 'Relevé SYNTHÉTIQUE de test'},
        },
        bloc.CLE_RACCORDEMENT: raccordement,
    }


class DeuxTauxDistinctsTest(SimpleTestCase):
    """COUV-AUTO : la couverture n'est JAMAIS le taux d'autoconsommation."""

    def test_les_deux_taux_different_de_plus_de_vingt_points(self):
        serie = serie_de_test()
        _suite, resultat = bloc.bloc_autoconsommation(serie,
                                                      contexte_de_test())

        self.assertEqual(resultat['motif_absence'], '')
        ecart = abs(resultat['taux_couverture']
                    - resultat['taux_autoconsommation'])
        self.assertGreater(ecart, 0.20)

    def test_la_definition_publiee_dit_la_regle(self):
        serie = serie_de_test(heures=48)
        _suite, resultat = bloc.bloc_autoconsommation(
            serie, contexte_de_test(heures=48))

        self.assertIn('COUV-AUTO', resultat['definition'])


class ProprieteAutoconsommeTest(SimpleTestCase):
    """``autoconsommé ≤ min(production, consommation)``, partout."""

    def test_sur_l_annee(self):
        serie = serie_de_test()
        _suite, resultat = bloc.bloc_autoconsommation(serie,
                                                      contexte_de_test())

        energie = resultat['energie']
        self.assertLessEqual(energie['autoconsomme_kwh'],
                             min(energie['production_kwh'],
                                 energie['consommation_kwh']) + 1e-6)

    def test_a_chaque_heure(self):
        serie = serie_de_test(heures=72)
        suite, resultat = bloc.bloc_autoconsommation(
            serie, contexte_de_test(heures=72))

        self.assertEqual(resultat['motif_absence'], '')
        for point in suite['points']:
            autoconsomme = point['charge_kwh'] - point['reseau_import_kwh']
            production = (point['p_ac_kw']
                          - point['reseau_export_kwh'] + 1e-9)
            self.assertLessEqual(autoconsomme, point['charge_kwh'] + 1e-9)
            self.assertLessEqual(autoconsomme, production + 1e-6)


class PlafondInjectionTest(SimpleTestCase):
    """Le plafond vient du REGISTRE, et il porte sa justification."""

    def test_sans_justification_le_bloc_est_omis_en_nommant_le_champ(self):
        serie = serie_de_test(heures=72)
        contexte = contexte_de_test(heures=72, plafond=3.0)
        suite, resultat = bloc.bloc_autoconsommation(serie, contexte)

        self.assertIsNone(resultat['energie'])
        self.assertIn('plafond_injection_justification',
                      resultat['motif_absence'])
        self.assertIs(suite, serie)

    def test_le_plafond_applique_publie_une_etape_declaree(self):
        serie = serie_de_test(heures=72)
        contexte = contexte_de_test(heures=72, plafond=3.0,
                                    justification=JUSTIFICATION)
        _suite, resultat = bloc.bloc_autoconsommation(serie, contexte)

        etape = resultat['etape_plafond']
        self.assertEqual(sorted(etape), sorted(etapes.CLES_ETAPE))
        self.assertFalse(etape['gain'])
        self.assertEqual(etape['source'], JUSTIFICATION)
        self.assertEqual(etape['motif_omission'], '')
        self.assertGreater(resultat['plafond']['energie_ecretee_kwh'], 0.0)
        self.assertEqual(resultat['plafond']['plafond_kw'], 3.0)

    def test_aucun_export_ne_depasse_le_plafond(self):
        serie = serie_de_test(heures=72)
        contexte = contexte_de_test(heures=72, plafond=3.0,
                                    justification=JUSTIFICATION)
        suite, _resultat = bloc.bloc_autoconsommation(serie, contexte)

        exports = [point['reseau_export_kwh'] for point in suite['points']]
        self.assertLessEqual(max(exports), 3.0 + 1e-6)

    def test_aucun_plafond_regle_n_ecrete_rien(self):
        serie = serie_de_test(heures=72)
        _suite, resultat = bloc.bloc_autoconsommation(
            serie, contexte_de_test(heures=72))

        self.assertIsNone(resultat['plafond'])
        self.assertIsNone(resultat['etape_plafond'])


class PlafondSoutirageTest(SimpleTestCase):
    """ACAL829 — l'import réseau face à un plafond de soutirage SAISI.

    Charge 9 kWh/h sans aucune production sur 24 h : import 9 kW à chaque pas.
    """

    @staticmethod
    def _contexte(plafond=None, justification=JUSTIFICATION):
        contexte = contexte_de_test(heures=24)
        contexte['consommation']['import_intervalle']['valeurs'] = [9.0] * 24
        if plafond is not None:
            raccordement = contexte[bloc.CLE_RACCORDEMENT]
            raccordement['plafond_soutirage_kw'] = plafond
            if justification is not None:
                raccordement['plafond_soutirage_justification'] = justification
        return contexte

    def _soutirage(self, plafond, **options):
        _suite, resultat = bloc.bloc_autoconsommation(
            serie_de_test(heures=24, p_ac=0.0),
            self._contexte(plafond, **options))
        return resultat

    def test_9_kw_face_a_6_kw_pointe_9_et_24_heures_au_dessus(self):
        # 24 pas × (9 − 6) kWh = 72 kWh au-dessus du plafond.
        soutirage = self._soutirage(6.0)['soutirage']
        self.assertEqual(soutirage, {
            'plafond_kw': 6.0, 'justification': JUSTIFICATION,
            'pointe_kw': 9.0, 'heures_au_dessus': 24,
            'energie_au_dessus_kwh': 72.0})

    def test_plafond_egal_a_la_pointe_zero_heure(self):
        # strictement au-dessus : 9 > 9 est faux (mutant « ≥ » ⇒ 24 h).
        soutirage = self._soutirage(9.0)['soutirage']
        self.assertEqual((soutirage['heures_au_dessus'],
                          soutirage['energie_au_dessus_kwh']), (0, 0.0))
        self.assertEqual(soutirage['pointe_kw'], 9.0)

    def test_non_saisi_soutirage_null_jamais_zero_heure(self):
        resultat = self._soutirage(None)
        self.assertIn('soutirage', resultat)
        self.assertIsNone(resultat['soutirage'])

    def test_sans_justification_le_bloc_est_omis_en_nommant_le_champ(self):
        resultat = self._soutirage(6.0, justification=None)
        self.assertIsNone(resultat['energie'])
        self.assertIsNone(resultat['soutirage'])
        self.assertIn('plafond_soutirage_justification',
                      resultat['motif_absence'])

    def test_saisie_refus_nommes(self):
        from apps.calepinage.services.raccordement import (
            RaccordementInvalide, _saisie_publiee,
        )

        for corps, champ, etat in (
                ({'plafond_soutirage_kw': -1,
                  'plafond_soutirage_justification': 'x'},
                 'raccordement.plafond_soutirage_kw', False),
                ({'plafond_soutirage_kw': 'abc',
                  'plafond_soutirage_justification': 'x'},
                 'raccordement.plafond_soutirage_kw', False),
                ({'plafond_soutirage_kw': 6},
                 'raccordement.plafond_soutirage_justification', True)):
            with self.subTest(corps=corps):
                with self.assertRaises(RaccordementInvalide) as refus:
                    _saisie_publiee(corps)
                self.assertEqual(refus.exception.champ, champ)
                self.assertEqual(refus.exception.etat, etat)
        retenue = _saisie_publiee({'plafond_soutirage_kw': 0,
                                   'plafond_soutirage_justification': 'x'})
        self.assertEqual(retenue['plafond_soutirage_kw'], 0.0)


class PlagesPlafondInjectionTest(SimpleTestCase):
    """ACAL828 — une plage horaire REMPLACE le plafond de base sur ses heures.

    Série de 24 h : 6 kW de production de 8 h à 18 h INCLUS (heure 18 comprise,
    pour qu'un ``≤ fin_h`` soit visible), charge 1 kWh : surplus 5 kWh/h.
    """

    @staticmethod
    def _serie():
        serie = serie_de_test(heures=24)
        for point in serie['points']:
            if point['heure'] == 18:
                point['p_ac_kw'] = P_AC_KW
        return serie

    @staticmethod
    def _contexte(plages, plafond=None):
        contexte = contexte_de_test(heures=24, plafond=plafond,
                                    justification=JUSTIFICATION)
        contexte[bloc.CLE_RACCORDEMENT]['plages_plafond_injection'] = plages
        return contexte

    def test_plage_16_18_a_2_kw_n_ecrete_que_les_heures_16_et_17(self):
        plage = {'debut_h': 16, 'fin_h': 18, 'plafond_kw': 2.0}
        suite, resultat = bloc.bloc_autoconsommation(
            self._serie(), self._contexte([plage]))
        exports = {point['heure']: point['reseau_export_kwh']
                   for point in suite['points']}
        self.assertEqual((exports[16], exports[17]), (2.0, 2.0))
        # 15 h et 18 h (borne exclue) ne sont pas touchées : surplus 5 kWh.
        self.assertEqual((exports[15], exports[18]), (5.0, 5.0))
        publie = resultat['plafond']
        self.assertIsNone(publie['plafond_kw'])
        self.assertEqual(publie['heures_ecretees'], 2)
        self.assertEqual(publie['plages'], [dict(
            plage, heures_ecretees=2, energie_ecretee_kwh=6.0)])

    def test_la_plage_remplace_le_plafond_de_base_sur_ses_heures(self):
        # base 4 kW : surplus 5 écrêté de 1 kWh de 8 h à 15 h (8 h) puis 18 h ;
        # plage 16-18 à 2 kW : 3 kWh écrêtés par heure sur 16 h et 17 h.
        plage = {'debut_h': 16, 'fin_h': 18, 'plafond_kw': 2.0}
        suite, resultat = bloc.bloc_autoconsommation(
            self._serie(), self._contexte([plage], plafond=4.0))
        exports = {point['heure']: point['reseau_export_kwh']
                   for point in suite['points']}
        self.assertEqual((exports[15], exports[16], exports[17], exports[18]),
                         (4.0, 2.0, 2.0, 4.0))
        self.assertEqual(resultat['plafond']['plages'][0]['heures_ecretees'],
                         2)
        self.assertEqual(resultat['plafond']['heures_ecretees'], 11)

    def test_plage_sans_depassement_publie_zero_heure(self):
        plage = {'debut_h': 2, 'fin_h': 4, 'plafond_kw': 2.0}
        _suite, resultat = bloc.bloc_autoconsommation(
            self._serie(), self._contexte([plage]))
        self.assertEqual(resultat['plafond']['plages'][0]['heures_ecretees'],
                         0)

    def test_pas_non_horaire_omet_le_bloc_en_nommant_la_resolution(self):
        serie = self._serie()
        serie['pas_minutes'] = 30
        _suite, resultat = bloc.bloc_autoconsommation(
            serie, self._contexte([{'debut_h': 16, 'fin_h': 18,
                                    'plafond_kw': 2.0}]))
        self.assertIsNone(resultat['energie'])
        self.assertIn('simulation.resolution_minutes',
                      resultat['motif_absence'])

    def test_validation_des_plages(self):
        from apps.calepinage.services import limites_livraison as limites

        plage = {'debut_h': 8, 'fin_h': 10, 'plafond_kw': 1.0}
        self.assertIsNone(limites.plages_saisies(None))
        self.assertEqual(limites.plages_saisies([plage]), [plage])
        cas = {
            'plus de 3 plages': [plage] * 4,
            'debut >= fin': [{'debut_h': 10, 'fin_h': 10, 'plafond_kw': 1}],
            'hors 0-24': [{'debut_h': 20, 'fin_h': 25, 'plafond_kw': 1}],
            'chevauchement': [plage, {'debut_h': 9, 'fin_h': 12,
                                      'plafond_kw': 1}],
            'plafond négatif': [{'debut_h': 1, 'fin_h': 2, 'plafond_kw': -1}],
        }
        for nom, plages in cas.items():
            with self.subTest(nom):
                with self.assertRaises(limites.PlageInvalide) as refus:
                    limites.plages_saisies(plages)
                self.assertTrue(
                    refus.exception.champ.startswith(
                        'plages_plafond_injection'))
        # deux plages contiguës ne se chevauchent pas ; 24 est admis.
        self.assertEqual(len(limites.plages_saisies(
            [plage, {'debut_h': 10, 'fin_h': 24, 'plafond_kw': 0}])), 2)


class ApresBatterieTest(SimpleTestCase):
    """La production vue au compteur est celle que CALX188 a laissée."""

    def test_la_serie_enrichie_par_la_batterie_est_relue(self):
        serie = serie_de_test(heures=240)
        contexte = contexte_de_test(heures=240)
        contexte[bloc_bat.CLE_CONTEXTE] = {
            'strategie': 'autoconso',
            'groupes': [{'groupe': 'BAT-TEST-1', 'specs': _specs()}],
        }
        apres_batterie, bloc_bat_resultat = bloc_bat.bloc_batterie(serie,
                                                                   contexte)
        self.assertEqual(bloc_bat_resultat['motif_absence'], '')

        _suite, resultat = bloc.bloc_autoconsommation(apres_batterie,
                                                      contexte)

        self.assertTrue(resultat['energie']['apres_batterie'])
        self.assertLess(resultat['energie']['production_kwh'],
                        resultat['energie']['production_brute_kwh'])

    def test_sans_batterie_les_deux_productions_coincident(self):
        serie = serie_de_test(heures=72)
        _suite, resultat = bloc.bloc_autoconsommation(
            serie, contexte_de_test(heures=72))

        self.assertFalse(resultat['energie']['apres_batterie'])
        self.assertAlmostEqual(resultat['energie']['production_kwh'],
                               resultat['energie']['production_brute_kwh'],
                               delta=0.01)


def _specs(*, capacite=10.0, puissance=5.0, rendement=90.0, dod=90.0):
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


class OmissionsTest(SimpleTestCase):
    """Chaque absence OMET le bloc avec SON motif, série inchangée."""

    def test_sans_courbe_de_charge_le_bloc_est_omis(self):
        serie = serie_de_test(heures=72)
        contexte = contexte_de_test(heures=72)
        contexte['consommation'] = {}
        suite, resultat = bloc.bloc_autoconsommation(serie, contexte)

        self.assertIsNone(resultat['energie'])
        self.assertTrue(resultat['motif_absence'])
        self.assertIs(suite, serie)

    def test_hors_reseau_le_bloc_est_omis(self):
        serie = serie_de_test(heures=72)
        contexte = contexte_de_test(heures=72)
        contexte[bloc.CLE_HORS_RESEAU] = {'actif': True}
        _suite, resultat = bloc.bloc_autoconsommation(serie, contexte)

        self.assertIsNone(resultat['energie'])
        self.assertEqual(resultat['motif_absence'], bloc.MOTIF_HORS_RESEAU)

    def test_sans_fuseau_le_bloc_est_omis_avec_le_motif_de_calx59(self):
        serie = serie_de_test(heures=72)
        contexte = contexte_de_test(heures=72)
        contexte[chaine_pertes.CLE_CROISEMENT_HORAIRE] = {
            'possible': False,
            'motif': chaine_pertes.MOTIF_FUSEAU_ABSENT,
            'champ': 'site.fuseau',
            'blocs_omis': list(chaine_pertes.BLOCS_HORAIRES_OMIS),
        }
        _suite, resultat = bloc.bloc_autoconsommation(serie, contexte)

        self.assertEqual(resultat['motif_absence'],
                         chaine_pertes.MOTIF_FUSEAU_ABSENT)

    def test_sans_colonne_d_energie_le_bloc_est_omis(self):
        muette = {'points': [{'annee': 2021, 'mois': 1, 'jour': 1,
                              'heure': rang % 24} for rang in range(72)],
                  'pas_minutes': 60}
        _suite, resultat = bloc.bloc_autoconsommation(
            muette, contexte_de_test(heures=72))

        self.assertIsNone(resultat['energie'])
        self.assertTrue(resultat['motif_absence'])


class ParMoisTest(SimpleTestCase):
    """ACAL445 — le découpage mensuel de l'autoconsommation est servi."""

    COLONNES = ('mois', 'consommation_kwh', 'production_kwh',
                'autoconsomme_kwh', 'import_reseau_kwh', 'export_reseau_kwh')

    def test_la_somme_des_mois_egale_l_annuel(self):
        _suite, resultat = bloc.bloc_autoconsommation(serie_de_test(),
                                                      contexte_de_test())
        par_mois = resultat['par_mois']
        energie = resultat['energie']

        self.assertEqual([ligne['mois'] for ligne in par_mois],
                         list(range(1, 13)))
        for ligne in par_mois:
            self.assertEqual(sorted(ligne), sorted(self.COLONNES))
        for colonne in ('consommation_kwh', 'production_kwh',
                        'autoconsomme_kwh', 'import_reseau_kwh',
                        'export_reseau_kwh'):
            self.assertAlmostEqual(
                sum(ligne[colonne] for ligne in par_mois),
                energie[colonne], delta=0.02)
        # Janvier = 31 jours x 24 h x 1 kWh (la consommation est plate).
        self.assertAlmostEqual(par_mois[0]['consommation_kwh'], 744.0,
                               delta=0.01)
        self.assertAlmostEqual(par_mois[1]['consommation_kwh'], 672.0,
                               delta=0.01)

    def test_un_mois_sans_point_vaut_null_jamais_zero(self):
        _suite, resultat = bloc.bloc_autoconsommation(
            serie_de_test(heures=48), contexte_de_test(heures=48))
        par_mois = resultat['par_mois']

        self.assertEqual(len(par_mois), 12)
        self.assertIsNotNone(par_mois[0]['consommation_kwh'])
        for ligne in par_mois[1:]:
            for colonne in self.COLONNES[1:]:
                self.assertIsNone(ligne[colonne])

    def test_bloc_omis_la_cle_est_presente_et_nulle(self):
        contexte = contexte_de_test(heures=72)
        contexte[bloc.CLE_HORS_RESEAU] = {'actif': True}
        _suite, resultat = bloc.bloc_autoconsommation(
            serie_de_test(heures=72), contexte)

        self.assertIn('par_mois', resultat)
        self.assertIsNone(resultat['par_mois'])


class AnneeMoyenneHeuresTest(SimpleTestCase):
    """ACAL1604 — en météo pluriannuelle, les comptes d'heures publiés sont
    ceux d'une année MOYENNE (≤ 8 760 h), comme les énergies.

    Cas chiffré à la main (série de test) : 6 kW de 8 h à 18 h, 1 kWh/h de
    charge ⇒ 10 heures par jour sans import, soit 3 650 h sur 2021 ; plafond
    3 kW ⇒ ces 10 heures sont écrêtées (surplus 5 kWh) : 3 650 h/an.
    """

    @staticmethod
    def _deux_ans():
        return {'points': serie_de_test(annee=2021)['points']
                + serie_de_test(annee=2022)['points'],
                'pas_minutes': 60, 'colonne_energie': 'p_ac_kw'}

    def test_deux_annees_identiques_heures_sans_import_d_une_annee(self):
        contexte = contexte_de_test(heures=17520, plafond=3.0,
                                    justification=JUSTIFICATION)
        contexte[chaine_pertes.CLE_ANNEES_FENETRE] = 2
        _suite, resultat = bloc.bloc_autoconsommation(self._deux_ans(),
                                                      contexte)

        self.assertEqual(resultat['heures_sans_import'], 3650)
        self.assertEqual(resultat['plafond']['heures_ecretees'], 3650)

    def test_plages_de_plafond_heures_annuelles(self):
        contexte = contexte_de_test(heures=17520, justification=JUSTIFICATION)
        contexte[bloc.CLE_RACCORDEMENT]['plages_plafond_injection'] = [
            {'debut_h': 16, 'fin_h': 18, 'plafond_kw': 2.0}]
        contexte[chaine_pertes.CLE_ANNEES_FENETRE] = 2
        _suite, resultat = bloc.bloc_autoconsommation(self._deux_ans(),
                                                      contexte)
        # 2 heures (16 h, 17 h) × 365 jours = 730 h/an.
        self.assertEqual(resultat['plafond']['plages'][0]['heures_ecretees'],
                         730)
        self.assertEqual(resultat['plafond']['heures_ecretees'], 730)

    def test_en_annee_type_le_compte_reste_entier(self):
        _suite, resultat = bloc.bloc_autoconsommation(serie_de_test(),
                                                      contexte_de_test())
        self.assertEqual(resultat['heures_sans_import'], 3650)
        self.assertIsInstance(resultat['heures_sans_import'], int)

    def test_autonomie_de_la_batterie_ramene_les_heures(self):
        imports, charge = [0.0, 1.0, 0.0, 1.0], [1.0] * 4
        self.assertEqual(bloc_bat.autonomie(imports, charge)
                         ['heures_sans_import'], 2)
        self.assertEqual(bloc_bat.autonomie(imports, charge, annees=2)
                         ['heures_sans_import'], 1)

    def test_hors_reseau_heures_defaillantes_annuelles(self):
        from apps.calepinage.services.etapes import hors_reseau as bloc_hr
        from apps.calepinage.tests import test_calx191_hors_reseau as hr

        deux_ans = {'points': hr.serie_de_test(heures=720)['points']
                    + hr.serie_de_test(annee=2022, heures=720)['points'],
                    'pas_minutes': 60, 'colonne_energie': 'p_ac_kw'}
        somme = bloc_hr.bloc_hors_reseau(
            deux_ans, hr.contexte_de_test(heures=1440, jours=0.25))[1]
        contexte = hr.contexte_de_test(heures=1440, jours=0.25)
        contexte[chaine_pertes.CLE_ANNEES_FENETRE] = 2
        deux = bloc_hr.bloc_hors_reseau(deux_ans, contexte)[1]

        # Même simulation, publiée à l'année moyenne : la moitié exacte.
        self.assertGreater(somme['heures_defaillantes'], 200)
        self.assertEqual(deux['heures_defaillantes'],
                         round(somme['heures_defaillantes'] / 2, 3))
        for mois_s, mois_2 in zip(somme['par_mois'], deux['par_mois']):
            self.assertEqual(mois_2['heures_defaillantes'],
                             round(mois_s['heures_defaillantes'] / 2, 3))
