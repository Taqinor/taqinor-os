"""CALX195 — le harnais qui confronte notre chaîne à PVGIS lui-même.

LES DEUX CÔTÉS, ET POURQUOI ILS SONT COMPARABLES
--------------------------------------------------
Les deux réponses PVGIS employées ici sont RÉELLES et ENREGISTRÉES, et elles
décrivent la MÊME installation :

* ``fixtures_pvgis/seriescalc_casablanca_sud.json`` — ``pvcalculation=1``,
  ``peakpower=1``, ``loss=7,25 %``, plan 15° plein sud, Casablanca
  (33,5 / −7,6), année 2020. C'est PVGIS qui calcule la production, avec son
  propre modèle PV (température de cellule comprise).
* ``fixtures_pvgis/seriescalc_casablanca_sud_irradiance.json`` —
  ``pvcalculation=0`` au MÊME point, sur le MÊME plan, la MÊME année. PVGIS
  n'y calcule aucune production : il ne rend que l'irradiance.

Le test vérifie lui-même que les deux réponses portent les mêmes 288
horodatages et le même ``G(i)`` heure par heure : sans cela, l'écart mesuré
parlerait de deux météos, pas de deux modèles.

L'ENTRÉE DE LA CHAÎNE LOCALE
------------------------------
``p_dc_w = kWc × G(i)`` — ce n'est pas un coefficient choisi, c'est la
DÉFINITION du kilowatt-crête (conditions STC : 1 000 W/m², 25 °C). Le
convertisseur d'irradiance en puissance appartiendra à
``services/simulation.py`` (CALX5), qui n'existe pas encore : le harnais le
pose donc ICI, dans le test, jamais dans le code produit.

L'écart mesuré est par conséquent exactement ce que le modèle PV de PVGIS
fait EN PLUS de cette définition linéaire — l'échauffement de cellule au
premier chef —, ce qui est précisément le nombre que la tâche demande de
publier : un ÉCART INFORMATIF, jamais une « validation ».

Aucune base, aucun réseau : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_calx195_validation
"""
from __future__ import annotations

import json
import pathlib
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services import chaine_pertes
from apps.calepinage.services import validation as v

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

#: L'instant figé de la mesure — une assertion qui dérive avec l'horloge
#: murale ne mesure plus rien.
FAITE_LE = '2026-09-21T10:15:00Z'

#: LE POSTE COMPARABLE, ET LUI SEUL. PVGIS n'accepte qu'un ``loss`` plat :
#: pour comparer À PERTE TOTALE ÉGALE, notre cascade ne doit porter QU'UN
#: poste global, de la valeur exacte que PVGIS dit avoir appliquée. Le poste
#: « ohmique_ac » est celui qui s'y prête : son étape n'est pas livrée, donc
#: c'est la saisie sourcée qui s'applique (arbitrage CALX149).
POSTE_COMPARABLE = 'ohmique_ac'

#: L'ÉCART ANNUEL MESURÉ, sur ces deux réponses et ce réglage, le 21/09/2026.
#: Il n'est pas une cible : c'est le relevé du jour. Qu'il bouge signifie que
#: notre modèle a bougé par rapport à celui de PVGIS — ce que ce harnais
#: existe pour rendre visible.
ECART_ANNUEL_MESURE_PCT = 16.97

#: Les deux mois extrêmes du relevé : mai le plus proche de PVGIS, juillet le
#: plus loin. L'écart d'été est le plus grand, ce qui est la signature de
#: l'échauffement de cellule que PVGIS modélise et que notre chaîne, sans
#: fiche module, OMET encore.
ECART_MAI_MESURE_PCT = 11.82
ECART_JUILLET_MESURE_PCT = 24.39

#: Tolérance d'assertion — de l'arithmétique d'arrondi, pas un seuil métier.
DELTA_PCT = 0.02


def _charge(nom):
    return json.loads((FIXTURES / nom).read_text(encoding='utf-8'))


REPONSE_PVGIS = _charge('seriescalc_casablanca_sud.json')
REPONSE_IRRADIANCE = _charge('seriescalc_casablanca_sud_irradiance.json')
LOSS_PCT = REPONSE_PVGIS['inputs']['pv_module']['system_loss']
KWC = REPONSE_PVGIS['inputs']['pv_module']['peak_power']


