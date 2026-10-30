"""CIQ231 — sensibilités industrielles calculées sur les SEULES valeurs
saisies par Reda (``TariffSettings.sensibilites_ci``), base à 0 %
d'indexation, aucun scénario par défaut.

SimpleTestCase : aucune base.
"""
import copy
import json
import math
import os

from django.test import SimpleTestCase

from apps.ventes import economie_ci as eco
from apps.ventes import tarif_ci
from apps.ventes.quote_engine import pricing

_ICI = os.path.dirname(__file__)

TARIF_MT = tarif_ci.tarif_applicable({
    'contrat': 'mt_general', 'base_tarifs': 'ht', 'provenance': 'facture',
    'date_facture': '2026-08-31',
    'mt': {'tarif_pointe': 1.6, 'tarif_pleines': 1.1, 'tarif_creuses': 0.8}})
TARIF_MT_DECLARE = {
    'contrat': 'mt_general', 'base_tarifs': 'ht', 'provenance': 'facture',
    'date_facture': '2026-08-31',
    'mt': {'tarif_pointe': 1.6, 'tarif_pleines': 1.1, 'tarif_creuses': 0.8}}
INVESTISSEMENT = {'ht': 300000.0, 'ttc': 360000.0}


def _apercu_contrat():
    with open(os.path.join(_ICI, os.pardir, 'contract_samples',
                           'etude_ci_preview.json'), encoding='utf-8') as fh:
        apercu = copy.deepcopy(json.load(fh)['exemple'])
    apercu['entrees_resolues']['tension'] = {'valeur': 'mt',
                                             'provenance': None}
    return apercu


def _apercu_main():
    """Un seul jour type (juin, 30 jours) : 10 h GMT produit 40 pour une
    charge de 100 ; 12 h GMT produit 100 pour une charge de 50 (surplus 50).
    Les deux heures sont en heures PLEINES (été, 7-18 h GMT)."""
    auto = [0.0] * 24
    surplus = [0.0] * 24
    charge = [0.0] * 24
    auto[10], charge[10] = 40.0, 100.0
    auto[12], surplus[12], charge[12] = 50.0, 50.0, 50.0
    return {
        'entrees_resolues': {'tension': {'valeur': 'mt'},
                             'tva_recuperable': {'valeur': 'oui'}},
        'profil_charge': {'jours_types': [
            {'mois': 6, 'type_jour': 'ouvre', 'nb_jours': 30,
             'charge_kwh': charge}]},
        'bilan': {'production_kwh': (40.0 + 100.0) * 30,
                  'horaire': [{'mois': 6, 'type_jour': 'ouvre',
                               'nb_jours': 30, 'autoconso_kwh': auto,
                               'surplus_kwh': surplus}]},
        'alertes': [],
    }


def _bloc(apercu, scenarios, mode='industriel'):
    return eco.assembler_economie_ci(
        apercu, tarif_declare=TARIF_MT_DECLARE, investissement=INVESTISSEMENT,
        mode_installation=mode, reglages={'sensibilites_ci': scenarios})


def _retour_manuel(investissement, economie1, *, idx=0.0, deg=None):
    """Retour simple recalculé À LA MAIN : première année où le cumul
    (−investissement + Σ économies indexées et dégradées) devient ≥ 0."""
    deg = pricing.PANEL_DEGRADATION if deg is None else deg
    cumul = -investissement
    for annee in range(1, 26):
        cumul += economie1 * (1 + idx) ** (annee - 1) \
            * (1 - deg) ** (annee - 1)
        if cumul >= 0:
            return annee
    return None


_JOURS_MOIS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _serie_8760():
    """Année type horaire déterministe (kWh/kWc) : cloche 6-18 h GMT, saison,
    et un ciel qui change d'un jour à l'autre (comme la série PVGIS réelle)."""
    serie = []
    for jour in range(365):
        ciel = 0.3 + 0.7 * ((jour * 37) % 11) / 10.0
        saison = 1.0 + 0.25 * math.cos(2 * math.pi * (jour - 172) / 365.0)
        for h in range(24):
            cloche = max(0.0, math.sin(math.pi * (h - 6 + 0.5) / 12.0)) if 6 <= h < 18 else 0.0
            serie.append(round(0.9 * ciel * saison * cloche, 4))
    return serie


def _profil(ouvre, repos, jours_repos_par_semaine):
    """``profil_charge.jours_types`` : un jour ouvré + un jour de repos / mois."""
    jours = []
    for mois, n in enumerate(_JOURS_MOIS, start=1):
        repos_n = round(n * jours_repos_par_semaine / 7.0)
        jours.append({'mois': mois, 'type_jour': 'ouvre', 'nb_jours': n - repos_n,
                      'charge_kwh': list(ouvre)})
        jours.append({'mois': mois, 'type_jour': 'repos', 'nb_jours': repos_n,
                      'charge_kwh': list(repos)})
    return jours


