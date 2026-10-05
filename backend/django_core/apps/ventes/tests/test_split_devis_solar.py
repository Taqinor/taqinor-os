"""SPL243 — golden de la découpe de ``solar_design.py`` (SPL259-SPL261).

``solar_design.py`` (≈4900 lignes, propriétaire moteur) est découpé en trois
régions déplacées vers trois modules frères de ``apps/ventes/`` :
``solar_base.py`` (helpers d'hypothèse/omission/série), ``solar_finance.py``
(tarifs TOU, net metering, compensation, projection, VAN/TRI, dégradation,
PPA) et ``solar_classification.py`` (prédicats de classification produit).
Ce module porte la preuve « move only » de chaque déplacement, capturée sur
le code d'AVANT :

(a) ``golden/split_sd_<region>.json`` — empreinte AST normalisée
    (``split_golden.empreintes`` : ``ImportFrom.level`` ramené à 0) de chaque
    symbole de la région ;
(b) ``DEPLACEMENTS`` — une entrée par région. Tant que son SPL n'a pas atterri
    (``actif=False``), le golden doit rester IDENTIQUE à la source actuelle
    (une tâche étrangère qui édite un symbole avant son déplacement rougit
    ici : recapturer avant de déplacer). Le SPL de la région passe ``actif`` à
    ``True`` dans le MÊME commit que le déplacement ;
(c) ``golden/split_sd_comportement.json`` — digests de COMPORTEMENT des
    vraies fonctions (jamais mockées) : ``hypotheses`` + ``omissions`` de
    ``string_design``, ``battery_storage_sizing``, ``simulate_bankable_yield``
    et ``tariff_escalation_projection`` avec leurs défauts, ``net_metering_savings``
    (tranches TOU par saison, avec/sans tarifs), ``compensation_surplus`` (les
    trois mécanismes), ``tariff_escalation_projection`` (indexation saisie /
    non saisie, horizons 20/25), ``module_degradation_curve``, ``ppa_model``
    (tarif saisi/absent), les helpers de base et TOUS les prédicats de
    classification sur une table de désignations ;
(d) ``golden/split_sd_rendu_html.json`` — empreinte sha256 du HTML RENDU (pas
    du PDF binaire) par le moteur premium sur les fixtures PURES qx45
    (industriel), qx46 (commercial, toutes catégories) et résidentielle
    (précédent QJR651 / ``test_premium_base_harnais.py`` : ``build_html`` des
    ``sample_data``, aucune BD). Règle #4 : on MESURE le rendu, on ne le
    change pas.

Capture des goldens (une fois, sur le code d'avant découpe — identiques
après, puisque (a) prouve la copie fidèle) :
    SPLIT_GOLDEN_CAPTURE=1 python manage.py test \\
        apps.ventes.tests.test_split_devis_solar

Lancer (aucune BD : SimpleTestCase seulement) :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_split_devis_solar -v 2
"""
import hashlib
import importlib
import os

from django.test import SimpleTestCase

from apps.ventes.tests import split_golden as sg

SOURCE = 'apps/ventes/solar_design.py'

#: Une entrée par région : (golden, module cible, SPL qui la déplace, actif).
DEPLACEMENTS = {
    'base': ('split_sd_base', 'apps/ventes/solar_base.py', 'SPL259', True),
    'finance': ('split_sd_finance', 'apps/ventes/solar_finance.py', 'SPL260',
                True),
    'classif': ('split_sd_classif', 'apps/ventes/solar_classification.py',
                'SPL261', True),
}

