"""CALX195 — le harnais qui confronte notre chaîne à PVGIS lui-même.

LES DEUX CÔTÉS, ET POURQUOI ILS SONT COMPARABLES
--------------------------------------------------
Les deux réponses PVGIS employées ici sont RÉELLES et ENREGISTRÉES, et elles
décrivent la MÊME installation :

* ``fixtures_pvgis/seriescalc_casablanca_sud.json`` — ``pvcalculation=1``,
  ``peakpower=1``, ``loss`` = somme des postes (7,25 %), plan 15° plein sud, Casablanca
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

import datetime
import json
import pathlib
import sys
from unittest import mock

if __name__ == '__main__':  # pragma: no cover — chemin « --write » seulement
    import os

    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'erp_agentique.settings.dev')
    import django

    django.setup()

import pandas as pd
import pvlib
from django.test import SimpleTestCase
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import Array, FixedMount, PVSystem

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
                    'verdict', 'avertissement', 'motif', 'poste_principal'):
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


def _etape_essai(rang, nom, perte_kwh, perte_pct, *, gain=False, omise=''):
    return {'rang': rang, 'etape': nom, 'libelle': f'Libellé {nom}',
            'perte_kwh': perte_kwh, 'perte_pct': perte_pct, 'gain': gain,
            'motif_omission': omise}


#: Cascade ÉCRITE dans le test : ``thermique`` retire le plus d'énergie ;
#: ``salissure`` a la plus grande PART (pour tuer le mutant « perte_pct ») ;
#: l'étape omise et le gain portent de plus grands nombres et sont exclus.
CASCADE_ESSAI = {'etapes': [
    _etape_essai(1, 'horizon', 40.0, 2.0),
    _etape_essai(2, 'bifacial', 500.0, 9.0, gain=True),
    _etape_essai(3, 'thermique', 120.0, 6.0),
    _etape_essai(4, 'spectral', 900.0, 30.0, omise='non modélisée'),
    _etape_essai(5, 'salissure', 90.0, 12.0),
]}
PERTES_INEGALES = {'chaine_pct': 18.0, 'pvgis_pct': 14.0, 'egales': False}


class PostePrincipalTest(SimpleTestCase):
    """ACAL692 — le plus gros poste est CITÉ, jamais démontré ni inventé."""

    def _attendu(self, cascade):
        # Référence INDÉPENDANTE : max de perte_kwh des étapes appliquées.
        appliquees = [e for e in cascade['etapes']
                      if not e['motif_omission'] and not e['gain']]
        meilleure = max(appliquees, key=lambda e: (e['perte_kwh'], -e['rang']))
        return {cle: meilleure[cle] for cle in
                ('etape', 'libelle', 'perte_kwh', 'perte_pct', 'rang')}

    def test_le_poste_qui_retire_le_plus_d_energie(self):
        poste = v._poste_principal(CASCADE_ESSAI, PERTES_INEGALES, -4.0)
        self.assertEqual(poste, self._attendu(CASCADE_ESSAI))
        self.assertEqual(poste['etape'], 'thermique')

    def test_egalite_rang_le_plus_bas(self):
        cascade = {'etapes': [_etape_essai(7, 'b', 50.0, 1.0),
                              _etape_essai(3, 'a', 50.0, 2.0)]}
        poste = v._poste_principal(cascade, PERTES_INEGALES, -1.0)
        self.assertEqual(poste['rang'], 3)

    def test_les_cinq_cas_null(self):
        egales = dict(PERTES_INEGALES, egales=True)
        chaine_moins = {'chaine_pct': 10.0, 'pvgis_pct': 14.0,
                        'egales': False}
        for pertes, ecart, cascade in (
                (egales, -4.0, CASCADE_ESSAI),
                (chaine_moins, -4.0, CASCADE_ESSAI),
                (PERTES_INEGALES, 2.0, CASCADE_ESSAI),
                (PERTES_INEGALES, -4.0, {'etapes': []}),
                (PERTES_INEGALES, None, CASCADE_ESSAI)):
            self.assertIsNone(v._poste_principal(cascade, pertes, ecart))

    def test_bloc_vide_porte_la_cle_a_null(self):
        bloc = v.ecart_vs_pvcalc(serie_entree(), contexte(), None)
        self.assertIn('poste_principal', bloc)
        self.assertIsNone(bloc['poste_principal'])

    def test_le_motif_cite_le_poste_sans_le_dire_cause(self):
        texte = v.MOTIF_POSTE_PRINCIPAL.format(**self._attendu(CASCADE_ESSAI))
        self.assertIn('« Libellé thermique » (6.0 %', texte)
        self.assertIn('pas démontré comme cause', texte)


def _etape_kwh(rang, nom, avant, apres):
    return {'rang': rang, 'etape': nom, 'libelle': f'Libellé {nom}',
            'kwh_avant': avant, 'kwh_apres': apres,
            'perte_kwh': round(avant - apres, 3),
            'perte_pct': round(100.0 * (1.0 - apres / avant), 3),
            'gain': False, 'motif_omission': ''}


#: ACAL1606 — cascade chiffrée à la main : horizon −2 %, IAM −5 %, salissure
#: −2 %, thermique −10 %, onduleur −3 %. Perte de la cascade = 1 − 0,98 ×
#: 0,95 × 0,98 × 0,90 × 0,97 = 20,3 % ; PVGIS modélise lui-même l'IAM et la
#: température : perte SYSTÈME envoyée = 1 − 0,98 × 0,98 × 0,97 = 6,8 %.
CASCADE_SYSTEME = {'total_pct': 20.3, 'etapes': [
    _etape_kwh(1, 'horizon', 1000.0, 980.0),
    _etape_kwh(7, 'iam', 980.0, 931.0),
    _etape_kwh(9, 'salissure', 931.0, 912.38),
    _etape_kwh(12, 'thermique', 912.38, 821.142),
    _etape_kwh(22, 'onduleur', 821.142, 796.50774),
]}


class _ClientPvcalc:
    """Le client qui demande une production : il note la perte envoyée."""

    def __init__(self):
        self.envois = []

    def _params_communs(self, *, lat, lon, base, politique):
        return {'lat': lat, 'lon': lon, 'loss': politique.valeur_loss}

    def _appeler(self, service, parametres):
        self.envois.append(parametres)
        return {'inputs': {}}, False


class PerteSystemeTest(SimpleTestCase):
    """ACAL1606 — PVGIS reçoit la perte SYSTÈME, pas la cascade entière."""

    def test_la_perte_envoyee_exclut_iam_et_thermique(self):
        from apps.calepinage.services import simulation

        client = _ClientPvcalc()
        simulation._reponse_pvcalculation(
            client, {'inclinaison_deg': 30.0, 'azimut_pvgis_deg': 0.0},
            {'lat': 33.5, 'lon': -7.6}, {'fenetre_annees': (2020, 2020)},
            CASCADE_SYSTEME, 2.84)
        self.assertEqual(len(client.envois), 1)
        self.assertAlmostEqual(float(client.envois[0]['loss']), 6.8,
                               delta=0.05)

    def test_les_pertes_totales_publient_la_perte_systeme_et_ses_exclues(self):
        pertes = v._pertes_totales(CASCADE_SYSTEME, {'loss_pct': 6.8})
        self.assertAlmostEqual(pertes['chaine_pct'], 6.8, delta=0.05)
        self.assertTrue(pertes['egales'])
        self.assertEqual(pertes['cascade_pct'], 20.3)
        self.assertEqual([e['etape'] for e in pertes['etapes_exclues']],
                         ['iam', 'thermique'])
        self.assertEqual(pertes['etapes_exclues'][1]['perte_pct'], 10.0)

    def test_au_dela_de_la_tolerance_le_poste_principal_est_nomme(self):
        pertes = v._pertes_totales(CASCADE_SYSTEME, {'loss_pct': 6.8})
        poste = v._poste_principal(CASCADE_SYSTEME, pertes, -8.0,
                                   tolerance=5.0)
        self.assertEqual(poste['etape'], 'thermique')
        self.assertIsNone(v._poste_principal(CASCADE_SYSTEME, pertes, -3.0,
                                             tolerance=5.0))
        self.assertIsNone(v._poste_principal(CASCADE_SYSTEME, pertes, -8.0))

    def test_une_chaine_qui_produit_plus_que_pvgis_ne_cite_aucun_poste(self):
        """ACAL1961 — +8 % hors tolérance de 5 % : la chaîne produit PLUS que
        PVGIS, aucune perte n'explique l'écart ⇒ aucun poste cité."""
        pertes = v._pertes_totales(CASCADE_SYSTEME, {'loss_pct': 6.8})
        self.assertIsNone(v._poste_principal(CASCADE_SYSTEME, pertes, 8.0,
                                             tolerance=5.0))

    def test_le_motif_dit_a_pertes_systeme_egales(self):
        self.assertIn('à pertes système égales', v.MOTIF_ECART_INFORMATIF)

    def test_la_chaleur_omise_n_est_pas_a_pertes_egales(self):
        """ACAL1933 — la chaleur des panneaux omise (fiche sans NOCT ni Uc) :
        les deux pourcentages coïncident, mais PVGIS compte une perte que la
        chaîne ne compte pas ⇒ ``egales`` faux et l'étape nommée."""
        omise = dict(CASCADE_SYSTEME['etapes'][3], kwh_apres=912.38,
                     perte_kwh=0.0, perte_pct=0.0,
                     motif_omission='Ni NOCT ni Uc sur la fiche.')
        cascade = {'total_pct': 11.4, 'etapes_omises': ['thermique'],
                   'etapes': [*CASCADE_SYSTEME['etapes'][:3], omise,
                              CASCADE_SYSTEME['etapes'][4]]}
        pertes = v._pertes_totales(cascade, {'loss_pct': 6.8})
        self.assertAlmostEqual(pertes['chaine_pct'], 6.8, delta=0.05)
        self.assertFalse(pertes['egales'])
        self.assertEqual(pertes['omises_vs_pvgis'], [{
            'etape': 'thermique', 'libelle': 'Échauffement des modules',
            'designation': 'la chaleur des panneaux'}])
        self.assertEqual(v._pertes_totales(CASCADE_SYSTEME, {'loss_pct': 6.8})
                         ['omises_vs_pvgis'], [])
        motif = v._motif_pertes(pertes)
        self.assertNotIn('à pertes système égales', motif)
        self.assertIn('sans la chaleur des panneaux, que PVGIS compte', motif)