def _apercu_profil(nom):
    """Trois profils réels du rejeu CEC6 : boulangerie BT, bureaux BT, usine MT —
    bilan central par LE moteur (``bilan_horaire`` sur la série 8 760 h)."""
    from apps.ventes.moteur_ci.autoconso import bilan_horaire
    from apps.ventes.moteur_ci.production import production_pour_bilan
    if nom == 'boulangerie':
        ouvre = [4.0 if 2 <= h < 10 else 2.0 if 10 <= h < 19 else 0.8 for h in range(24)]
        jours, kwc, tension = _profil(ouvre, [0.8] * 24, 1), 18.0, 'bt'
    elif nom == 'bureaux':
        ouvre = [12.0 if 7 <= h < 17 else 2.0 for h in range(24)]
        jours, kwc, tension = _profil(ouvre, [2.0] * 24, 2), 60.0, 'bt'
    else:
        ouvre = [120.0 if 5 <= h < 21 else 30.0 for h in range(24)]
        jours, kwc, tension = _profil(ouvre, [30.0] * 24, 1), 400.0, 'mt'
    production = {'serie_horaire': {'kwh_kwc': _serie_8760()}}
    bilan, _alertes = bilan_horaire(jours, production_pour_bilan(production), kwc,
                                    tension=tension)
    return {'entrees_resolues': {'tension': {'valeur': tension},
                                 'tva_recuperable': {'valeur': 'oui'}},
            'profil_charge': {'jours_types': jours}, 'production': production,
            'taille': {'retenue_kwc': kwc}, 'bilan': bilan, 'alertes': []}


SCENARIOS_P90 = [
    {'cle': 'production', 'variation_pct': -7.7, 'source': 'P90 (test)'},
    {'cle': 'tarif_kwh', 'variation_pct': -10, 'source': 'baisse (test)'},
    {'cle': 'tarif_kwh', 'variation_pct': 10, 'source': 'hausse (test)'},
    {'cle': 'production', 'variation_pct': 5, 'source': 'P10 (test)'}]


class SensibiliteMonotoneTest(SimpleTestCase):
    """ERR-CI-SENSIBILITE-P90-INVERSEE (CEC6 P1.4) — moins de production ou un
    tarif plus bas ne rapporte JAMAIS plus que le central (et l'inverse)."""

    def _bloc(self, nom):
        apercu = _apercu_profil(nom)
        declare = TARIF_MT_DECLARE if nom == 'usine' else {'contrat': 'bt_patente'}
        return eco.assembler_economie_ci(
            apercu, tarif_declare=declare, investissement=INVESTISSEMENT,
            mode_installation='industriel', reglages={'sensibilites_ci': SCENARIOS_P90})

    def test_trois_profils_monotones(self):
        for nom in ('boulangerie', 'bureaux', 'usine'):
            with self.subTest(profil=nom):
                bloc = self._bloc(nom)
                centre = (bloc['economie_annee1']['total_mad'],
                          bloc['flux_ht']['flux'][-1]['cumul_mad'],
                          bloc['indicateurs']['tri_pct'])
                for sc in bloc['sensibilites']:
                    self.assertNotIn('motif', sc)
                    valeurs = (sc['economie_annee1_mad'], sc['cumul_25_ans_mad'], sc['tri_pct'])
                    for v, c in zip(valeurs, centre):
                        if sc['variation_pct'] < 0:
                            self.assertLess(v, c, (nom, sc))
                        else:
                            self.assertGreater(v, c, (nom, sc))

    def test_production_meme_moteur_que_le_central(self):
        """À +0 % le scénario production retrouve EXACTEMENT le central."""
        apercu = _apercu_profil('usine')
        modifie, motif = eco._options.apercu_production_comparable(
            apercu, 1.0, eco._apercu_production, origine=False, motif_sans_charge='x')
        self.assertIsNone(motif)
        self.assertEqual(modifie['bilan']['horaire'], apercu['bilan']['horaire'])

    def test_bilan_non_reproductible_omis_avec_motif(self):
        apercu = _apercu_profil('usine')
        apercu['taille'] = {'retenue_kwc': 380.0}  # étude périmée : autre puissance
        modifie, motif = eco._options.apercu_production_comparable(
            apercu, 0.923, eco._apercu_production, origine=False, motif_sans_charge='x')
        self.assertIsNone(modifie)
        self.assertEqual(motif, eco._options.MOTIF_SENSIBILITE_NON_REPRODUCTIBLE)

    def test_regles_origine_gardent_le_calcul_envoye(self):
        """Fondateur 08/10 : un devis envoyé garde ce que le client a reçu."""
        apercu = _apercu_profil('usine')
        modifie, _motif = eco._options.apercu_production_comparable(
            apercu, 0.923, eco._apercu_production, origine=True, motif_sans_charge='x')
        self.assertEqual(modifie, eco._apercu_production(apercu, 0.923))