#: Symboles de niveau module de chaque région (lus par la capture).
REGIONS = {
    'base': (
        '_source_defaut', '_hypothese', '_omission', '_taux_ou_none',
        '_omissions_temperatures', '_coerce_series',
    ),
    'finance': (
        'DEFAULT_HOUR_TRANCHES', 'MOTIF_TARIFS_TOU_ABSENTS', '_TRANCHE_ORDER',
        '_JOURS_PAR_MOIS', '_libelle_heure', 'tranches_du_mois',
        '_mois_de_l_heure', 'net_metering_savings', '_serie_mensuelle',
        'compensation_surplus', 'DEFAULT_TARIFF_ESCALATION',
        'MENTION_INDEXATION_NON_SAISIE', 'DEFAULT_MODULE_DEGRADATION',
        'DEFAULT_DISCOUNT_RATE', 'DEFAULT_HORIZON_YEARS', '_MIN_HORIZON_YEARS',
        '_MAX_HORIZON_YEARS', '_npv', '_irr', 'tariff_escalation_projection',
        'DEFAULT_WARRANTY_FLOORS', 'DEFAULT_YEAR1_DEGRADATION',
        'module_degradation_curve', 'MOTIF_TARIF_PPA_ABSENT',
        'DEFAULT_PPA_ESCALATION', 'DEFAULT_OM_ESCALATION',
        'DEFAULT_PPA_TERM_YEARS', 'ppa_model',
    ),
    'classif': (
        '_WATT_RE', '_KW_RE', '_KWH_RE', 'parse_watt', 'parse_kw',
        '_PANEL_MODULE_QUALIFIERS', '_PANEL_BRANDS',
        '_autre_famille_que_panneau', 'is_panel', 'is_battery',
        'OFFGRID_KEYWORDS', '_a_mot_cle_offgrid',
        'OFFGRID_AUTRE_FAMILLE_KEYWORDS', 'is_hybrid_inverter',
        'is_offgrid_inverter', 'is_reseau_inverter', 'is_any_inverter',
        'is_inverter', 'is_smart_meter', '_WIFI_RE', 'is_wifi_dongle',
    ),
}

#: Modules où vit chaque nom, avant ou après la découpe.
_MODULES = (
    'apps.ventes.solar_design', 'apps.ventes.solar_base',
    'apps.ventes.solar_finance', 'apps.ventes.solar_classification',
)

_CAPTURE = os.environ.get('SPLIT_GOLDEN_CAPTURE') == '1'


class DeplacementsSolarTests(SimpleTestCase):
    """(a)+(b) — identité AST de chaque région, rouge d'abord."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if _CAPTURE:
            for region, (golden, _cible, _spl, actif) in DEPLACEMENTS.items():
                if not actif:
                    sg.ecrire_golden(
                        golden, sg.empreintes(SOURCE, REGIONS[region]))

    def test_trois_regions_disjointes_et_non_vides(self):
        vus = {}
        for region, (golden, _cible, _spl, _actif) in DEPLACEMENTS.items():
            symboles = sg.charger_golden(golden)
            self.assertTrue(symboles, f'golden {golden} vide')
            self.assertEqual(sorted(symboles), sorted(REGIONS[region]))
            for nom in symboles:
                self.assertNotIn(nom, vus, f'{nom} dans {region} et {vus.get(nom)}')
                vus[nom] = region
        self.assertEqual(len(vus), sum(len(s) for s in REGIONS.values()))

    def test_regions_en_attente_identiques_a_la_source(self):
        for region, (golden, _cible, spl, actif) in DEPLACEMENTS.items():
            if actif:
                continue
            with self.subTest(region=region, spl=spl):
                attendu = sg.charger_golden(golden)
                self.assertEqual(
                    sg.empreintes(SOURCE, sorted(attendu)), attendu,
                    f'{region} : symbole édité depuis la capture — recapturer '
                    f'le golden AVANT {spl}')

    def test_regions_deplacees_fideles(self):
        for region, (golden, cible, spl, actif) in DEPLACEMENTS.items():
            if not actif:
                continue
            with self.subTest(region=region, spl=spl):
                sg.verifier_deplacement(golden, cible, SOURCE)


def _f(nom):
    """Le VRAI objet ``nom``, où qu'il vive (avant ou après découpe)."""
    for chemin in _MODULES:
        try:
            module = importlib.import_module(chemin)
        except ImportError:
            continue
        if nom in vars(module):
            return vars(module)[nom]
    raise AssertionError(f'{nom} introuvable dans {_MODULES}')