#: Une courbe de rendement à éclairement partiel telle que les fiches en
#: publient (celle de ``test_calx162_niveau_irradiance.COURBE_REELLE``).
COURBE_FAIBLE_ECLAIREMENT = [
    {'w_m2': 200, 'rendement_relatif_pct': 96.0},
    {'w_m2': 600, 'rendement_relatif_pct': 99.0},
    {'w_m2': 1000, 'rendement_relatif_pct': 100.0},
]


def _serie_avec_composantes():
    """La série d'entrée, plus Gb/Gd/Gr de la réponse ENREGISTRÉE au même
    point, même plan, même année (``components=1``) : l'IAM s'applique."""
    composantes = _charge('seriescalc_casablanca_sud_composantes.json')
    serie = serie_entree()
    for point, ligne in zip(serie['points'],
                            composantes['outputs']['hourly']):
        point.update(gb_i_w_m2=ligne['Gb(i)'], gd_i_w_m2=ligne['Gd(i)'],
                     gr_i_w_m2=ligne['Gr(i)'])
    return serie


def _mesure_chaine_complete(fiche):
    """La CHAÎNE ENTIÈRE (``ORDRE_ETAPES`` non réduit), contexte neuf."""
    ctx = contexte()
    ctx['fiche_module'] = dict(fiche)
    return v.ecart_vs_pvcalc(_serie_avec_composantes(), ctx, REPONSE_PVGIS,
                             maintenant=FAITE_LE)


