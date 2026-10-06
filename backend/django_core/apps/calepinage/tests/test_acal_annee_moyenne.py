"""ACAL54 — le P50 et toutes les énergies sur l'ANNÉE MOYENNE de la fenêtre.

Constat C-ACAL-079 : la chaîne sommait TOUTES les heures de la fenêtre
météo et publiait la somme comme « P50 annuel » — une fenêtre pluriannuelle
de 10 ans rendait un P50 dix fois trop grand (≈ 170 000 kWh pour 8,52 kWc),
et ``_repartir`` forçait les années à sommer à ce faux total.

Désormais : P50 = moyenne des totaux annuels observés, mensuel = mois moyen,
par pan idem, ``production.annees[]`` = totaux OBSERVÉS (``observe: true``),
``portee = 'annee_moyenne'`` et ``annees_fenetre = N`` ; batterie,
autoconsommation et hors réseau publient leurs énergies à l'année moyenne ;
garde-fou de vraisemblance du rendement spécifique ; ``VERSION_SIMULATION``
bumpée.

Chaîne RÉELLE (``simuler_calepinage``, client rejoué) et blocs aval RÉELS
(fixtures de CALX188/CALX190). Aucun mock de la chaîne.

Run :
    python manage.py test apps.calepinage.tests.test_acal_annee_moyenne -v2
"""
from __future__ import annotations

import copy
import datetime

from django.test import SimpleTestCase

from apps.calepinage.services import simulation as service
from apps.calepinage.services.chaine_pertes import (
    CLE_ANNEES_FENETRE, MOTIF_RENDEMENT_INVRAISEMBLABLE,
)
from apps.calepinage.services.etapes import autoconsommation as bloc_auto
from apps.calepinage.services.etapes import batterie as bloc_bat
from apps.calepinage.services.simulation import simuler_calepinage

from .test_calx5_simulation import (
    LAYOUT, MATERIEL, REGLAGES, _Calepinage, _ClientRejoue, _reponse_meteo,
)
from .test_calx188_batterie import (
    contexte_de_test as contexte_batterie, serie_de_test as serie_batterie,
)
from .test_calx190_autoconsommation import (
    contexte_de_test as contexte_auto, serie_de_test as serie_auto,
)

#: Trois années NON bissextiles : trois années pleines identiques.
ANNEES = (2018, 2019, 2021)


def _reponse_annees(annees):
    """La réponse rejouée : ``annees`` années PLEINES et identiques."""
    reponse = _reponse_meteo()
    points = []
    for annee in annees:
        depart = datetime.datetime(annee, 1, 1)
        for rang in range(8760):
            moment = depart + datetime.timedelta(hours=rang)
            globale = max(0.0, 900.0 - abs(moment.hour - 13) * 130.0)
            points.append({
                'annee': moment.year, 'mois': moment.month,
                'jour': moment.day, 'heure': moment.hour,
                'gi_w_m2': globale, 'gb_i_w_m2': globale * 0.8,
                'gd_i_w_m2': globale * 0.18, 'gr_i_w_m2': globale * 0.02,
                't2m_c': 18.0, 'ws10m': 2.5,
                'h_sun_deg': max(0.0, 60.0 - abs(moment.hour - 13) * 8.0),
            })
    reponse['points'] = points
    reponse['serie_horaire']['points'] = points
    reponse['meteo']['annees'] = list(annees)
    reponse['annees'] = list(annees)
    return reponse


def _reglages(annees):
    reglages = copy.deepcopy(REGLAGES)
    reglages['simulation']['fenetre_annees'] = {
        'valeur': [min(annees), max(annees)], 'source': 'note interne',
        'reference': 'fenêtre de test ACAL54'}
    return reglages


def _simuler(annees):
    rendu = simuler_calepinage(
        _Calepinage(layout=copy.deepcopy(LAYOUT)),
        client=_ClientRejoue(_reponse_annees(annees)), materiel=MATERIEL,
        reglages=_reglages(annees), enregistrer=False)
    return rendu['blocs']


class AnneeMoyenneTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.une = _simuler(ANNEES[:1])
        cls.trois = _simuler(ANNEES)

    def test_p50_est_la_moyenne_des_annees(self):
        une = self.une['production']['total']
        trois = self.trois['production']['total']

        self.assertAlmostEqual(trois['p50_kwh'], une['p50_kwh'], delta=0.1)
        self.assertEqual(trois['portee'], 'annee_moyenne')
        self.assertEqual(trois['annees_fenetre'], 3)
        self.assertEqual(une['annees_fenetre'], 1)
        annees = self.trois['production']['annees']
        self.assertEqual([ligne['annee'] for ligne in annees], list(ANNEES))
        for ligne in annees:
            self.assertIs(ligne['observe'], True)
            self.assertAlmostEqual(ligne['kwh'], trois['p50_kwh'], delta=0.1)
        self.assertAlmostEqual(
            trois['specific_yield_kwh_kwc'],
            round(trois['p50_kwh'] / trois['kwc'], 1), delta=0.1)
        for ligne in self.trois['production']['par_pan']:
            self.assertAlmostEqual(
                ligne['p50_kwh'],
                self.une['production']['par_pan'][0]['p50_kwh'], delta=0.1)

    def test_mensuel_moyenne_par_mois_calendaire(self):
        for un_mois, trois_mois in zip(self.une['production']['mensuel'],
                                       self.trois['production']['mensuel']):
            self.assertAlmostEqual(trois_mois['p50_kwh'], un_mois['p50_kwh'],
                                   delta=0.1, msg=un_mois['mois'])
        somme = sum(mois['p50_kwh'] for mois in
                    self.trois['production']['mensuel'])
        self.assertAlmostEqual(somme,
                               self.trois['production']['total']['p50_kwh'],
                               delta=0.1)

    def test_incertitude_et_projection_partent_de_l_annee_moyenne(self):
        p50 = self.trois['production']['total']['p50_kwh']
        self.assertAlmostEqual(
            self.trois['incertitude']['quantiles']['p50_kwh'], p50,
            delta=0.1)
        projection = self.trois['production']['projection']
        if projection:
            self.assertLessEqual(projection[0]['p50_kwh'], p50 + 0.1)

    def test_garde_fou_rendement_specifique(self):
        # 900 W/m² de crête, 365 jours : un rendement hors [600 ; 2400] est
        # SIGNALÉ, jamais borné.
        rendement = self.trois['production']['total'][
            'specific_yield_kwh_kwc']
        prefixe = MOTIF_RENDEMENT_INVRAISEMBLABLE.split('{')[0]
        signale = any(texte.startswith(prefixe)
                      for texte in self.trois.get('avertissements') or [])
        self.assertEqual(signale, not 600.0 <= rendement <= 2400.0)
        # Deux jours seulement (fixture CALX5) : rendement absurde ⇒ signalé.
        court = simuler_calepinage(
            _Calepinage(), client=_ClientRejoue(), materiel=MATERIEL,
            reglages=REGLAGES, enregistrer=False)['blocs']
        self.assertTrue(any(texte.startswith(prefixe)
                            for texte in court['avertissements']))
        self.assertIsNotNone(court['production']['total']['p50_kwh'])

    def test_version_simulation_bumpee_perime(self):
        # ACAL54 a bumpé ``sim-1`` (somme des années) ; une version
        # ultérieure (ACAL128 : ``sim-3``) ne la ramène jamais en arrière.
        self.assertNotEqual(service.VERSION_SIMULATION, 'sim-1')
        self.assertGreaterEqual(int(service.VERSION_SIMULATION.split('-')[1]),
                                2)
        self.assertEqual(self.trois['simulation']['version_simulation'],
                         service.VERSION_SIMULATION)
        # Une simulation stockée sous ``sim-1`` ne porte plus l'empreinte
        # d'aujourd'hui : elle est servie PÉRIMÉE.
        from unittest import mock

        from apps.calepinage.services.electrique import resultat_calepinage

        pivot = _Calepinage(layout=copy.deepcopy(LAYOUT))
        with mock.patch.object(service, 'VERSION_SIMULATION', 'sim-1'):
            simuler_calepinage(pivot, client=_ClientRejoue(),
                               materiel=MATERIEL, reglages=REGLAGES,
                               enregistrer=True)
        servi = resultat_calepinage(pivot, materiel=MATERIEL,
                                    reglages=REGLAGES)
        self.assertTrue(servi['simulation_perimee'])


def _trois_ans(fabrique, **kwargs):
    series = [fabrique(annee=annee, **kwargs) for annee in ANNEES]
    return {'points': [point for serie in series
                       for point in serie['points']],
            'pas_minutes': 60, 'colonne_energie': 'p_ac_kw'}


class BlocsAvalTest(SimpleTestCase):

    def test_batterie_et_autoconsommation_annee_moyenne(self):
        # Batterie : la même année répétée trois fois, énergies /3. Seul
        # l'état de charge reporté d'une année sur l'autre (la 1re part de
        # l'état initial) les distingue : 3 kWh ou 0,1 %.
        _s, une = bloc_bat.bloc_batterie(serie_batterie(),
                                         contexte_batterie())
        contexte = contexte_batterie(heures=3 * 8760)
        contexte[CLE_ANNEES_FENETRE] = 3
        _s, trois = bloc_bat.bloc_batterie(_trois_ans(serie_batterie),
                                           contexte)
        self.assertEqual(trois['motif_absence'], '')
        for cle in ('production_kwh', 'consommation_kwh', 'export_kwh',
                    'autoconsomme_kwh', 'import_reseau_kwh'):
            attendu = une['total']['energie'][cle]
            self.assertAlmostEqual(trois['total']['energie'][cle], attendu,
                                   delta=max(3.0, abs(attendu) * 0.001),
                                   msg=cle)
        attendu = une['total']['energie_restituee_kwh']
        self.assertAlmostEqual(trois['total']['energie_restituee_kwh'],
                               attendu, delta=max(3.0, attendu * 0.001))
        # Sans la division, la somme des trois années serait publiée.
        self.assertLess(trois['total']['energie']['production_kwh'],
                        2 * une['total']['energie']['production_kwh'])

        # Autoconsommation : énergies /3, taux inchangés.
        _s, une = bloc_auto.bloc_autoconsommation(serie_auto(),
                                                  contexte_auto())
        contexte = contexte_auto(heures=3 * 8760)
        contexte[CLE_ANNEES_FENETRE] = 3
        _s, trois = bloc_auto.bloc_autoconsommation(_trois_ans(serie_auto),
                                                    contexte)
        self.assertEqual(trois['motif_absence'], '')
        for cle in ('consommation_kwh', 'production_kwh', 'autoconsomme_kwh',
                    'export_reseau_kwh', 'import_reseau_kwh'):
            self.assertAlmostEqual(trois['energie'][cle],
                                   une['energie'][cle], delta=0.1, msg=cle)
        self.assertEqual(trois['taux_autoconsommation'],
                         une['taux_autoconsommation'])