class SensibilitesTest(SimpleTestCase):
    def test_reglage_vide_liste_vide_et_motif(self):
        bloc = _bloc(_apercu_contrat(), [])
        self.assertEqual(bloc['sensibilites'], [])
        omis = {o['cle']: o['motif'] for o in bloc['omissions']}
        self.assertEqual(omis['sensibilites'], eco.MOTIF_SANS_SENSIBILITE)

    def test_tarif_plus_10_retour_recalcule(self):
        bloc = _bloc(_apercu_main(), [
            {'cle': 'tarif_kwh', 'variation_pct': 10,
             'source': 'hausse ONEE annoncée (test)'}])
        # Base à la main : 90 kWh/j × 30 j × 1,1 MAD (pleines) = 2 970 MAD.
        self.assertAlmostEqual(bloc['economie_annee1']['total_mad'], 2970.0)
        sc = bloc['sensibilites'][0]
        self.assertAlmostEqual(sc['economie_annee1_mad'], 2970.0 * 1.1,
                               places=1)
        self.assertEqual(sc['retour_ans'],
                         _retour_manuel(300000.0, 2970.0 * 1.1))
        self.assertEqual(sc['source'], 'hausse ONEE annoncée (test)')

    def test_indexation_plus_2_publiee_sans_refus(self):
        bloc = _bloc(_apercu_contrat(), [
            {'cle': 'indexation_tarif', 'variation_pct': 2,
             'source': 'historique ONEE publié (test)'}])
        sc = bloc['sensibilites'][0]
        self.assertEqual(sc['cle'], 'indexation_tarif')
        self.assertNotIn('motif', sc)
        self.assertIsNotNone(sc['tri_pct'])
        # La base reste à 0 % d'indexation (QX39).
        hyp = {h['cle']: h['valeur'] for h in bloc['flux_ht']['hypotheses']}
        self.assertEqual(hyp['indexation_pct'], 0.0)
        self.assertGreater(sc['tri_pct'], bloc['indicateurs']['tri_pct'])

    def test_quatre_scenarios_quatre_publies_en_plus_de_la_base(self):
        scenarios = [
            {'cle': 'indexation_tarif', 'variation_pct': 2, 'source': 's1'},
            {'cle': 'degradation', 'variation_pct': 1, 'source': 's2'},
            {'cle': 'tarif_kwh', 'variation_pct': -10, 'source': 's3'},
            {'cle': 'production', 'variation_pct': -10, 'source': 's4'}]
        bloc = _bloc(_apercu_contrat(), scenarios)
        self.assertEqual([s['cle'] for s in bloc['sensibilites']],
                         [s['cle'] for s in scenarios])
        self.assertIsNotNone(bloc['indicateurs']['retour_ans'])

    def test_production_moins_10_recalcul_horaire(self):
        bloc = _bloc(_apercu_main(), [
            {'cle': 'production', 'variation_pct': -10,
             'source': 'P90 saisi (test)'}])
        sc = bloc['sensibilites'][0]
        # À la main : 10 h → min(36, 100) = 36 ; 12 h → min(90, 50) = 50 ;
        # (36 + 50) × 30 j × 1,1 = 2 838 MAD, soit −4,4 % (< 10 %).
        self.assertAlmostEqual(sc['economie_annee1_mad'], 2838.0, places=2)
        baisse = 1 - sc['economie_annee1_mad'] / 2970.0
        self.assertLess(baisse, 0.10)
        self.assertGreater(baisse, 0.0)

    def test_commercial_sensibilites_calculees(self):
        """AMOT97 (D-ACI-15=a) — le commercial reçoit ses scénarios (son
        scénario prudent est imprimé), sur le même flux que l'industriel."""
        scenario = [{'cle': 'tarif_kwh', 'variation_pct': 10, 'source': 's'}]
        commercial = _bloc(_apercu_contrat(), scenario, mode='commercial')
        industriel = _bloc(_apercu_contrat(), scenario, mode='industriel')
        self.assertEqual(len(commercial['sensibilites']), 1)
        self.assertEqual(commercial['sensibilites'],
                         industriel['sensibilites'])
        self.assertIsNotNone(commercial['sensibilites'][0]['retour_ans'])