class EgaliteSurLaChaineCompleteTest(SimpleTestCase):
    """ACAL1933 (revue) — sur la chaîne RÉELLE, le spectre (toujours omis en
    v1) ne compte pas : seule une étape que PVGIS modélise et que CE
    calepinage omet faute de donnée retire « à pertes système égales »."""

    def test_rien_d_omis_hors_toujours_omises_reste_a_pertes_egales(self):
        fiche = dict(_fiche_du_scenario(),
                     rendement_par_irradiance=COURBE_FAIBLE_ECLAIREMENT)
        bloc = _mesure_chaine_complete(fiche)
        pertes = bloc['pertes_totales']
        self.assertEqual(pertes['omises_vs_pvgis'], [])
        self.assertTrue(pertes['egales'])
        self.assertIn('à pertes système égales', bloc['motif'])
        self.assertEqual([e['etape'] for e in pertes['etapes_exclues']],
                         ['iam', 'niveau_irradiance', 'thermique'])

    def test_une_etape_pvgis_omise_par_choix_retire_l_egalite(self):
        bloc = _mesure_chaine_complete(_fiche_du_scenario())
        pertes = bloc['pertes_totales']
        self.assertFalse(pertes['egales'])
        self.assertEqual(pertes['omises_vs_pvgis'], [{
            'etape': 'niveau_irradiance', 'libelle': "Niveau d'irradiance",
            'designation': 'la perte par faible éclairement'}])
        self.assertNotIn('à pertes système égales', bloc['motif'])
        self.assertIn('sans la perte par faible éclairement, que PVGIS '
                      'compte', bloc['motif'])


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


