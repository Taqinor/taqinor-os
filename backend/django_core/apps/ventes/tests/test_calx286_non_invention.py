"""CALX286 — plus aucun défaut financier non sourcé muet : omission motivée, PROUVÉE.

Deux preuves, conformément au « Done » de la tâche :

1. **Test de non-invention** (:class:`NonInventionTest`) — il importe
   ``apps.ventes.solar_design``, appelle CHAQUE fonction publique du module
   (énumérée par introspection : une fonction ajoutée demain est couverte
   d'office) avec ses seuls paramètres OBLIGATOIRES à des valeurs neutres
   (zéro, vide) et SANS aucun paramètre optionnel, puis affirme qu'aucune
   sortie numérique non nulle n'apparaît sans une entrée ``hypotheses``
   portant une ``source`` qui la gouverne (``couvre``). Avec des entrées
   neutres, un nombre non nul ne peut venir QUE d'un défaut du module : il
   doit donc être publié. Trois exemptions, écrites avec leur raison.

2. **Appelants inchangés** (:class:`AppelantsInchangesTest`) — les chemins de
   production qui s'appuyaient sur ces défauts (``apps/ventes/compatibilites
   .py`` pour les températures, ``apps/ventes/etude.py`` pour la dégradation,
   l'actualisation et l'arbre de pertes, ``apps/calepinage/services/
   batterie.py:86-106`` qui relit DoD et rendement, ``apps/ventes/
   quote_engine/`` via son cashflow) rendent des résultats TERME À TERME
   identiques à ceux capturés AVANT la tâche (:data:`AVANT`, capturé sur le
   commit CALX279 avec les mêmes appels).

Les quatre familles retirées : ``DEFAULT_TARIFF_ESCALATION`` /
``DEFAULT_MODULE_DEGRADATION`` / ``DEFAULT_DISCOUNT_RATE`` ;
``_BATTERY_DEFAULT_DOD`` / ``_ROUND_TRIP`` / ``_BACKUP_PEAK_FACTOR`` /
``_NIGHT_FRACTION`` ; ``DEFAULT_LOSS_FACTORS`` ; ``DEFAULT_COLD_TEMP_C`` /
``DEFAULT_HOT_TEMP_C`` (:class:`FamillesOmisesTest`).

Run :
    python manage.py test apps.ventes.tests.test_calx286_non_invention -v2
"""
import inspect
import json
import unittest

from django.test import SimpleTestCase

from apps.ventes import solar_design as sd

#: Valeurs NEUTRES des paramètres obligatoires (zéro, vide, rien).
NEUTRES = {
    'designation': '', 'text': '', 'produit': None, 'scenarios': [],
    'daily_irradiation_kwh_m2': 0, 'produits': [], 'n_panels': 0,
    'annual_production_kwh': 0, 'debit_hmt_m3h': 0,
    'base_production_kwh': 0, 'annual_savings_year1': 0,
    'hour_tranches': [],
}

#: Fonctions publiques NON appelées, chacune avec sa raison écrite.
EXEMPTIONS = {
    'load_curve_from_xlsx': "lit un fichier Excel fourni : aucun nombre "
                            "par défaut, rien à appeler à vide",
    'optimize_orientation': "interroge PVGIS (réseau) : hors d'un test pur",
    'generate_boq': "bordereau technique (quantités, aucun montant) dont la "
                    "forme est épinglée clé pour clé par "
                    "test_pv83_shims_electrique et core/tests/"
                    "test_electrique_nomenclature ; ses défauts restants "
                    "(phases=1, câble AC 15 m) sont hors des quatre familles "
                    "de CALX286 et signalés pour une tâche dédiée",
}

#: Nombres STRUCTURELS : indices et compteurs, jamais une hypothèse.
CLES_STRUCTURELLES = {'year', 'hours', 'heure', 'mois', 'periode',
                      'fin_mois', 'index', 'heures'}

#: Les paramètres des quatre familles : leur défaut DOIT être None.
PARAMETRES_DES_FAMILLES = {
    'escalation_rate', 'grid_escalation', 'degradation_rate',
    'annual_degradation_rate', 'discount_rate', 'depth_of_discharge',
    'round_trip_efficiency', 'backup_peak_factor', 'cold_temp_c',
    'hot_temp_c', 'loss_factors',
}