def serie_entree(kwc=KWC):
    """La série d'entrée de la chaîne, bâtie sur l'irradiance NUE réelle."""
    points = []
    for ligne in REPONSE_IRRADIANCE['outputs']['hourly']:
        moment = ligne['time']
        points.append({
            'annee': int(moment[0:4]), 'mois': int(moment[4:6]),
            'jour': int(moment[6:8]), 'heure': int(moment[9:11]),
            'gi_w_m2': ligne['G(i)'], 't2m_c': ligne['T2m'],
            'ws10m': ligne['WS10m'], 'h_sun_deg': ligne['H_sun'],
            'p_w': kwc * ligne['G(i)'],
        })
    return {'pas_minutes': 60, 'colonne_energie': 'p_w', 'points': points}


def contexte(*, tolerance=None, poste_comparable=True, kwc=KWC):
    """Le contexte de chaîne — minimal, et NOMMÉ poste par poste."""
    reglages = {
        'mode_meteo': {'valeur': 'pluriannuel', 'source': 'societe'},
        'fenetre_annees': {'valeur': '2020-2020', 'source': 'societe'},
    }
    if tolerance is not None:
        reglages[v.CLE_TOLERANCE] = {
            'valeur': tolerance, 'source': 'societe',
            'reference': 'Politique interne du bureau d\'études',
        }
    postes = []
    if poste_comparable:
        postes.append({
            'poste': POSTE_COMPARABLE, 'pct': LOSS_PCT,
            'source': 'pvgis:inputs.pv_module.system_loss',
            'libelle': 'Perte totale plate, alignée sur la requête PVGIS',
        })
    return {
        'site': {'lat': 33.5, 'lon': -7.6, 'fuseau': 'Africa/Casablanca'},
        'meteo': {'heure': {'base': 'utc'}},
        'plans': [{'cle': 'A', 'kwc': kwc, 'inclinaison_deg': 15.0,
                   'azimut_pvgis_deg': 0.0}],
        'reglages_simulation': reglages,
        'postes_saisis': postes,
    }


def cascade_isolee():
    """Isole la cascade sur le SEUL poste comparable, le temps du test.

    Les autres étapes de la chaîne atterrissent en parallèle sur le même
    arbre : mesurer un écart contre PVGIS sur la cascade ENTIÈRE ferait
    bouger le relevé à chaque étape livrée, et le harnais mesurerait le
    calendrier des lanes plutôt que le modèle. Les assertions CHIFFRÉES
    tournent donc sur cette cascade réduite ; les assertions de FORME, elles,
    tournent sur la chaîne entière (voir ``FormeDuBlocTest``).
    """
    return mock.patch.object(chaine_pertes, 'ORDRE_ETAPES',
                             (POSTE_COMPARABLE,))


def mesurer(**kwargs):
    resultat = kwargs.pop('resultat', None)
    with cascade_isolee():
        return v.ecart_vs_pvcalc(serie_entree(), contexte(**kwargs),
                                 REPONSE_PVGIS, resultat=resultat,
                                 maintenant=FAITE_LE)


class LesDeuxReponsesDecriventLeMemeSiteTest(SimpleTestCase):
    """Sans cela, l'écart parlerait de deux météos et non de deux modèles."""

    def test_les_memes_horodatages(self):
        gauche = [ligne['time']
                  for ligne in REPONSE_PVGIS['outputs']['hourly']]
        droite = [ligne['time']
                  for ligne in REPONSE_IRRADIANCE['outputs']['hourly']]
        self.assertEqual(gauche, droite)
        self.assertEqual(len(gauche), 288)

    def test_la_meme_irradiance_de_plan(self):
        ecart_max = max(
            abs(gauche['G(i)'] - droite['G(i)'])
            for gauche, droite in zip(REPONSE_PVGIS['outputs']['hourly'],
                                      REPONSE_IRRADIANCE['outputs']['hourly']))
        self.assertEqual(ecart_max, 0.0)

    def test_le_meme_plan_et_la_meme_fenetre(self):
        for charge in (REPONSE_PVGIS, REPONSE_IRRADIANCE):
            fixe = charge['inputs']['mounting_system']['fixed']
            self.assertEqual(fixe['slope']['value'], 15)
            self.assertEqual(fixe['azimuth']['value'], 0)
            meteo = charge['inputs']['meteo_data']
            self.assertEqual((meteo['year_min'], meteo['year_max']),
                             (2020, 2020))


