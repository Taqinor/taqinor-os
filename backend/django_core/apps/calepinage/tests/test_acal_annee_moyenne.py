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

from django.test import SimpleTestCase, TestCase

from apps.calepinage.services import annee_moyenne
from apps.calepinage.services import simulation as service
from apps.calepinage.services.courbe_charge import (
    construire_courbe_charge,
)
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
    JUSTIFICATION, contexte_de_test as contexte_auto,
    serie_de_test as serie_auto,
)
from . import test_calx191_hors_reseau as hr191

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


#: R3-01 — les blocs dont les énergies sont comparées, et les clés d'énergie
#: de la maille électrique et de la performance (celles de la cascade :
#: ``annee_moyenne.CLES_ENERGIE_CASCADE``).
BLOCS_D_ENERGIE = ('cascade', 'ombrage', 'performance', 'production')
CLES_ENERGIE_AUTRES = ('p50_kwh', 'irradiation_plan_kwh_m2')
SOUS_BLOCS_PRODUCTION = ('par_module', 'par_chaine', 'par_mppt',
                         'par_onduleur', 'hors_chaine')


def _energies_publiees(blocs):
    """``{chemin: valeur}`` de chaque énergie cumulée publiée (nombre)."""
    trouvees = {}
    cles = annee_moyenne.CLES_ENERGIE_CASCADE | set(CLES_ENERGIE_AUTRES)

    def parcourir(noeud, chemin):
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                sous = '%s.%s' % (chemin, cle)
                if cle in cles and isinstance(valeur, (int, float)) \
                        and not isinstance(valeur, bool):
                    trouvees[sous] = float(valeur)
                parcourir(valeur, sous)
        elif isinstance(noeud, list):
            for rang, valeur in enumerate(noeud):
                parcourir(valeur, '%s[%d]' % (chemin, rang))

    for bloc in BLOCS_D_ENERGIE:
        if bloc != 'production':
            parcourir(blocs.get(bloc), bloc)
    for sous in SOUS_BLOCS_PRODUCTION:
        parcourir(blocs['production'].get(sous), 'production.' + sous)
    return trouvees


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

    def test_cascade_et_agregats_sur_l_annee_moyenne(self):
        # R3-01 — trois années identiques : CHAQUE énergie publiée de la
        # cascade (étapes, entrées, postes lisibles, irradiation), des
        # cascades par pan, de la maille électrique et de la performance
        # vaut celle d'une année (la somme en valait le triple).
        une, trois = (_energies_publiees(self.une),
                      _energies_publiees(self.trois))
        self.assertTrue(any(c.startswith('cascade.etapes') for c in une))
        for cle in ('production.par_module', 'production.par_onduleur',
                    'performance.irradiation_plan_kwh_m2',
                    'ombrage.par_pan', 'cascade.postes_lisibles'):
            self.assertTrue(any(c.startswith(cle) for c in une), cle)
        self.assertEqual(sorted(une), sorted(trois))
        for chemin, valeur in une.items():
            self.assertAlmostEqual(trois[chemin], valeur,
                                   delta=max(0.01, abs(valeur) * 1e-6),
                                   msg=chemin)

    def test_l_arrivee_de_la_cascade_est_le_p50(self):
        for blocs in (self.une, self.trois):
            arrivee = annee_moyenne._arrivee_de_la_cascade(blocs['cascade'])
            self.assertAlmostEqual(
                arrivee, blocs['production']['total']['p50_kwh'], delta=0.1)
            self.assertAlmostEqual(
                blocs['cascade']['postes_lisibles']['arrivee_kwh'], arrivee,
                delta=0.001)

    def test_incertitude_et_projection_partent_de_l_annee_moyenne(self):
        p50 = self.trois['production']['total']['p50_kwh']
        self.assertAlmostEqual(
            self.trois['incertitude']['quantiles']['p50_kwh'], p50,
            delta=0.1)
        projection = self.trois['production']['projection']
        if projection:
            self.assertLessEqual(projection[0]['p50_kwh'], p50 + 0.1)

    def test_garde_fou_rendement_specifique(self):
        # ACAL704 — aucune borne en code : SANS borne saisie, rien n'avertit
        # (mutant « remettre (600, 2400) » : échec ici, deux jours de fixture
        # CALX5 donnent un rendement absurde) ; AVEC une borne saisie et
        # sourcée sous le rendement, l'avertissement la cite.
        prefixe = MOTIF_RENDEMENT_INVRAISEMBLABLE.split('{')[0]

        def court(reglages):
            return simuler_calepinage(
                _Calepinage(), client=_ClientRejoue(), materiel=MATERIEL,
                reglages=reglages, enregistrer=False)['blocs']

        sans = court(REGLAGES)
        self.assertFalse(any(texte.startswith(prefixe)
                             for texte in sans['avertissements']))
        rendement = sans['production']['total']['specific_yield_kwh_kwc']
        avec_reglages = copy.deepcopy(REGLAGES)
        borne = rendement / 2.0
        avec_reglages['simulation']['rendement_specifique_max_kwh_kwc'] = {
            'valeur': borne, 'source': 'societe',
            'reference': 'Cas de test ACAL704'}
        avec = court(avec_reglages)
        signales = [texte for texte in avec['avertissements']
                    if texte.startswith(prefixe)]
        self.assertEqual(len(signales), 1)
        self.assertIn(f'{borne:g}', signales[0])
        self.assertIn('non saisie', signales[0])
        self.assertEqual(avec['production']['total']['specific_yield_kwh_kwc'],
                         rendement, 'la valeur est publiée telle quelle')

    def test_borne_haute_franchie_avertissement_servi(self):
        # ACAL1623 — la phrase écrite par la simulation FRAÎCHE arrive dans
        # ``avertissements`` de ``GET resultat/`` (elle s'y perdait : le
        # résultat servi ne portait que ceux du verdict électrique) ; sans
        # borne saisie, rien. Mutant : ne pas servir ceux de la simulation.
        from apps.calepinage.services.electrique import (
            CLE_SIMULATION, resultat_calepinage)
        from .test_calx70_resultat_sert_la_simulation import (
            _Calepinage as _Pivot)

        prefixe = MOTIF_RENDEMENT_INVRAISEMBLABLE.split('{')[0]

        def servis(reglages):
            pivot = _Pivot(copy.deepcopy(LAYOUT))
            empreinte = resultat_calepinage(pivot, materiel=MATERIEL)['hash_entree']
            blocs = simuler_calepinage(
                _Calepinage(layout=copy.deepcopy(LAYOUT)), client=_ClientRejoue(),
                materiel=MATERIEL, reglages=reglages, enregistrer=False)['blocs']
            blocs[CLE_SIMULATION]['hash_entree'] = empreinte
            pivot.resultat = blocs
            servi = resultat_calepinage(pivot, materiel=MATERIEL)
            self.assertTrue(servi['simule'])
            return [texte for texte in servi['avertissements'] if texte.startswith(prefixe)]

        self.assertEqual(servis(REGLAGES), [])
        avec = copy.deepcopy(REGLAGES)
        avec['simulation']['rendement_specifique_max_kwh_kwc'] = {
            'valeur': 1.0, 'source': 'Saisie', 'reference': 'Cas ACAL1623'}
        signales = servis(avec)
        self.assertEqual(len(signales), 1)
        self.assertIn('hors de la plage vraisemblable', signales[0])

    def test_borne_sans_source_n_est_pas_lue(self):
        from apps.calepinage.services.rendement_plausible import (
            avertissement_de_rendement)

        def contexte(**saisies):
            return {'reglages_simulation': saisies}

        sourcee = {'valeur': 2400.0, 'source': 'societe', 'reference': 'x'}
        self.assertTrue(avertissement_de_rendement(
            2650.0, contexte(rendement_specifique_max_kwh_kwc=sourcee)))
        self.assertEqual(avertissement_de_rendement(
            2650.0, contexte(rendement_specifique_max_kwh_kwc=dict(
                sourcee, source=''))), '')
        self.assertEqual(avertissement_de_rendement(2650.0, contexte()), '')
        bas = {'valeur': 3000.0, 'source': 'societe', 'reference': 'x'}
        texte = avertissement_de_rendement(
            2650.0, contexte(rendement_specifique_min_kwh_kwc=bas,
                             rendement_specifique_max_kwh_kwc=sourcee))
        self.assertIn('[3000 ; 2400]', texte)

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