def _sur(appel):
    """Résultat OU type d'exception : une levée fait partie du comportement."""
    try:
        return appel()
    except Exception as exc:  # noqa: BLE001 — caractérisation
        return f'<{type(exc).__name__}>'


def _hyp_omis(resultat):
    """``hypotheses`` + ``omissions`` d'un résultat (dict), sinon le résultat."""
    if not isinstance(resultat, dict):
        return resultat
    return {'hypotheses': resultat.get('hypotheses'),
            'omissions': resultat.get('omissions')}


#: Grilles TOU des tests CALX275 (annuel + été).
ANNUEL = ['creuse'] * 8 + ['pleine'] * 10 + ['pointe'] * 4 + ['pleine'] * 2
ETE = ['creuse'] * 8 + ['pleine'] * 11 + ['pointe'] * 4 + ['pleine']
TARIFS = {'pointe': 2.0, 'pleine': 1.0, 'creuse': 0.5}

#: Table de désignations pour les prédicats de classification.
DESIGNATIONS = (
    '', 'Panneau solaire 450 Wc', 'Panneaux monocristallins 550W',
    'Module PV 550 W', 'Module photovoltaïque Jinko 575 Wc',
    'Jinko Tiger Neo 580W', 'Moduleur de tension', 'Module de communication',
    'Onduleur hybride Deye 6 kW', 'Onduleur réseau Huawei 10 kVA',
    'Onduleur reseau injection 5kW', 'Onduleur hors réseau 5 kW',
    'Onduleur Hybride Off-Grid 8kW', 'Deye off-Grid 6kw', 'Deye off grid 6kw',
    'Kit solaire off-grid', 'Batterie off-grid 5kWh', 'Batterie lithium 5 kWh',
    'Batterie LiFePO4 10,24 kWh', 'Smart Meter DTSU666',
    'Passerelle Wi-Fi Deye', 'Dongle WIFI', 'Clé wifi Huawei',
    'Câble solaire 6 mm²', 'Structure aluminium', 'Pompe immergée 3 CV',
    'Onduleur autonome 3kVA', 'Onduleur 3,6 kW', 'Variateur 7,5 kW',
)

PREDICATS = (
    'is_battery', 'is_hybrid_inverter', 'is_offgrid_inverter',
    'is_reseau_inverter', 'is_any_inverter', 'is_inverter', 'is_smart_meter',
    'is_wifi_dongle', '_a_mot_cle_offgrid', '_autre_famille_que_panneau',
    'parse_watt', 'parse_kw',
)