class EcartPublieTest(SimpleTestCase):
    """L'écart entre les deux chemins est PUBLIÉ, annuel et mois par mois."""

    def setUp(self):
        self.bloc = mesurer()

    def test_les_deux_totaux_sont_publies(self):
        self.assertGreater(self.bloc['total_chaine_locale_kwh'], 0.0)
        self.assertGreater(self.bloc['total_pvcalc_kwh'], 0.0)

    def test_le_total_pvgis_est_celui_de_la_reponse_enregistree(self):
        attendu = sum(ligne['P']
                      for ligne in REPONSE_PVGIS['outputs']['hourly']) / 1000.0
        self.assertAlmostEqual(self.bloc['total_pvcalc_kwh'], attendu,
                               places=1)

    def test_l_ecart_annuel_est_celui_qui_a_ete_mesure(self):
        self.assertAlmostEqual(self.bloc['ecart_pct'],
                               ECART_ANNUEL_MESURE_PCT, delta=DELTA_PCT)

    def test_l_ecart_est_publie_mois_par_mois(self):
        self.assertEqual([ligne['mois'] for ligne in self.bloc['mensuel']],
                         list(range(1, 13)))
        for ligne in self.bloc['mensuel']:
            self.assertIsNotNone(ligne['chaine_locale_kwh'])
            self.assertIsNotNone(ligne['pvcalc_kwh'])
            self.assertIsNotNone(ligne['ecart_pct'])

    def test_l_ete_s_ecarte_plus_que_le_printemps(self):
        par_mois = {ligne['mois']: ligne['ecart_pct']
                    for ligne in self.bloc['mensuel']}
        self.assertAlmostEqual(par_mois[5], ECART_MAI_MESURE_PCT,
                               delta=DELTA_PCT)
        self.assertAlmostEqual(par_mois[7], ECART_JUILLET_MESURE_PCT,
                               delta=DELTA_PCT)
        self.assertGreater(par_mois[7], par_mois[5])

    def test_les_mois_somment_l_annee(self):
        for cle_mois, cle_total in (('chaine_locale_kwh',
                                     'total_chaine_locale_kwh'),
                                    ('pvcalc_kwh', 'total_pvcalc_kwh')):
            somme = sum(ligne[cle_mois] for ligne in self.bloc['mensuel'])
            self.assertAlmostEqual(somme, self.bloc[cle_total], delta=0.15)


class PerteTotaleEgaleTest(SimpleTestCase):
    """L'écart ne se lit comme un écart de MODÈLE qu'à perte totale égale."""

    def test_les_deux_pertes_totales_sont_publiees_et_egales(self):
        pertes = mesurer()['pertes_totales']
        self.assertEqual(pertes['pvgis_pct'], LOSS_PCT)
        self.assertAlmostEqual(pertes['chaine_pct'], LOSS_PCT,
                               delta=v.EPSILON_PERTE_PCT)
        self.assertTrue(pertes['egales'])

    def test_le_motif_previent_quand_elles_ne_le_sont_pas(self):
        bloc = mesurer(poste_comparable=False)
        self.assertFalse(bloc['pertes_totales']['egales'])
        self.assertIsNone(bloc['pertes_totales']['chaine_pct'])
        self.assertIn('ne sont PAS égales', bloc['motif'])

    def test_aucune_production_n_est_retouchee(self):
        """Le harnais MESURE : il ne ramène jamais le total sur PVGIS."""
        avec = mesurer(tolerance=1.0)['total_chaine_locale_kwh']
        sans = mesurer()['total_chaine_locale_kwh']
        self.assertEqual(avec, sans)