def _blocs_de_publication(annees, kwh=(1000.0, 900.0)):
    """Des blocs publiés minimaux : une étape PARTAGÉE (copie superficielle
    de la cascade de la somme) entre la cascade et la cascade du pan."""
    entree = {'distribution': {'energie_totale_kwh': kwh[0],
                               'classes': [{'energie_kwh': kwh[0],
                                            'part_pct': 100.0}]}}
    # Le pourcentage se DÉDUIT des deux énergies (jamais un littéral de perte
    # en dur : garde CAL238) ; l'ombrage du pan est une donnée de fabrication.
    pct = 100.0 * (kwh[0] - kwh[1]) / kwh[0]
    ombrage_pan_pct = 2.0
    etape = {'etape': 'onduleur', 'motif_omission': '', 'kwh_avant': kwh[0],
             'kwh_apres': kwh[1], 'perte_kwh': kwh[0] - kwh[1],
             'perte_pct': pct, 'entree': entree}
    return {
        'production': {'total': {'annees_fenetre': annees,
                                 'p50_kwh': kwh[1] / annees}},
        'cascade': {'etapes': [etape], 'total_pct': pct,
                    'irradiation_incidente_kwh_m2': 2000.0,
                    'postes_lisibles': {'depart_kwh': kwh[0],
                                        'arrivee_kwh': kwh[1]}},
        'ombrage': {'par_pan': [{'pan': 'A', 'perte_ombrage_pct': ombrage_pan_pct,
                                 'cascade': {'etapes': [dict(etape)]}}]},
        'performance': {'irradiation_plan_kwh_m2': 2000.0, 'pr': 0.8},
        'meteo': {'mode': 'pluriannuel'},
        'simulation': {'calcule_le': '2026-11-22T01:00:00Z'},
    }