def _fonctions_publiques():
    return sorted(
        (nom, fn) for nom, fn in inspect.getmembers(sd, inspect.isfunction)
        if not nom.startswith('_') and fn.__module__ == sd.__name__)


def _feuilles_numeriques(objet, chemin=''):
    """(chemin pointé, valeur) de chaque nombre non nul, hors publications."""
    if isinstance(objet, bool):
        return
    if isinstance(objet, (int, float)):
        if objet != 0:
            yield chemin, objet
        return
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            if cle in ('hypotheses', 'omissions'):
                continue
            yield from _feuilles_numeriques(
                valeur, f'{chemin}.{cle}' if chemin else str(cle))
    elif isinstance(objet, (list, tuple)):
        for valeur in objet:
            yield from _feuilles_numeriques(valeur, chemin)


def _couvertures_sourcees(resultat):
    couvertures = []
    if isinstance(resultat, dict):
        for entree in resultat.get('hypotheses') or []:
            if str(entree.get('source') or '').strip():
                couvertures.extend(entree.get('couvre') or [entree['cle']])
    return couvertures


def _est_structurel(chemin, valeur):
    derniere = chemin.rsplit('.', 1)[-1]
    if derniere in CLES_STRUCTURELLES:
        return True
    # Un facteur multiplicatif neutre (× 1) ne porte aucune hypothèse.
    return 'factor' in derniere and valeur == 1.0


class NonInventionTest(unittest.TestCase):
    def test_aucune_sortie_non_nulle_sans_hypothese_sourcee(self):
        appelees = []
        for nom, fonction in _fonctions_publiques():
            if nom in EXEMPTIONS:
                continue
            obligatoires = {
                p.name: NEUTRES[p.name]
                for p in inspect.signature(fonction).parameters.values()
                if p.default is inspect.Parameter.empty
                and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)}
            resultat = fonction(**obligatoires)
            appelees.append(nom)
            couvertures = _couvertures_sourcees(resultat)
            for chemin, valeur in _feuilles_numeriques(resultat):
                if _est_structurel(chemin, valeur):
                    continue
                with self.subTest(fonction=nom, sortie=chemin):
                    self.assertTrue(
                        any(chemin == c or chemin.startswith(c + '.')
                            for c in couvertures),
                        f'{nom}() publie {chemin} = {valeur} sans hypothèse '
                        'sourcée qui le gouverne : un défaut muet')
            if isinstance(resultat, dict):
                for omission in resultat.get('omissions') or []:
                    self.assertTrue(str(omission.get('motif') or '').strip(),
                                    f'{nom}() : omission sans motif')
        # Toutes les fonctions publiques sont appelées ou exemptées.
        self.assertGreater(len(appelees), 20)

    def test_exemptions_designent_des_fonctions_existantes(self):
        noms = {nom for nom, _ in _fonctions_publiques()}
        self.assertLessEqual(set(EXEMPTIONS), noms)

    def test_aucun_parametre_des_familles_n_a_de_defaut_chiffre(self):
        for nom, fonction in _fonctions_publiques():
            for p in inspect.signature(fonction).parameters.values():
                if p.name in PARAMETRES_DES_FAMILLES:
                    with self.subTest(fonction=nom, parametre=p.name):
                        self.assertIsNone(
                            p.default,
                            f'{nom}({p.name}=…) : défaut chiffré implicite')