class ToleranceEtVerdictTest(SimpleTestCase):
    """Aucun verdict sans tolérance SAISIE — jamais un seuil codé."""

    def test_sans_tolerance_l_ecart_est_publie_sans_verdict(self):
        bloc = mesurer()
        self.assertIsNotNone(bloc['ecart_pct'])
        self.assertIsNone(bloc['verdict'])
        self.assertIsNone(bloc['tolerance_pct'])
        self.assertIsNone(bloc['tolerance_source'])
        self.assertIn(v.CHAMP_TOLERANCE, bloc['motif'])
        self.assertIn('SANS VERDICT', bloc['motif'])

    def test_une_tolerance_large_donne_le_verdict_dans_la_tolerance(self):
        bloc = mesurer(tolerance=25.0)
        self.assertEqual(bloc['verdict'], v.VERDICT_DANS_LA_TOLERANCE)
        self.assertEqual(bloc['tolerance_pct'], 25.0)
        self.assertEqual(bloc['tolerance_source'], 'societe')
        self.assertEqual(bloc['avertissement'], '')
        self.assertNotIn('SANS VERDICT', bloc['motif'])

    def test_un_ecart_au_dela_de_la_tolerance_avertit_en_nommant(self):
        resultat = {}
        bloc = mesurer(tolerance=5.0, resultat=resultat)
        self.assertEqual(bloc['verdict'], v.VERDICT_HORS_TOLERANCE)
        self.assertIn(str(bloc['ecart_pct']), bloc['avertissement'])
        self.assertIn('5.0', bloc['avertissement'])
        self.assertIn("n'est ajusté", bloc['avertissement'])
        # Un avertissement que personne n'affiche est un blocage silencieux.
        self.assertIn(bloc['avertissement'], resultat['avertissements'])

    def test_une_tolerance_sans_source_ne_donne_aucun_verdict(self):
        """``etapes.reglage`` refuse une valeur sans provenance (D-CALX 7)."""
        contexte_muet = contexte()
        contexte_muet['reglages_simulation'][v.CLE_TOLERANCE] = {
            'valeur': 5.0, 'source': ''}
        with cascade_isolee():
            bloc = v.ecart_vs_pvcalc(serie_entree(), contexte_muet,
                                     REPONSE_PVGIS, maintenant=FAITE_LE)
        self.assertIsNone(bloc['verdict'])
        self.assertIsNone(bloc['tolerance_pct'])


class FormeDuBlocTest(SimpleTestCase):
    """La forme du contrat, sur la chaîne ENTIÈRE et non la cascade réduite."""

    def setUp(self):
        self.resultat = {}
        v.ecart_vs_pvcalc(serie_entree(), contexte(), REPONSE_PVGIS,
                          resultat=self.resultat, maintenant=FAITE_LE)
        self.bloc = self.resultat[v.CLE_VALIDATION]

    def test_le_bloc_est_pose_sous_validation(self):
        self.assertIn(v.CLE_VALIDATION, self.resultat)

    def test_les_huit_cles_du_contrat_sont_servies(self):
        for cle in ('faite_le', 'total_chaine_locale_kwh',
                    'total_pvcalc_kwh', 'ecart_pct', 'tolerance_pct',
                    'verdict', 'avertissement', 'motif'):
            self.assertIn(cle, self.bloc)

    def test_aucune_cle_hors_de_la_liste_declaree(self):
        self.assertEqual(sorted(self.bloc), sorted(v.CLES_VALIDATION))

    def test_la_date_de_la_mesure_est_publiee(self):
        self.assertEqual(self.bloc['faite_le'], FAITE_LE)

    def test_le_motif_dit_que_ce_n_est_pas_une_validation(self):
        self.assertIn('ÉCART INFORMATIF', self.bloc['motif'])
        self.assertIn('jamais un ajustement', self.bloc['motif'])

    def test_la_chaine_entiere_publie_les_douze_mois(self):
        self.assertEqual(len(self.bloc['mensuel']), 12)