class ComportementSolarTests(SimpleTestCase):
    """(c) — digests de comportement, identiques avant/après la découpe."""

    def _base(self):
        res = {}
        res['source_defaut'] = [_f('_source_defaut')(n)
                                for n in ('DEFAULT_MODULE', 'X')]
        res['hypothese'] = [_f('_hypothese')('k', 1.5, 'src'),
                            _f('_hypothese')('k', 2, 'src', ['a', 'b'])]
        res['omission'] = [_f('_omission')('k', 'motif'),
                           _f('_omission')('k', 'motif', ('a',))]
        res['taux_ou_none'] = [
            _f('_taux_ou_none')(v)
            for v in (None, True, '3.5', 'abc', 7, float('nan'), '0')]
        res['omissions_temperatures'] = [
            _f('_omissions_temperatures')(c, h, ['x'])
            for c, h in ((None, None), (-5, None), (None, 70), (-5, 70))]
        coerce = _f('_coerce_series')
        res['coerce_series'] = [
            _sur(lambda v=v: coerce(v))
            for v in (None, [], [1, 2, 3], ['1', 'x', -2], list(range(24)),
                      (0.5,) * 288)]
        return res

    def _finance(self):
        res = {}
        tranches = _f('tranches_du_mois')
        res['tranches_du_mois'] = [
            _sur(lambda g=g, m=m: tranches(g, m))
            for g in (ANNUEL, {'annuel': ANNUEL, 'ete': ETE}, {'ete': ETE},
                      None)
            for m in (None, 3, 8)]
        res['libelle_heure'] = [_f('_libelle_heure')(h) for h in (0, 9, 23)]
        mois = _f('_mois_de_l_heure')
        res['mois_de_l_heure'] = [
            _sur(lambda i=i, n=n: mois(i, n))
            for n in (24, 288, 8760, 8784, 100) for i in (0, 60, 200, 1500)
        ] + [mois(1, 24, [3, 13]), mois(0, 24, [7]), mois(5, 24, ['x'])]

        inj = [0.0] * 288
        imp = [0.0] * 288
        for i in range(0, 288, 7):
            inj[i] = 4.0
        for i in range(3, 288, 5):
            imp[i] = 3.0
        nm = _f('net_metering_savings')
        res['net_metering'] = [
            _sur(lambda: nm(injected_curve=inj, import_curve=imp,
                            days_per_year=1,
                            hour_tranches={'annuel': ANNUEL, 'ete': ETE},
                            tranche_tariffs=TARIFS)),
            _sur(lambda: nm(injected_curve=inj, import_curve=imp,
                            days_per_year=1, hour_tranches={'ete': ETE},
                            tranche_tariffs=TARIFS)),
            _sur(lambda: nm(injected_curve=inj, import_curve=imp,
                            days_per_year=1,
                            hour_tranches={'annuel': ANNUEL, 'ete': ETE})),
            _sur(lambda: nm(injected_curve=inj[:24], import_curve=imp[:24],
                            hour_tranches=ANNUEL, tranche_tariffs=TARIFS,
                            annual_cap_kwh=50, compensation_ratio=0.8,
                            spill_tariff=0.3)),
            _sur(lambda: nm(injected_curve=inj[:24], import_curve=imp[:24],
                            tranche_tariffs=TARIFS,
                            surplus_injecte_compense=False)),
            _sur(lambda: nm()),
        ]

        comp = _f('compensation_surplus')
        injection = [100, 120, 150, 180, 200, 220, 230, 220, 180, 150, 110, 90]
        soutirage = [150, 130, 110, 90, 80, 70, 60, 70, 90, 110, 140, 160]
        production = [300] * 12
        res['compensation'] = [
            _sur(lambda m=m, r=r: comp(
                mecanisme=m, injection_kwh_mois=injection,
                import_kwh_mois=soutirage, production_kwh_mois=production,
                tarif_rachat_mad_kwh=r, tarif_import_mad_kwh=1.2,
                report_periode=12, plafond_annuel_kwh=1500,
                ratio_compensation=0.9))
            for m in (None, 'injection_totale', 'surplus',
                      'net_metering_report', 'inconnu')
            for r in (None, 0.45)]
        res['compensation_report_2'] = _sur(lambda: comp(
            mecanisme='net_metering_report',
            injection_kwh_mois=[100, 0, 0, 0], import_kwh_mois=[0, 0, 30, 0],
            report_periode=2, tarif_import_mad_kwh=1.0))

        proj = _f('tariff_escalation_projection')
        res['projection'] = [
            _sur(lambda e=e, h=h: proj(
                annual_savings_year1=12000.0, upfront_cost=80000.0,
                escalation_rate=e, horizon_years=h))
            for e in (None, 0.03) for h in (None, 20, 25)]
        res['projection_complete'] = _sur(lambda: proj(
            annual_savings_year1=12000.0, upfront_cost=80000.0,
            escalation_rate=0.02, degradation_rate=0.005, horizon_years=25,
            discount_rate=0.06, baseline_bill_year1=20000.0))
        res['projection_bornes'] = [
            _sur(lambda h=h: proj(annual_savings_year1=1000.0,
                                  upfront_cost=0.0, horizon_years=h))
            for h in (0, 1, 60, 'x')]
        res['npv'] = [_f('_npv')(0.06, [-1000, 300, 300, 300, 300]),
                      _f('_npv')(0.0, [])]
        res['irr'] = [_sur(lambda c=c: _f('_irr')(c))
                      for c in ([-1000, 300, 300, 300, 300], [100, 100], [])]
        res['constantes'] = [
            _f(n) for n in (
                'DEFAULT_HOUR_TRANCHES', 'MOTIF_TARIFS_TOU_ABSENTS',
                '_TRANCHE_ORDER', '_JOURS_PAR_MOIS',
                'DEFAULT_TARIFF_ESCALATION', 'MENTION_INDEXATION_NON_SAISIE',
                'DEFAULT_MODULE_DEGRADATION', 'DEFAULT_DISCOUNT_RATE',
                'DEFAULT_HORIZON_YEARS', '_MIN_HORIZON_YEARS',
                '_MAX_HORIZON_YEARS', 'DEFAULT_WARRANTY_FLOORS',
                'DEFAULT_YEAR1_DEGRADATION', 'MOTIF_TARIF_PPA_ABSENT',
                'DEFAULT_PPA_ESCALATION', 'DEFAULT_OM_ESCALATION',
                'DEFAULT_PPA_TERM_YEARS')]

        deg = _f('module_degradation_curve')
        res['degradation'] = [
            _sur(lambda: deg()),
            _sur(lambda: deg(10000.0)),
            _sur(lambda: deg(10000.0, horizon_years=25)),
            _sur(lambda: deg(10000.0, annual_degradation_rate=0.004,
                             year1_degradation=0.01, horizon_years=30,
                             curve='linear')),
            _sur(lambda: deg(10000.0, warranty_floors={10: 0.9, 25: 0.8})),
        ]

        ppa = _f('ppa_model')
        res['ppa'] = [
            _sur(lambda t=t: ppa(annual_production_kwh=150000.0,
                                 ppa_tariff=t, grid_tariff=1.3))
            for t in (None, 0.9)]
        res['ppa_complet'] = _sur(lambda: ppa(
            annual_production_kwh=150000.0, ppa_tariff=0.9, grid_tariff=1.3,
            ppa_escalation=0.02, grid_escalation=0.03, term_years=15,
            capex=900000.0, annual_om=15000.0, om_escalation=0.02,
            degradation_rate=0.005, year1_degradation=0.02,
            discount_rate=0.07))
        return res

    def _calculateurs(self):
        res = {}
        sd = _f('string_design')
        res['string_design'] = [
            _sur(lambda: sd(20)),
            _sur(lambda: sd(20, cold_temp_c=-5.0, hot_temp_c=70.0)),
            _sur(lambda: sd(14, module={'vmp': 41.0, 'voc': 49.5},
                            inverter={'v_max': 1000.0, 'n_mppt': 2,
                                      'v_mppt_min': 200.0,
                                      'v_mppt_max': 850.0, 'ac_kw': 6.0},
                            cold_temp_c=-5.0)),
            _sur(lambda: sd(0)),
        ]
        bat = _f('battery_storage_sizing')
        res['battery'] = [
            _sur(lambda: bat()),
            _sur(lambda: bat(mode='autoconso', pv_daily_production_kwh=30.0,
                             pv_self_consumption_kwh=18.0,
                             night_load_kwh=8.0)),
            _sur(lambda: bat(mode='backup', critical_load_kw=2.0,
                             backup_hours=4.0)),
            _sur(lambda: bat(mode='both', pv_kwc=6.0,
                             productible_kwh_kwc_year=1650.0,
                             night_load_kwh=8.0, critical_load_kw=2.0,
                             backup_hours=4.0, evening_peak_kw=3.0,
                             depth_of_discharge=0.9,
                             round_trip_efficiency=0.92,
                             system_voltage_v=48.0)),
            _sur(lambda: bat(mode='inconnu')),
        ]
        yld = _f('simulate_bankable_yield')
        res['yield'] = [
            _sur(lambda: yld(10000.0)),
            _sur(lambda: yld(10000.0, kwc=6.0, include_p75=False)),
            _sur(lambda: yld(10000.0, loss_factors={'soiling': 0.03},
                             annual_variability=0.05)),
        ]
        proj = _f('tariff_escalation_projection')
        res['projection_defauts'] = _sur(lambda: proj(
            annual_savings_year1=12000.0))
        res['hypotheses_omissions'] = {
            nom: [_hyp_omis(r) for r in (res[nom] if isinstance(res[nom], list)
                                         else [res[nom]])]
            for nom in ('string_design', 'battery', 'yield',
                        'projection_defauts')}
        return res

    def _classification(self):
        res = {}
        for nom in PREDICATS:
            fonction = _f(nom)
            res[nom] = [_sur(lambda d=d: fonction(d)) for d in DESIGNATIONS]
        is_panel = _f('is_panel')
        res['is_panel'] = [_sur(lambda d=d: is_panel(d)) for d in DESIGNATIONS]
        res['is_panel_nom'] = [
            _sur(lambda d=d, n=n: is_panel(d, n))
            for d, n in (('', 'Panneau 450 Wc'), ('Ligne 1', 'Jinko 575W'),
                         ('Panneau 450 Wc', 'Onduleur hybride'),
                         ('Ligne', ''))]
        res['tables'] = [
            list(_f(n)) for n in (
                '_PANEL_MODULE_QUALIFIERS', '_PANEL_BRANDS',
                'OFFGRID_KEYWORDS', 'OFFGRID_AUTRE_FAMILLE_KEYWORDS')]
        res['regex'] = [_f(n).pattern for n in (
            '_WATT_RE', '_KW_RE', '_KWH_RE', '_WIFI_RE')]
        return res

    def _scenarios(self):
        res = {}
        for prefixe, bloc in (('base', self._base()),
                              ('finance', self._finance()),
                              ('calc', self._calculateurs()),
                              ('classif', self._classification())):
            for nom, valeur in bloc.items():
                res[f'{prefixe}.{nom}'] = valeur
        return res

    def test_digests_identiques(self):
        digests = {nom: sg.digest(val) for nom, val in self._scenarios().items()}
        if _CAPTURE:
            sg.ecrire_golden('split_sd_comportement', {'comportement': digests})
        attendu = sg.charger_golden('split_sd_comportement').get('comportement')
        self.assertTrue(
            attendu, 'golden de comportement non capturé : lancer une fois '
            'SPLIT_GOLDEN_CAPTURE=1 sur ce module (voir la docstring)')
        self.assertEqual(digests, attendu)