# --- ACAL474 : le BANC des quatre sites marocains ----------------------------
#
# Pour chaque site, DEUX réponses PVGIS réelles enregistrées (production
# calculée par PVGIS, irradiance seule) rejouées contre notre chaîne ET contre
# pvlib ``ModelChain`` (PVWatts). L'écart MESURÉ est gelé dans
# ``donnees/banc_validation.json`` ; le test échoue si un écart s'éloigne du
# gel de plus d'un pas d'arrondi PUBLIÉ (10^-DECIMALES_ECART point) — ce n'est
# pas un seuil choisi. Mettre le gel à jour exige de nommer le changement de
# modèle voulu : ``python -m apps.calepinage.tests.test_calx195_validation
# --write "<changement de modèle>"``. PVsyst publie ± 5 % annuel et HelioScope
# < 1 % contre PVsyst : cités, jamais employés comme seuil.
BANC = pathlib.Path(__file__).resolve().parents[1] / 'donnees' / 'banc_validation.json'
SITES_BANC = ('casablanca', 'marrakech', 'oujda', 'agadir')
PAS_ARRONDI = 10.0 ** -v.DECIMALES_ECART


def _reponses_du_site(site):
    return (_charge('seriescalc_%s_sud.json' % site),
            _charge('seriescalc_%s_sud_irradiance.json' % site))


def _serie_du_site(irradiance):
    points = []
    for ligne in irradiance['outputs']['hourly']:
        moment = ligne['time']
        points.append({
            'annee': int(moment[0:4]), 'mois': int(moment[4:6]),
            'jour': int(moment[6:8]), 'heure': int(moment[9:11]),
            'gi_w_m2': ligne['G(i)'], 't2m_c': ligne['T2m'],
            'ws10m': ligne['WS10m'], 'h_sun_deg': ligne['H_sun'],
            'p_w': KWC * ligne['G(i)'],
        })
    return {'pas_minutes': 60, 'colonne_energie': 'p_w', 'points': points}


def _fiche_du_scenario():
    """La fiche module du scénario : celle des tests de l'étape thermique."""
    from apps.calepinage.tests.test_calx163_etape_thermique import (
        FICHE_COMPLETE)
    return dict(FICHE_COMPLETE)


def _mesure_moteur(site, *, fiche, thermique=True):
    produit, irradiance = _reponses_du_site(site)
    ctx = contexte()
    ctx['fiche_module'] = dict(fiche)
    ordre = ('thermique', POSTE_COMPARABLE) if thermique else (
        POSTE_COMPARABLE,)
    with mock.patch.object(chaine_pertes, 'ORDRE_ETAPES', ordre):
        return v.ecart_vs_pvcalc(_serie_du_site(irradiance), ctx, produit,
                                 maintenant=FAITE_LE)