class FormePvcalcMensuelleTest(SimpleTestCase):
    """La réponse ``PVcalc`` (mensuelle) est lue comme la série horaire.

    Les DOUZE valeurs employées ici ne sont pas fabriquées : elles sont les
    douze totaux mensuels de la réponse ``seriescalc`` enregistrée, ré-écrits
    sous la forme que ``PVcalc`` sert (``outputs.monthly.fixed[].E_m``, celle
    que ``apps/parametres/pvgis_profils.py:1020`` lit déjà). Le test affirme
    que les deux formes donnent le MÊME total : c'est le lecteur qui est
    éprouvé, pas la donnée.
    """

    def setUp(self):
        mensuel = {}
        for ligne in REPONSE_PVGIS['outputs']['hourly']:
            mois = int(ligne['time'][4:6])
            mensuel[mois] = mensuel.get(mois, 0.0) + ligne['P'] / 1000.0
        self.reponse = {
            'inputs': REPONSE_PVGIS['inputs'],
            'outputs': {'monthly': {'fixed': [
                {'month': mois, 'E_m': mensuel[mois]}
                for mois in range(1, 13)]}},
        }

    def test_le_total_est_celui_de_la_serie_horaire(self):
        with cascade_isolee():
            mensuelle = v.ecart_vs_pvcalc(serie_entree(), contexte(),
                                          self.reponse, maintenant=FAITE_LE)
        horaire = mesurer()
        self.assertAlmostEqual(mensuelle['total_pvcalc_kwh'],
                               horaire['total_pvcalc_kwh'], places=1)
        self.assertAlmostEqual(mensuelle['ecart_pct'], horaire['ecart_pct'],
                               delta=DELTA_PCT)

    def test_les_mois_sans_numero_suivent_leur_rang(self):
        for ligne in self.reponse['outputs']['monthly']['fixed']:
            ligne.pop('month')
        with cascade_isolee():
            bloc = v.ecart_vs_pvcalc(serie_entree(), contexte(),
                                     self.reponse, maintenant=FAITE_LE)
        par_mois = {ligne['mois']: ligne['pvcalc_kwh']
                    for ligne in bloc['mensuel']}
        attendu = {ligne['mois']: ligne['pvcalc_kwh']
                   for ligne in mesurer()['mensuel']}
        self.assertEqual(par_mois, attendu)


class RefusNommesTest(SimpleTestCase):
    """Chaque refus est NOMMÉ — jamais un écart à 0 faute de mesure."""

    def _nul(self, bloc):
        for cle in ('total_chaine_locale_kwh', 'total_pvcalc_kwh',
                    'ecart_pct', 'verdict'):
            self.assertIsNone(bloc[cle])

    def test_aucune_reponse_a_confronter(self):
        bloc = v.ecart_vs_pvcalc(serie_entree(), contexte(), None)
        self._nul(bloc)
        self.assertEqual(bloc['motif'], v.MOTIF_SANS_ECART)

    def test_une_reponse_sans_production(self):
        bloc = v.ecart_vs_pvcalc(
            serie_entree(), contexte(),
            {'inputs': REPONSE_PVGIS['inputs'],
             'outputs': {'hourly': [{'time': '20200115:0009',
                                     'G(i)': 0.0}]}})
        self._nul(bloc)
        self.assertEqual(bloc['motif'], v.MOTIF_PVGIS_SANS_PRODUCTION)

    def test_deux_puissances_cretes_differentes(self):
        bloc = v.ecart_vs_pvcalc(serie_entree(), contexte(kwc=9.0),
                                 REPONSE_PVGIS)
        self._nul(bloc)
        self.assertIn('9.0', bloc['motif'])
        self.assertIn(str(KWC), bloc['motif'])

    def test_une_chaine_sans_energie_lisible(self):
        muette = {'pas_minutes': 60,
                  'points': [{'annee': 2020, 'mois': 1, 'jour': 15,
                              'heure': 12, 'gi_w_m2': 800.0}]}
        with cascade_isolee():
            bloc = v.ecart_vs_pvcalc(muette, contexte(), REPONSE_PVGIS)
        self._nul(bloc)
        self.assertEqual(bloc['motif'], v.MOTIF_CHAINE_SANS_ENERGIE)

    def test_un_refus_est_publie_dans_le_resultat(self):
        resultat = {}
        v.ecart_vs_pvcalc(serie_entree(), contexte(), None, resultat=resultat)
        self.assertEqual(resultat[v.CLE_VALIDATION]['motif'],
                         v.MOTIF_SANS_ECART)
        self.assertNotIn('avertissements', resultat)