def _sha(texte):
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()


class RenduHtmlSolarTests(SimpleTestCase):
    """(d) — empreinte du HTML RENDU, identique avant/après (règle #4)."""

    def _rendus(self):
        from apps.ventes.quote_engine.commercial import categories
        from apps.ventes.quote_engine.commercial import render as c_render
        from apps.ventes.quote_engine.commercial import renderer as c_renderer
        from apps.ventes.quote_engine.commercial import sample_data as c_sample
        from apps.ventes.quote_engine.industriel import render as i_render
        from apps.ventes.quote_engine.industriel import renderer as i_renderer
        from apps.ventes.quote_engine.industriel import sample_data as i_sample
        from apps.ventes.tests import _moteur_fixtures as mf

        rendus = {
            'industriel_qx45': _sha(i_render.build_html(
                i_renderer._augment(i_sample.build()))),
        }
        for categorie in sorted(categories.METADATA):
            rendus[f'commercial_qx46_{categorie}'] = _sha(c_render.build_html(
                c_renderer._augment(c_sample.build(categorie))))
        for variante in ('deux', 'sans', 'long'):
            rendus[f'residentiel_{variante}'] = _sha(
                mf.html_residentiel(variante))
        return rendus

    def test_empreintes_html_identiques(self):
        rendus = self._rendus()
        if _CAPTURE:
            sg.ecrire_golden('split_sd_rendu_html', {'rendu': rendus})
        attendu = sg.charger_golden('split_sd_rendu_html').get('rendu')
        self.assertTrue(
            attendu, 'golden de rendu non capturé : lancer une fois '
            'SPLIT_GOLDEN_CAPTURE=1 sur ce module (voir la docstring)')
        self.assertEqual(rendus, attendu)