def _mesure_pvlib(site, fiche):
    """Total pvlib (kWh) sur la MÊME série ; ``(None, motif)`` si la fiche se tait."""
    manquants = [cle for cle in ('temp_coeff_pmax_pct_c', 'uc_w_m2k')
                 if fiche.get(cle) is None]
    if manquants:
        return None, ('comparaison pvlib OMISE : la fiche module du scénario '
                      'ne porte pas %s' % ', '.join(manquants))
    produit, irradiance = _reponses_du_site(site)
    lignes = irradiance['outputs']['hourly']
    index = pd.to_datetime([ligne['time'] for ligne in lignes],
                           format='%Y%m%d:%H%M', utc=True)
    meteo = pd.DataFrame({
        'poa_global': [ligne['G(i)'] for ligne in lignes],
        'poa_direct': [ligne['G(i)'] for ligne in lignes],
        'poa_diffuse': 0.0,
        'temp_air': [ligne['T2m'] for ligne in lignes],
        'wind_speed': [ligne['WS10m'] for ligne in lignes]}, index=index)
    position = irradiance['inputs']['location']
    systeme = PVSystem(
        arrays=[Array(
            FixedMount(surface_tilt=15, surface_azimuth=180),
            module_parameters={'pdc0': KWC * 1000.0,
                               'gamma_pdc': fiche['temp_coeff_pmax_pct_c']
                               / 100.0},
            temperature_model_parameters={
                'u0': fiche['uc_w_m2k'],
                'u1': fiche.get('uv_w_m3sk') or 0.0})],
        inverter_parameters={'pdc0': KWC * 1000.0})
    chaine = ModelChain(
        systeme, Location(position['latitude'], position['longitude']),
        dc_model='pvwatts', ac_model='pvwatts', aoi_model='no_loss',
        spectral_model='no_loss', temperature_model='faiman',
        losses_model='no_loss')
    chaine.run_model_from_poa(meteo)
    perte = produit['inputs']['pv_module']['system_loss']
    return float(chaine.results.dc.sum()) / 1000.0 * (1 - perte / 100.0), ''


def mesurer_le_banc(fiche=None):
    """Le relevé complet des quatre sites (ce que ``--write`` fige)."""
    fiche = _fiche_du_scenario() if fiche is None else fiche
    sites = {}
    for site in SITES_BANC:
        bloc = _mesure_moteur(site, fiche=fiche)
        pvlib_kwh, motif = _mesure_pvlib(site, fiche)
        total_moteur = bloc['total_chaine_locale_kwh']
        sites[site] = {
            'total_moteur_kwh': total_moteur,
            'total_pvcalc_kwh': bloc['total_pvcalc_kwh'],
            'ecart_pvcalc_annuel_pct': bloc['ecart_pct'],
            'ecart_pvcalc_mensuel_pct': {
                str(ligne['mois']): ligne['ecart_pct']
                for ligne in bloc['mensuel']},
            'total_pvlib_kwh': (None if pvlib_kwh is None
                                else round(pvlib_kwh, 1)),
            'ecart_pvlib_annuel_pct': (
                None if pvlib_kwh is None
                else v._ecart_pct(total_moteur, pvlib_kwh)),
            'motif_pvlib': motif,
        }
    return sites