class PublicationAnneeMoyenneTest(SimpleTestCase):
    """R3-01 — la division à la publication, sans chaîne."""

    def test_annee_type_identique_au_bit(self):
        blocs = _blocs_de_publication(1)
        avant = copy.deepcopy(blocs)
        self.assertIs(annee_moyenne.publier_a_l_annee_moyenne(blocs), blocs)
        self.assertEqual(blocs, avant)
        self.assertIsNone(annee_moyenne._etat_des_energies(blocs))

    def test_chaque_energie_divisee_une_fois_le_reste_intact(self):
        blocs = annee_moyenne.publier_a_l_annee_moyenne(
            _blocs_de_publication(4))
        etape = blocs['cascade']['etapes'][0]
        self.assertEqual((etape['kwh_avant'], etape['kwh_apres'],
                          etape['perte_kwh']), (250.0, 225.0, 25.0))
        # L'entrée est PARTAGÉE avec la cascade du pan : divisée une fois.
        self.assertEqual(etape['entree']['distribution'],
                         {'energie_totale_kwh': 250.0,
                          'classes': [{'energie_kwh': 250.0,
                                       'part_pct': 100.0}]})
        pan = blocs['ombrage']['par_pan'][0]['cascade']['etapes'][0]
        self.assertEqual((pan['kwh_avant'], pan['kwh_apres']), (250.0, 225.0))
        self.assertEqual(blocs['cascade']['postes_lisibles'],
                         {'depart_kwh': 250.0, 'arrivee_kwh': 225.0})
        self.assertEqual(blocs['cascade']['irradiation_incidente_kwh_m2'],
                         500.0)
        self.assertEqual(blocs['performance'],
                         {'irradiation_plan_kwh_m2': 500.0, 'pr': 0.8})
        # Pourcentages, ratios et le N lui-même : tels quels.
        self.assertEqual((etape['perte_pct'], blocs['cascade']['total_pct'],
                          blocs['ombrage']['par_pan'][0]['perte_ombrage_pct'],
                          blocs['production']['total']['annees_fenetre']),
                         (10.0, 10.0, 2.0, 4))

    def test_distribution_d_ecretage_ramenee_a_l_annee(self):
        # ACAL1605 — fenêtre de 10 ans : l'étape d'écrêtage a perdu
        # 15 140 kWh sur la fenêtre (1 514 kWh par an) ; l'histogramme de
        # l'onduleur publiait 15 140,8 kWh d'énergie écrêtée, dix fois la
        # perte publiée de l'étape. Les deux se lisent à l'année moyenne.
        avant, ecrete, part = 200000.0, 15140.0, 7.57
        etape = {
            'etape': 'ecretage', 'kwh_avant': avant,
            'kwh_apres': avant - ecrete, 'perte_kwh': ecrete, 'perte_pct': part,
            'entree': {'distribution': {
                'borne_kw': 5.0, 'energie_totale_kwh': avant,
                'energie_ecretee_kwh': ecrete, 'part_ecretee_pct': part,
                'classes': [{'de_kw': 0.0, 'a_kw': 5.0,
                             'energie_kwh': 150000.0},
                            {'de_kw': 5.0, 'a_kw': 7.5,
                             'energie_kwh': 50000.0}]}},
        }
        blocs = annee_moyenne.publier_a_l_annee_moyenne({
            'production': {'total': {'annees_fenetre': 10}},
            'cascade': {'etapes': [etape]}})
        publie = blocs['cascade']['etapes'][0]
        distribution = publie['entree']['distribution']
        self.assertEqual(publie['perte_kwh'], 1514.0)
        self.assertEqual(distribution['energie_ecretee_kwh'], 1514.0)
        self.assertEqual(distribution['energie_ecretee_kwh'],
                         publie['perte_kwh'])
        # La somme des classes reste l'énergie entrant dans l'étape.
        self.assertEqual(sum(c['energie_kwh'] for c in distribution['classes']),
                         publie['kwh_avant'])
        self.assertEqual(distribution['energie_totale_kwh'],
                         publie['kwh_avant'])
        # Pourcentages et puissances : tels quels.
        self.assertEqual((distribution['part_ecretee_pct'],
                          distribution['borne_kw']), (7.57, 5.0))

    def test_plafond_d_injection_deja_ramene_non_redivise(self):
        # ACAL1605 — le plafond d'injection (``autoconsommation``, déjà à
        # l'année par ``_par_an``) ne passe pas par la cascade publiée.
        blocs = annee_moyenne.publier_a_l_annee_moyenne({
            'production': {'total': {'annees_fenetre': 10}},
            'cascade': {'etapes': []},
            'autoconsommation': {
                'plafond': {'energie_ecretee_kwh': 40.0},
                'etape_plafond': {'entree': {'energie_ecretee_kwh': 40.0}}}})
        auto = blocs['autoconsommation']
        self.assertEqual(auto['plafond']['energie_ecretee_kwh'], 40.0)
        self.assertEqual(
            auto['etape_plafond']['entree']['energie_ecretee_kwh'], 40.0)

    def test_etat_des_energies_rangees(self):
        # Rangé AVANT la correction : l'arrivée vaut N × P50.
        etat = annee_moyenne._etat_des_energies(_blocs_de_publication(4))
        self.assertEqual(etat, {
            'annees': 4, 'mode': 'pluriannuel',
            'calcule_le': '2026-11-22T01:00:00Z', 'p50_kwh': 225.0,
            'arrivee_kwh': 900.0, 'fenetre_entiere': True})
        juste = annee_moyenne.publier_a_l_annee_moyenne(
            _blocs_de_publication(4))
        self.assertIs(annee_moyenne._etat_des_energies(juste)[
            'fenetre_entiere'], False)
        sans_cascade = dict(_blocs_de_publication(4), cascade=None)
        self.assertIsNone(annee_moyenne._etat_des_energies(sans_cascade)[
            'fenetre_entiere'])

    def test_sans_dry_run_refuse_avant_toute_lecture(self):
        import io

        from django.core.management import CommandError, call_command

        with self.assertRaises(CommandError) as refus:
            call_command('acal_dryrun_annee_moyenne', stdout=io.StringIO())
        self.assertIn('ajoutez --dry-run', str(refus.exception))


