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