class BancQuatreSitesTest(SimpleTestCase):
    """Les écarts MESURÉS sont gelés au pas d'arrondi publié."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gel = json.loads(BANC.read_text(encoding='utf-8'))
        cls.mesure = mesurer_le_banc()

    def test_les_deux_reponses_de_chaque_site_decrivent_la_meme_meteo(self):
        for site in SITES_BANC:
            produit, irradiance = _reponses_du_site(site)
            gauche = produit['outputs']['hourly']
            droite = irradiance['outputs']['hourly']
            self.assertEqual([x['time'] for x in gauche],
                             [x['time'] for x in droite], site)
            self.assertEqual(max(abs(x['G(i)'] - y['G(i)'])
                                 for x, y in zip(gauche, droite)), 0.0, site)
            for charge in (produit, irradiance):
                self.assertEqual(charge['inputs']['meteo_data']['year_min'],
                                 2020, site)

    def test_les_quatre_sites_sont_au_gel(self):
        self.assertEqual(sorted(self.gel['sites']), sorted(SITES_BANC))

    def test_l_ecart_annuel_et_mensuel_contre_pvcalc_reste_au_gel(self):
        for site in SITES_BANC:
            gele, mesure = self.gel['sites'][site], self.mesure[site]
            self.assertAlmostEqual(mesure['ecart_pvcalc_annuel_pct'],
                                   gele['ecart_pvcalc_annuel_pct'],
                                   delta=PAS_ARRONDI, msg=site)
            for mois, ecart in gele['ecart_pvcalc_mensuel_pct'].items():
                self.assertAlmostEqual(
                    mesure['ecart_pvcalc_mensuel_pct'][mois], ecart,
                    delta=PAS_ARRONDI, msg='%s mois %s' % (site, mois))

    def test_l_ecart_annuel_contre_pvlib_reste_au_gel(self):
        for site in SITES_BANC:
            self.assertAlmostEqual(
                self.mesure[site]['ecart_pvlib_annuel_pct'],
                self.gel['sites'][site]['ecart_pvlib_annuel_pct'],
                delta=PAS_ARRONDI, msg=site)

    def test_sans_l_effet_thermique_plusieurs_sites_sortent_du_gel(self):
        """Le mutant : retirer ``thermique`` de la chaîne fait échouer le banc."""
        sortis = 0
        for site in SITES_BANC:
            sans = _mesure_moteur(site, fiche=_fiche_du_scenario(),
                                  thermique=False)['ecart_pct']
            gele = self.gel['sites'][site]['ecart_pvcalc_annuel_pct']
            sortis += abs(sans - gele) > PAS_ARRONDI
        self.assertGreaterEqual(sortis, 2)

    def test_une_fiche_sans_gamma_omet_pvlib_et_le_dit(self):
        fiche = {cle: valeur for cle, valeur in _fiche_du_scenario().items()
                 if cle != 'temp_coeff_pmax_pct_c'}
        total, motif = _mesure_pvlib('marrakech', fiche)
        self.assertIsNone(total)
        self.assertIn('temp_coeff_pmax_pct_c', motif)

    def test_le_gel_nomme_son_modele_et_sa_version_pvlib(self):
        self.assertEqual(self.gel['pvlib_version'], pvlib.__version__)
        self.assertTrue(self.gel['changement_de_modele'])


def ecrire_le_banc(arguments):  # pragma: no cover — chemin « --write » seulement
    """``--write "<changement de modèle voulu>"`` : régénère le gel."""
    if '--write' not in arguments or len(arguments) < 2:
        raise SystemExit('usage : --write "<changement de modèle voulu>" '
                         '(nommer le changement est obligatoire)')
    nom = [a for a in arguments if a != '--write'][0]
    import hashlib

    services = pathlib.Path(v.__file__).resolve().parent
    empreinte = hashlib.sha256()
    for fichier in sorted(services.glob('*.py')) + sorted(
            (services / 'etapes').glob('*.py')):
        empreinte.update(fichier.read_bytes())
    gel = {
        'mesure_le': datetime.date.today().isoformat(),
        'changement_de_modele': nom,
        'pvlib_version': pvlib.__version__,
        'moteur_empreinte_services': empreinte.hexdigest(),
        'pas_arrondi_pct': PAS_ARRONDI,
        'chaine_mesuree': ['thermique', POSTE_COMPARABLE],
        'fiche_module_scenario': _fiche_du_scenario(),
        'reponses': 'tests/fixtures_pvgis/seriescalc_<site>_sud[_irradiance].json',
        'sites': mesurer_le_banc(),
    }
    BANC.parent.mkdir(exist_ok=True)
    BANC.write_text(json.dumps(gel, ensure_ascii=False, indent=1) + '\n',
                    encoding='utf-8')
    return 'écrit : %s' % BANC


if __name__ == '__main__':  # pragma: no cover — chemin « --write » seulement
    print(ecrire_le_banc(sys.argv[1:]))