class FamillesOmisesTest(unittest.TestCase):
    def test_projection_sans_degradation_ni_actualisation(self):
        res = sd.tariff_escalation_projection(
            annual_savings_year1=12000, upfront_cost=80000)
        omis = {o['cle'] for o in res['omissions']}
        self.assertEqual(omis, {'degradation_rate', 'discount_rate'})
        self.assertIsNone(res['summary']['npv'])
        self.assertIsNone(res['summary']['total_savings'])
        self.assertIsNone(res['schedule'][1]['annual_savings'])
        # Jamais les 6 %/an d'avant.
        self.assertEqual(res['summary']['escalation_rate'], 0.0)

    def test_projection_sans_actualisation_garde_le_tri(self):
        res = sd.tariff_escalation_projection(
            annual_savings_year1=12000, upfront_cost=80000,
            degradation_rate=0.005)
        self.assertIsNone(res['summary']['npv'])
        self.assertIsNotNone(res['summary']['irr'])
        self.assertIsNone(res['schedule'][0]['discounted_savings'])

    def test_degradation_modules_omise(self):
        res = sd.module_degradation_curve(10000)
        self.assertIsNone(res['schedule'][0]['production_factor'])
        self.assertIsNone(res['summary']['total_production_kwh'])
        self.assertIn('annual_degradation_rate',
                      {o['cle'] for o in res['omissions']})

    def test_batterie_dod_rendement_nuit_et_pointe_omis(self):
        res = sd.battery_storage_sizing(
            mode='both', daily_surplus_kwh=10.0, critical_load_kw=2.0,
            backup_hours=4.0)
        omis = {o['cle'] for o in res['omissions']}
        self.assertLessEqual({'depth_of_discharge', 'round_trip_efficiency',
                              'night_load_kwh', 'backup_peak_factor'}, omis)
        self.assertIsNone(res['autoconso']['usable_kwh'])
        self.assertIsNone(res['backup']['usable_kw'])
        self.assertIsNone(res['backup']['nominal_kwh'])
        self.assertIsNone(res['recommended']['nominal_kwh'])

    def test_arbre_de_pertes_omis(self):
        res = sd.simulate_bankable_yield(10000)
        self.assertIsNone(res['performance_ratio'])
        self.assertIsNone(res['p50_kwh'])
        self.assertIsNone(res['p90_kwh'])
        self.assertEqual(res['loss_breakdown'], {})

    def test_temperatures_de_dimensionnement_omises(self):
        design = sd.string_design(12)
        verdicts = sd.verdicts_chaines(12)
        choix = sd.match_inverter([], n_panels=12)
        for res in (design, verdicts, choix):
            omis = {o['cle'] for o in res['omissions']}
            self.assertEqual(omis, {'cold_temp_c', 'hot_temp_c'})
        self.assertIsNone(design['voltages'])
        self.assertIsNone(design['ok'])
        self.assertIsNone(verdicts['bloquants'])
        self.assertIsNone(choix['compatible'])

    def test_ppa_sans_degradation_non_calcule(self):
        res = sd.ppa_model(annual_production_kwh=20000, ppa_tariff=0.9,
                           grid_tariff=1.4)
        self.assertIsNone(res['investor'])
        self.assertIn('degradation_rate', res['motif'])