class ListerPluriannuelsTest(SimpleTestCase):
    """ACAL1252 (D-ACAL-64) — la sélection PURE du relevé, sur des traces
    rangées construites à la main."""

    def _entree(self, resultat, documents=(), objet='calepinage'):
        return {'company_id': 7, 'calepinage_id': 11, 'objet': objet,
                'objet_id': 11, 'resultat': resultat,
                'documents': list(documents)}

    def test_pluriannuel_n3_liste_avec_energie_divisee(self):
        rangees = _blocs_de_publication(3)
        releve = annee_moyenne.lister_pluriannuels([self._entree(
            rangees, [{'nom': 'rapport_etude__v001__fr.pdf',
                       'remis_le': datetime.datetime(
                           2026, 11, 22, 9, 0,
                           tzinfo=datetime.timezone.utc)}])])
        self.assertEqual(releve['indetermines'], [])
        self.assertEqual(releve['comptes'],
                         {'lus': 1, 'concerne': 1, 'indetermine': 0})
        simulation, document = releve['concernes']
        self.assertEqual(simulation, {
            'company_id': 7, 'calepinage_id': 11, 'objet': 'calepinage',
            'objet_id': 11, 'mode': 'pluriannuel', 'annees': 3,
            'energie_rangee_kwh': 900.0, 'energie_par_an_kwh': 300.0,
            'p50_kwh': 300.0, 'document': None,
            'date': '2026-11-22T01:00:00Z', 'motif': ''})
        self.assertEqual(document['document'], 'rapport_etude__v001__fr.pdf')
        self.assertEqual(document['date'], '2026-11-22T09:00:00+00:00')
        self.assertEqual(document['energie_par_an_kwh'], 300.0)
        # Rien n'est lu en dehors des identifiants : aucune clé nominative.
        self.assertFalse({'titre', 'nom', 'client', 'telephone', 'email',
                          'adresse', 'gps'} & set(simulation))
        # La trace rangée n'est pas touchée (fonction pure).
        self.assertEqual(rangees, _blocs_de_publication(3))

    def test_annee_type_et_deja_moyenne_non_listees(self):
        juste = annee_moyenne.publier_a_l_annee_moyenne(
            _blocs_de_publication(3))
        releve = annee_moyenne.lister_pluriannuels([
            self._entree(_blocs_de_publication(1)), self._entree(juste),
            self._entree({'roof_layout': {}}), self._entree(None)])
        self.assertEqual((releve['concernes'], releve['indetermines']),
                         ([], []))
        self.assertEqual(releve['comptes']['lus'], 4)

    def test_trace_sans_n_ni_preuve_indeterminee(self):
        sans_trace = _blocs_de_publication(3)
        del sans_trace['production']['total']['annees_fenetre']
        del sans_trace['meteo']
        sans_cascade = dict(_blocs_de_publication(3), cascade=None)
        releve = annee_moyenne.lister_pluriannuels([
            self._entree(sans_trace), self._entree(sans_cascade,
                                                   objet='variante')])
        self.assertEqual(releve['concernes'], [])
        sans_n, sans_preuve = releve['indetermines']
        self.assertEqual((sans_n['annees'], sans_n['mode'],
                          sans_n['energie_par_an_kwh']), (None, None, None))
        self.assertIn("nombre d'années de la fenêtre non rangé",
                      sans_n['motif'])
        self.assertEqual((sans_preuve['objet'], sans_preuve['annees'],
                          sans_preuve['energie_par_an_kwh']),
                         ('variante', 3, None))
        self.assertIn('impossible à prouver', sans_preuve['motif'])

    def test_document_remis_avant_le_calcul_indetermine(self):
        releve = annee_moyenne.lister_pluriannuels([self._entree(
            _blocs_de_publication(3),
            [{'nom': 'diagramme_pertes__v001__fr.svg',
              'remis_le': '2026-11-20T08:00:00+00:00'}])])
        self.assertEqual(len(releve['concernes']), 1)
        (avant,) = releve['indetermines']
        self.assertEqual(avant['document'], 'diagramme_pertes__v001__fr.svg')
        self.assertIsNone(avant['energie_par_an_kwh'])
        self.assertIn('remis avant le calcul rangé', avant['motif'])


