"""QJR114 — le derate système n'est plus appliqué DEUX FOIS (étude bancable).

`apps.parametres.pvgis.fetch_productible` interroge PVGIS avec ``loss=14`` :
le productible rendu est DÉJÀ net de ces 14 %. Le chemin bancable le passait
tel quel à ``simulate_bankable_yield``, qui exige une base « AVANT pertes » et
réapplique un arbre complet — 28,3 % de pertes cumulées au lieu des 20 %
tranchés par le fondateur, et deux productions contradictoires sur la MÊME
page Étude du PDF (carte « Production annuelle » au derate canonique 0,9302
contre la P50 bancable).

La garde épinglée ici : à ombrage nul, la P50 bancable et la production
canonique de ``quote_engine.pricing`` décrivent le même devis à moins de 1 %
près (elles sont en fait ÉGALES par construction). Les deux fetchers réseau
sont monkeypatchés — ces tests ne touchent JAMAIS le réseau.
"""
from unittest import mock

from django.test import TestCase

from apps.ventes.etude import (
    base_avant_pertes_kwh,
    loss_factors_canoniques,
    production_nette_canonique_kwh,
    run_bankable_study,
)
from apps.ventes.quote_engine.pricing import (
    PRODUCTION_DERATE,
    PVGIS_BUILTIN_LOSS,
    SYSTEM_LOSS_TOTAL,
)
from apps.ventes.solar_design import DEFAULT_LOSS_FACTORS
from apps.ventes.tests.test_quote_engine import (
    make_client, make_company, make_devis, make_user,
)

# Productible PVGIS simulé (kWh/kWc/an) — net des 14 % demandés à l'API.
_PRODUCTIBLE_NET14 = 1700.0
_KWC = 10.0


def _fake_productible(settings, lat, lon, *, peakpower_kwc=1.0, tilt=None,
                      azimuth=None):
    return {
        'source': 'pvgis',
        'productible_kwh_kwc': _PRODUCTIBLE_NET14,
        'production_mensuelle_kwh_kwc': None,
        'reason': None,
    }


def _fake_tmy(lat, lon):
    return {
        'source': 'pvgis',
        'irradiance_annuelle_kwh_m2': 2000.0,
        'irradiance_mensuelle_kwh_m2': [120.0] * 12,
        'temperature_moyenne_c': 19.0,
        'reason': None,
    }