#: Sorties capturées AVANT CALX286 (commit CALX279), mêmes appels.
AVANT = json.loads(r'''{
 "bankable": {
  "annual_variability": 0.06,
  "applied_losses": [
   "availability",
   "inverter",
   "mismatch",
   "shading",
   "soiling",
   "temperature",
   "wiring"
  ],
  "base_production_kwh": 10000.0,
  "loss_breakdown": {
   "availability": {
    "fraction": 0.0118,
    "pct": 1.18
   },
   "inverter": {
    "fraction": 0.0294,
    "pct": 2.94
   },
   "mismatch": {
    "fraction": 0.0235,
    "pct": 2.35
   },
   "shading": {
    "fraction": 0.05,
    "pct": 5.0
   },
   "soiling": {
    "fraction": 0.0352,
    "pct": 3.52
   },
   "temperature": {
    "fraction": 0.0935,
    "pct": 9.35
   },
   "wiring": {
    "fraction": 0.0235,
    "pct": 2.35
   }
  },
  "p50_kwh": 7600.0,
  "p75_kwh": 7292.7,
  "p90_kwh": 7015.4,
  "performance_ratio": 0.76,
  "specific_yield_kwh_kwc": 1266.7,
  "total_loss_pct": 24.0,
  "warnings": [],
  "z_p75": 0.674,
  "z_p90": 1.282
 },
 "cashflow": {
  "cashflow": [
   12000,
   11940,
   11880,
   11821,
   11762,
   11703,
   11644,
   11586,
   11528,
   11471,
   11413,
   11356,
   11299,
   11243,
   11187,
   11131,
   11075,
   11020,
   10965,
   10910,
   10855,
   10801,
   10747,
   10693,
   10640
  ],
  "cumulative": [
   -68000,
   -56060,
   -44180,
   -32359,
   -20597,
   -8894,
   2750,
   14337,
   25865,
   37336,
   48749,
   60105,
   71405,
   82648,
   93834,
   104965,
   116040,
   127060,
   138025,
   148935,
   159790,
   170591,
   181338,
   192032,
   202671
  ],
  "net_gain": 202671,
  "payback_years": 6.8,
  "years": 25
 },
 "degradation": {
  "schedule": [
   {
    "production_factor": 0.98,
    "production_kwh": 9800.0,
    "warranty_breach": false,
    "warranty_floor": null,
    "year": 1
   },
   {
    "production_factor": 0.9751,
    "production_kwh": 9751.0,
    "warranty_breach": false,
    "warranty_floor": null,
    "year": 2
   },
   {
    "production_factor": 0.970225,
    "production_kwh": 9702.25,
    "warranty_breach": false,
    "warranty_floor": null,
    "year": 3
   },
   {
    "production_factor": 0.965373,
    "production_kwh": 9653.73,
    "warranty_breach": false,
    "warranty_floor": null,
    "year": 4
   },
   {
    "production_factor": 0.960547,
    "production_kwh": 9605.47,
    "warranty_breach": false,
    "warranty_floor": null,
    "year": 5
   }
  ],
  "summary": {
   "annual_degradation_rate": 0.005,
   "any_warranty_breach": false,
   "curve": "compound",
   "factor_last_year": 0.960547,
   "factor_year1": 0.98,
   "first_breach_year": null,
   "horizon_years": 5,
   "total_production_kwh": 48512.45,
   "year1_degradation": 0.02
  },
  "warnings": [],
  "warranty_checks": [
   {
    "factor": 0.936772,
    "first_breach_year": null,
    "floor": 0.9,
    "ok": true,
    "shortfall_pct": 0.0,
    "year": 10
   },
   {
    "factor": 0.86892,
    "first_breach_year": null,
    "floor": 0.8,
    "ok": true,
    "shortfall_pct": 0.0,
    "year": 25
   }
  ]
 },
 "hypotheses_batterie": {
  "dod_pct": [
   90.0,
   "Hypothèse de référence du dépôt (apps/ventes/solar_design.py) — la fiche ne publie pas de profondeur de décharge."
  ],
  "rendement_ar_pct": [
   90.0,
   "Hypothèse de référence du dépôt (apps/ventes/solar_design.py) — la fiche ne publie pas de rendement aller-retour."
  ]
 },
 "projection": {
  "hypotheses": [
   {
    "cle": "escalation_rate",
    "source": "aucune indexation saisie — projection à tarif constant (décision fondateur QRES54, quote_engine/pricing.py TARIFF_ESCALATION)",
    "valeur": 0.0
   }
  ],
  "schedule": [
   {
    "annual_savings": 12000.0,
    "cumulative_savings": 12000.0,
    "degradation_factor": 1.0,
    "discounted_savings": 11428.57,
    "escalated_tariff_factor": 1.0,
    "net_cumulative": -68000.0,
    "projected_bill": null,
    "year": 1
   },
   {
    "annual_savings": 11940.0,
    "cumulative_savings": 23940.0,
    "degradation_factor": 0.995,
    "discounted_savings": 10829.93,
    "escalated_tariff_factor": 1.0,
    "net_cumulative": -56060.0,
    "projected_bill": null,
    "year": 2
   },
   {
    "annual_savings": 11880.3,
    "cumulative_savings": 35820.3,
    "degradation_factor": 0.990025,
    "discounted_savings": 10262.65,
    "escalated_tariff_factor": 1.0,
    "net_cumulative": -44179.7,
    "projected_bill": null,
    "year": 3
   },
   {
    "annual_savings": 11820.9,
    "cumulative_savings": 47641.2,
    "degradation_factor": 0.985075,
    "discounted_savings": 9725.08,
    "escalated_tariff_factor": 1.0,
    "net_cumulative": -32358.8,
    "projected_bill": null,
    "year": 4
   },
   {
    "annual_savings": 11761.79,
    "cumulative_savings": 59402.99,
    "degradation_factor": 0.98015,
    "discounted_savings": 9215.67,
    "escalated_tariff_factor": 1.0,
    "net_cumulative": -20597.01,
    "projected_bill": null,
    "year": 5
   }
  ],
  "summary": {
   "degradation_rate": 0.005,
   "discount_rate": 0.05,
   "discounted_payback_year": null,
   "escalation_rate": 0.0,
   "horizon_years": 5,
   "indexation_mention": "aucune indexation saisie",
   "irr": -0.091948,
   "net_total": -20597.01,
   "npv": -28538.09,
   "payback_year": null,
   "savings_last_year": 11761.79,
   "savings_year1": 12000.0,
   "total_discounted_savings": 51461.91,
   "total_savings": 59402.99,
   "upfront_cost": 80000.0
  },
  "warnings": [
   "retour sur investissement non atteint sur l'horizon — l'économie cumulée ne couvre pas le coût initial"
  ]
 },
 "string_design": {
  "ac_kw": 10.0,
  "checks": {
   "vmp_cold_under_mppt_max": true,
   "vmp_hot_over_mppt_min": true,
   "vmp_hot_over_vmin": true,
   "voc_cold_under_vmax": true
  },
  "dc_ac_ratio": 1.32,
  "dc_kw": 13.2,
  "n_mppt": 2,
  "n_panels": 24,
  "ok": true,
  "panels_per_string": 12,
  "string_layout": [
   1,
   1
  ],
  "strings": 2,
  "voltages": {
   "cold_temp_c": -5.0,
   "hot_temp_c": 70.0,
   "vmp_cold": 450.8,
   "vmp_hot": 343.7,
   "vmp_stc": 408.0,
   "voc_cold": 531.9
  },
  "warnings": []
 },
 "verdicts_chaines": {
  "alertes": [],
  "alertes_courant": [],
  "bloquants": [],
  "fenetre_trop_etroite": false,
  "homogene": true,
  "longueur_chaine": 12,
  "nb_chaines": 2
 }
}''')