class CommandeAnneeMoyenneTest(TestCase):
    """Q2 — la liste des documents remis, en lecture seule."""

    def setUp(self):
        from django.contrib.contenttypes.models import ContentType

        from authentication.models import Company

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client
        from apps.records.models import Attachment

        self.company = Company.objects.create(nom='Fenetre Co',
                                              slug='fenetre-co-r301')
        client = Client.objects.create(company=self.company, nom='Client')
        self.faux = Calepinage.objects.create(
            company=self.company, client=client, titre='Pluriannuel',
            resultat=_blocs_de_publication(10))
        Calepinage.objects.create(company=self.company, client=client,
                                  titre='Année type',
                                  resultat=_blocs_de_publication(1))
        Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.faux.pk, file_key='cle/rapport',
            filename='rapport_etude__v001__fr.pdf')

    def test_dry_run_liste_sans_ecrire(self):
        import io

        from django.core.management import call_command
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        sortie = io.StringIO()
        with CaptureQueriesContext(connection) as requetes:
            call_command('acal_dryrun_annee_moyenne', '--dry-run',
                         '--company', 'fenetre-co-r301', stdout=sortie)
        ecritures = [r['sql'] for r in requetes.captured_queries
                     if r['sql'].lstrip().upper().startswith(
                         ('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(ecritures, [])
        # Que des lectures : chaque requête est un SELECT.
        self.assertTrue(all(r['sql'].lstrip().upper().startswith('SELECT')
                            for r in requetes.captured_queries),
                        [r['sql'] for r in requetes.captured_queries])
        lignes = sortie.getvalue().splitlines()
        self.assertEqual(lignes[0],
                         'DRY-RUN R3-01 (lecture seule) — aucune écriture')
        prefixe = '%s | %s | calepinage %s | ' % (
            self.company.pk, self.faux.pk, self.faux.pk)
        concernes = [ligne for ligne in lignes if ligne.startswith(prefixe)]
        self.assertEqual(len(concernes), 2)
        self.assertTrue(concernes[0].startswith(
            prefixe + '— | 2026-11-22T01:00:00Z | pluriannuel | 10 | '
            '900.0 | 90.0 | 90.0'), concernes[0])
        self.assertIn('| rapport_etude__v001__fr.pdf |', concernes[1])
        self.assertTrue(concernes[1].endswith(
            '| pluriannuel | 10 | 900.0 | 90.0 | 90.0 | —'), concernes[1])
        # Aucun titre (il peut porter le nom du client).
        self.assertNotIn('Pluriannuel |', sortie.getvalue())
        self.assertIn('2 résultat(s) rangé(s) lu(s) ; 1 concerné(s) ; 0 '
                      'indéterminé(s) ; 2 ligne(s) concernée(s) dont 1 '
                      'document(s) remis ; 0 ligne(s) indéterminée(s).',
                      lignes)
        # Le même relevé par l'identifiant de société, en JSON.
        sortie_json = io.StringIO()
        call_command('acal_dryrun_annee_moyenne', '--dry-run', '--json',
                     '--company', str(self.company.pk), stdout=sortie_json)
        import json
        releve = json.loads(sortie_json.getvalue())
        self.assertEqual([r['energie_par_an_kwh']
                          for r in releve['concernes']], [90.0, 90.0])
        self.assertEqual({r['company_id'] for r in releve['concernes']},
                         {self.company.pk})
        # La commande n'appelle que la sélection pure et des lectures : ni
        # get_or_create (get_for_model), ni save, ni tâche de fond.
        from unittest import mock

        from django.contrib.contenttypes.models import ContentTypeManager
        from django.db.models import Model
        with mock.patch.object(ContentTypeManager, 'get_for_model',
                               side_effect=AssertionError('get_or_create')), \
                mock.patch.object(Model, 'save',
                                  side_effect=AssertionError('save')), \
                mock.patch('core.jobs.submit',
                           side_effect=AssertionError('tâche')):
            call_command('acal_dryrun_annee_moyenne', '--dry-run',
                         stdout=io.StringIO())


# ---------------------------------------------------------------------------
# ACAL1670 — la GARDE de la classe K-ANNEE-MOYENNE (fiche T2/classes) : deux
# années IDENTIQUES publient, pour chaque grandeur annuelle, ce que publie une
# année. La liste n'est pas écrite à la main : on PARCOURT le résultat, donc
# une clé neuve non ramenée échoue sans que personne ne pense à l'ajouter.
# ---------------------------------------------------------------------------

#: Une grandeur « par an » : une énergie (``*_kwh``, ``kwh_an``,
#: ``kwh_hors_production_an``), un compte d'heures (``heures*``) ou, sous
#: ``profil_mensuel``, la ligne ``kwh`` d'un mois.
def _est_annuelle(cle, dans_profil):
    return (cle.endswith('_kwh') or cle.startswith('heures')
            or cle.startswith('kwh_') or (dans_profil and cle == 'kwh'))


def _grandeurs_annuelles(noeud, chemin='', dans_profil=False, trouvees=None):
    """``{chemin: nombre}`` de chaque grandeur annuelle publiée sous ``noeud``."""
    trouvees = {} if trouvees is None else trouvees
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            sous = '%s.%s' % (chemin, cle) if chemin else cle
            if (isinstance(valeur, (int, float))
                    and not isinstance(valeur, bool)
                    and _est_annuelle(cle, dans_profil)):
                trouvees[sous] = float(valeur)
            _grandeurs_annuelles(valeur, sous,
                                 dans_profil or cle == 'profil_mensuel',
                                 trouvees)
    elif isinstance(noeud, list):
        for rang, valeur in enumerate(noeud):
            _grandeurs_annuelles(valeur, '%s[%d]' % (chemin, rang),
                                 dans_profil, trouvees)
    return trouvees


def _deux_ans(fabrique, **kwargs):
    series = [fabrique(annee=annee, **kwargs) for annee in ANNEES[:2]]
    return {'points': [point for serie in series
                       for point in serie['points']],
            'pas_minutes': 60, 'colonne_energie': 'p_ac_kw'}


def _fenetre(contexte, annees):
    contexte[CLE_ANNEES_FENETRE] = annees
    return contexte


def _scenario_consommation(annees):
    serie = serie_auto() if annees == 1 else _deux_ans(serie_auto)
    contexte = _fenetre(contexte_auto(heures=annees * 8760), annees)
    rendu = construire_courbe_charge(serie, contexte)
    assert rendu['omissions']['consommation'] == ''
    return rendu['consommation']


def _scenario_plafond(annees):
    serie = serie_auto() if annees == 1 else _deux_ans(serie_auto)
    contexte = _fenetre(contexte_auto(
        heures=annees * 8760, plafond=3.0, justification=JUSTIFICATION),
        annees)
    _suite, resultat = bloc_auto.bloc_autoconsommation(serie, contexte)
    assert resultat['motif_absence'] == ''
    return resultat


def _scenario_batterie(annees):
    serie = serie_batterie() if annees == 1 else _deux_ans(serie_batterie)
    contexte = _fenetre(contexte_batterie(heures=annees * 8760), annees)
    _suite, resultat = bloc_bat.bloc_batterie(serie, contexte)
    assert resultat['motif_absence'] == ''
    return resultat


def _scenario_hors_reseau(annees):
    serie = (hr191.serie_de_test() if annees == 1
             else _deux_ans(hr191.serie_de_test))
    contexte = _fenetre(hr191.contexte_de_test(heures=annees * 8760,
                                               jours=0.1), annees)
    contexte[hr191.bloc.CLE_CONTEXTE]['groupe'] = dict(hr191.GROUPE)
    _suite, resultat = hr191.bloc.bloc_hors_reseau(serie, contexte)
    assert resultat['motif_absence'] == ''
    return resultat


class GardeAnneeMoyenneTest(SimpleTestCase):
    """ACAL1670 — une ligne par ligne de la matrice : consommation, batterie,
    plafond d'injection, hors réseau (avec groupe) ; énergies, heures, profil
    mensuel. Deux années identiques ⇒ les nombres d'UNE année (à l'arrondi et
    au report d'état de charge de la 2e année près)."""

    SCENARIOS = (('consommation', _scenario_consommation),
                 ('plafond d\'injection', _scenario_plafond),
                 ('batterie', _scenario_batterie),
                 ('hors réseau', _scenario_hors_reseau))

    def test_deux_annees_identiques_publient_les_nombres_d_une_annee(self):
        heures_lues = []
        for nom, scenario in self.SCENARIOS:
            with self.subTest(bloc=nom):
                une = _grandeurs_annuelles(scenario(1))
                deux = _grandeurs_annuelles(scenario(2))
                # Garde de couverture : un bloc qui ne publie rien ne passe pas.
                self.assertGreater(len(une), 3, nom)
                self.assertTrue(any(abs(v) > 9.0 for v in une.values()), nom)
                for chemin, attendu in une.items():
                    self.assertIn(chemin, deux, '%s : %s manque' % (nom, chemin))
                    self.assertAlmostEqual(
                        deux[chemin], attendu,
                        delta=max(3.0, abs(attendu) * 0.01),
                        msg='%s : %s (une année %s, deux années %s)'
                            % (nom, chemin, attendu, deux[chemin]))
                heures_lues += [c for c, v in une.items()
                                if c.split('.')[-1].startswith('heures')
                                and abs(v) > 9.0]
        # La matrice a une ligne « heures » : au moins une a été COMPARÉE.
        self.assertTrue(heures_lues)

    def test_le_profil_mensuel_de_la_consommation_est_compare(self):
        une = _grandeurs_annuelles(_scenario_consommation(1))
        mois = [c for c in une if c.startswith('profil_mensuel[')]
        self.assertEqual(len(mois), 12)