class TestQJR114DerateUnique(TestCase):
    def setUp(self):
        from django.core.cache import cache as django_cache
        django_cache.clear()
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '20', '1500'),
        ], reference='DEV-QJR114-0001')

    def _zones(self, **extra):
        zone = {'label': 'Pan Sud', 'lat': 33.57, 'lon': -7.59,
                'tilt': 30, 'azimuth': 0, 'kwc': _KWC}
        zone.update(extra)
        return [zone]

    def _run(self, zones=None):
        with mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy',
                        side_effect=_fake_tmy), \
             mock.patch('apps.parametres.pvgis.fetch_productible',
                        side_effect=_fake_productible):
            return run_bankable_study(self.devis, zones=zones or self._zones())

    # ── LA GARDE : une seule production pour un même devis ──────────────────

    def test_p50_et_production_canonique_ne_divergent_pas_de_plus_de_1_pct(self):
        """Un même devis ne peut pas produire deux productions écartées > 1 %."""
        result = self._run()
        p50 = result['pr']['p50_kwh']

        # La production canonique du dépôt : productible PVGIS (net 14 %) ×
        # PRODUCTION_DERATE — la formule EXACTE de pricing (carte « Production
        # annuelle ») et d'etude_horaire.
        canonique = _PRODUCTIBLE_NET14 * _KWC * PRODUCTION_DERATE

        ecart_relatif = abs(p50 - canonique) / canonique
        self.assertLess(
            ecart_relatif, 0.01,
            f"P50 bancable {p50} vs production canonique {canonique} : "
            f"{ecart_relatif:.2%} d'écart — deux vérités sur la même page")

    def test_p50_est_exactement_la_production_canonique(self):
        """Au-delà de la tolérance : l'égalité est EXACTE par construction."""
        result = self._run()
        canonique = _PRODUCTIBLE_NET14 * _KWC * PRODUCTION_DERATE
        self.assertAlmostEqual(result['pr']['p50_kwh'], canonique, places=1)

    def test_le_double_derate_historique_est_bien_parti(self):
        """Régression : l'ancien calcul (base nette × arbre par défaut)."""
        pr_arbre_defaut = 1.0
        for frac in DEFAULT_LOSS_FACTORS.values():
            pr_arbre_defaut *= (1.0 - frac)
        double_derate = _PRODUCTIBLE_NET14 * _KWC * pr_arbre_defaut

        result = self._run()
        # L'ancienne valeur était ~11 % sous la canonique : elle doit avoir
        # disparu, pas seulement s'être rapprochée.
        self.assertGreater(result['pr']['p50_kwh'], double_derate * 1.05)

    # ── La cascade AFFICHÉE est cohérente avec la garde ─────────────────────

    def test_cascade_totalise_les_20_pct_du_fondateur(self):
        result = self._run()
        pr = result['pr']
        self.assertAlmostEqual(pr['performance_ratio'], 1.0 - SYSTEM_LOSS_TOTAL,
                               places=3)
        self.assertAlmostEqual(pr['total_loss_pct'], SYSTEM_LOSS_TOTAL * 100.0,
                               places=1)

    def test_les_postes_affiches_expliquent_le_total_affiche(self):
        """Le produit des postes de la cascade REND le total publié."""
        pr = self._run()['pr']
        produit = 1.0
        for pct in pr['loss_breakdown'].values():
            produit *= (1.0 - pct / 100.0)
        self.assertAlmostEqual(produit * 100.0,
                               (1.0 - pr['total_loss_pct'] / 100.0) * 100.0,
                               places=1)

    def test_les_cles_de_la_cascade_sont_inchangees(self):
        """Contrat PACT10 : le calage ne renomme AUCUN poste."""
        pr = self._run()['pr']
        attendues = set(DEFAULT_LOSS_FACTORS) | {'shading'}
        self.assertEqual(set(pr['loss_breakdown']), attendues)

    def test_les_postes_gardent_leur_poids_relatif(self):
        """Le calage est une remise à l'échelle, pas une réécriture."""
        factors = loss_factors_canoniques(0.0)
        # La température reste le poste dominant, la disponibilité le moindre.
        sans_ombrage = {p: f for p, f in factors.items() if p != 'shading'}
        self.assertEqual(max(sans_ombrage, key=sans_ombrage.get), 'temperature')
        self.assertEqual(min(sans_ombrage, key=sans_ombrage.get), 'availability')
        # ... et chaque poste reste dans le même ordre de grandeur.
        for poste, defaut in DEFAULT_LOSS_FACTORS.items():
            self.assertLess(sans_ombrage[poste], defaut * 1.5)
            self.assertGreater(sans_ombrage[poste], defaut)

    def test_produit_des_facteurs_cales_vaut_le_total_fondateur(self):
        produit = 1.0
        for poste, frac in loss_factors_canoniques(0.0).items():
            if poste == 'shading':
                continue
            produit *= (1.0 - frac)
        self.assertAlmostEqual(produit, 1.0 - SYSTEM_LOSS_TOTAL, places=6)

    # ── L'ombrage MESURÉ s'ajoute, sans entrer dans le calage ───────────────

    def test_ombrage_mesure_sajoute_tel_quel_et_baisse_la_p50(self):
        matrice = [[0.9] * 24 for _ in range(12)]
        avec_ombrage = self._run(self._zones(shading12x24=matrice))
        sans_ombrage = self._run()

        self.assertGreater(avec_ombrage['pr']['loss_breakdown']['shading'], 0.0)
        self.assertLess(avec_ombrage['pr']['p50_kwh'],
                        sans_ombrage['pr']['p50_kwh'])
        # La P50 ombragée reste la canonique diminuée de l'ombrage MESURÉ.
        ombrage = avec_ombrage['pr']['loss_breakdown']['shading'] / 100.0
        attendue = production_nette_canonique_kwh(
            _PRODUCTIBLE_NET14 * _KWC, ombrage)
        self.assertAlmostEqual(avec_ombrage['pr']['p50_kwh'], attendue,
                               delta=max(1.0, attendue * 0.001))

    # ── Les briques, isolément ─────────────────────────────────────────────

    def test_base_avant_pertes_remonte_au_brut(self):
        self.assertAlmostEqual(
            base_avant_pertes_kwh(17000.0) * (1.0 - PVGIS_BUILTIN_LOSS),
            17000.0, places=6)

    def test_base_avant_pertes_ne_leve_jamais(self):
        self.assertEqual(base_avant_pertes_kwh(0.0), 0.0)
        self.assertEqual(base_avant_pertes_kwh(None), 0.0)
        self.assertEqual(base_avant_pertes_kwh('illisible'), 0.0)
        self.assertEqual(base_avant_pertes_kwh(-5.0), 0.0)

    def test_production_nette_canonique_est_la_formule_de_pricing(self):
        self.assertAlmostEqual(
            production_nette_canonique_kwh(17000.0),
            17000.0 * PRODUCTION_DERATE, places=6)
        self.assertEqual(production_nette_canonique_kwh(0.0), 0.0)
        self.assertEqual(production_nette_canonique_kwh(None), 0.0)