MODULE = {'vmp': 34, 'voc': 41, 'puissance_w': 550, 'temp_coeff_voc': -0.27,
          'temp_coeff_vmp': -0.35}
ONDULEUR = {'v_min': 90, 'v_max': 1000, 'v_mppt_min': 120, 'v_mppt_max': 850,
            'n_mppt': 2, 'ac_kw': 10}


class AppelantsInchangesTest(SimpleTestCase):
    """Les chemins de production rendent EXACTEMENT les chiffres d'avant."""

    def test_compatibilites_temperatures_explicites(self):
        # ``apps/ventes/compatibilites.py`` passe désormais −5 / 70 °C.
        from apps.ventes import compatibilites
        temperatures = compatibilites._TEMPERATURES_DIMENSIONNEMENT
        self.assertEqual(
            sd.string_design(24, module=MODULE, inverter=ONDULEUR,
                             **temperatures),
            AVANT['string_design'])
        self.assertEqual(
            sd.verdicts_chaines(24, module=MODULE, inverter=ONDULEUR,
                                **temperatures),
            AVANT['verdicts_chaines'])

    def test_etude_projection_et_degradation(self):
        # ``apps/ventes/etude.py`` passe dégradation et actualisation.
        res = sd.tariff_escalation_projection(
            annual_savings_year1=12000.0, upfront_cost=80000.0,
            horizon_years=5, degradation_rate=sd.DEFAULT_MODULE_DEGRADATION,
            discount_rate=sd.DEFAULT_DISCOUNT_RATE)
        for cle in ('schedule', 'summary', 'warnings'):
            self.assertEqual(res[cle], AVANT['projection'][cle], cle)
        deg = sd.module_degradation_curve(
            production_year1=10000.0, horizon_years=5,
            annual_degradation_rate=sd.DEFAULT_MODULE_DEGRADATION)
        for cle in ('schedule', 'warranty_checks', 'summary', 'warnings'):
            self.assertEqual(deg[cle], AVANT['degradation'][cle], cle)

    def test_etude_arbre_de_pertes_cale(self):
        from apps.ventes.etude import loss_factors_canoniques
        res = sd.simulate_bankable_yield(
            10000.0, loss_factors=loss_factors_canoniques(0.05), kwc=6.0)
        for cle, valeur in AVANT['bankable'].items():
            self.assertEqual(res[cle], valeur, cle)

    def test_calepinage_hypotheses_de_reference_batterie(self):
        from apps.calepinage.services import batterie
        attendu = {cle: tuple(v) for cle, v in
                   AVANT['hypotheses_batterie'].items()}
        self.assertEqual(batterie._hypotheses_de_reference(), attendu)

    def test_moteur_de_devis_cashflow(self):
        from apps.ventes.quote_engine import pricing
        self.assertEqual(
            pricing.compute_cashflow_payback(80000.0, 12000.0,
                                             inverter_replace_cost=None),
            AVANT['cashflow'])
