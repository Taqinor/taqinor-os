"""QJR138 — l'autoconsommation tourne sur la production NETTE et la saisonnalité RÉELLE.

Deux défauts d'une même chaîne, tous deux dans le sens qui MAJORAIT l'économie
annoncée :

(a) la courbe remise à ``hourly_self_consumption`` n'appliquait QUE l'ombrage,
    aucun poste de l'arbre de pertes : elle dépassait d'environ 20 % la
    ``p50_kwh`` publiée dans le MÊME dict, et ``self_consumed_kwh`` avec elle
    (puis ``annual_savings_year1`` → VAN/TRI/payback) ;
(b) ``monthly_kwh = base / 12`` lissait la production à plat alors que la part
    mensuelle réelle (TMY) était calculée deux lignes plus haut et déjà
    utilisée pour pondérer l'ombrage. Charge ET production à plat,
    ``Σ min(charge, production)`` se prenait sur des moyennes : par concavité
    de ``min``, l'autoconsommation était SYSTÉMATIQUEMENT majorée.

Les deux effets sont isolés ici, puis mesurés ensemble sur un profil été/hiver
contrasté. Les fetchers réseau sont monkeypatchés — aucun accès réseau.
"""
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.ventes.etude import (
    _tiled_load_curve,
    _weighted_shading_loss_pct,
    _zone_monthly_share,
    _zone_production_weights,
    production_horaire_zone,
    production_nette_canonique_kwh,
    run_bankable_study,
)
from apps.ventes.solar_design import hourly_self_consumption
from apps.ventes.tests.test_quote_engine import (
    make_client, make_company, make_devis, make_user,
)

# Irradiation mensuelle CONTRASTÉE été/hiver (kWh/m², forme marocaine typique) —
# le déséquilibre saisonnier est la raison même de vendre une batterie.
_IRR_MENSUELLE = [80.0, 95.0, 130.0, 150.0, 175.0, 185.0,
                  190.0, 180.0, 150.0, 120.0, 90.0, 75.0]
_PRODUCTIBLE_NET14 = 1700.0
_KWC = 10.0
_BASE = _PRODUCTIBLE_NET14 * _KWC


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
        'irradiance_annuelle_kwh_m2': sum(_IRR_MENSUELLE),
        'irradiance_mensuelle_kwh_m2': list(_IRR_MENSUELLE),
        'temperature_moyenne_c': 19.0,
        'reason': None,
    }


def _autoconso(load_curve, production_curve):
    return hourly_self_consumption(
        load_curve=load_curve, production_curve=production_curve,
    )['self_consumed_kwh']


class TestQJR138CourbePure(SimpleTestCase):
    """Les deux effets, isolés sur la fonction pure (aucune base)."""

    def setUp(self):
        self.share = _zone_monthly_share(
            {'irradiance_mensuelle_kwh_m2': _IRR_MENSUELLE})
        self.zone_nette = {
            'base_production_kwh': _BASE,
            'production_nette_kwh': production_nette_canonique_kwh(_BASE),
        }
        # 14 000 kWh/an : un résidentiel qui consomme moins qu'il ne produit.
        self.load = _tiled_load_curve(14000.0 / 365.0, 'residential')

    def test_les_parts_mensuelles_sont_bien_contrastees(self):
        self.assertAlmostEqual(sum(self.share), 1.0, places=9)
        self.assertGreater(max(self.share), 2.0 * min(self.share))

    # ── (a) production NETTE, plus la production BRUTE ─────────────────────

    def test_la_courbe_nette_somme_a_la_production_canonique(self):
        curve = production_horaire_zone(
            self.zone_nette, monthly_share=self.share)
        self.assertAlmostEqual(sum(curve), production_nette_canonique_kwh(_BASE),
                               delta=1.0)

    def test_la_courbe_brute_depassait_la_nette(self):
        brute = production_horaire_zone(
            {'base_production_kwh': _BASE}, monthly_share=self.share)
        nette = production_horaire_zone(
            self.zone_nette, monthly_share=self.share)
        self.assertGreater(sum(brute), sum(nette))

    def test_effet_a_la_production_nette_baisse_l_autoconsommation(self):
        brute = production_horaire_zone(
            {'base_production_kwh': _BASE}, monthly_share=self.share)
        nette = production_horaire_zone(
            self.zone_nette, monthly_share=self.share)
        self.assertLess(_autoconso(self.load, nette),
                        _autoconso(self.load, brute))

    # ── (b) saisonnalité RÉELLE, plus la répartition plate ─────────────────

    def test_effet_b_la_saisonnalite_baisse_l_autoconsommation(self):
        plate = production_horaire_zone(self.zone_nette)
        saison = production_horaire_zone(
            self.zone_nette, monthly_share=self.share)
        # Même énergie annuelle, répartie autrement.
        self.assertAlmostEqual(sum(plate), sum(saison), delta=1.0)
        # Par concavité de min, l'autoconsommation ne peut que baisser.
        self.assertLess(_autoconso(self.load, saison),
                        _autoconso(self.load, plate))

    def test_le_desequilibre_saisonnier_est_bien_dans_la_courbe(self):
        curve = production_horaire_zone(
            self.zone_nette, monthly_share=self.share)
        juillet = sum(curve[6 * 24:7 * 24])
        decembre = sum(curve[11 * 24:12 * 24])
        self.assertGreater(juillet, 2.0 * decembre)

    def test_les_deux_effets_ensemble_font_baisser_l_autoconsommation(self):
        avant = production_horaire_zone({'base_production_kwh': _BASE})
        apres = production_horaire_zone(
            self.zone_nette, monthly_share=self.share)
        self.assertLess(_autoconso(self.load, apres),
                        _autoconso(self.load, avant))

    # ── Replis : jamais d'exception, comportement historique préservé ──────

    def test_monthly_share_absent_ou_illisible_revient_aux_parts_egales(self):
        attendu = production_horaire_zone(self.zone_nette)
        for mauvais in (None, [], [1.0] * 5, [0.0] * 12, ['x'] * 12):
            self.assertEqual(
                production_horaire_zone(self.zone_nette, monthly_share=mauvais),
                attendu, msg=f'monthly_share={mauvais!r}')

    def test_sans_production_nette_la_base_historique_est_conservee(self):
        curve = production_horaire_zone({'base_production_kwh': 12000.0})
        self.assertEqual(len(curve), 288)
        self.assertAlmostEqual(sum(curve), 12000.0, delta=1.0)

    def test_base_absente_rend_288_zeros(self):
        self.assertEqual(production_horaire_zone(None), [0.0] * 288)
        self.assertEqual(production_horaire_zone({}), [0.0] * 288)
        self.assertEqual(
            production_horaire_zone({'production_nette_kwh': 0.0}), [0.0] * 288)

    def test_la_matrice_d_ombrage_est_toujours_appliquee(self):
        matrix = [[0.0 if h == 20 else 1.0 for h in range(24)]
                  for _ in range(12)]
        curve = production_horaire_zone(
            self.zone_nette, matrix, monthly_share=self.share)
        for m in range(12):
            self.assertEqual(curve[m * 24 + 20], 0.0)


class TestQJR138ChaineComplete(TestCase):
    """L'invariant de bout en bout : la courbe somme à la p50 publiée."""

    def setUp(self):
        from django.core.cache import cache as django_cache
        django_cache.clear()
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '20', '1500'),
        ], reference='DEV-QJR138-0001')

    def _run(self, zone_extra=None):
        zone = {'label': 'Pan Sud', 'lat': 33.57, 'lon': -7.59,
                'tilt': 30, 'azimuth': 0, 'kwc': _KWC}
        zone.update(zone_extra or {})
        with mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy',
                        side_effect=_fake_tmy), \
             mock.patch('apps.parametres.pvgis.fetch_productible',
                        side_effect=_fake_productible):
            return run_bankable_study(self.devis, zones=[zone])

    def _production_curve(self, result):
        """Reconstruit la courbe telle que ``run_bankable_study`` l'a bâtie."""
        share = _zone_monthly_share(_fake_tmy(0, 0))
        zone = result['zones'][0]
        return production_horaire_zone(
            {**zone,
             'production_nette_kwh': production_nette_canonique_kwh(
                 zone['base_production_kwh'])},
            None, monthly_share=share)

    def test_la_courbe_de_production_somme_a_la_p50_publiee(self):
        """Le cœur de (a) : plus AUCUN écart entre la courbe et le chiffre publié."""
        result = self._run()
        total_courbe = sum(self._production_curve(result))
        p50 = result['pr']['p50_kwh']
        self.assertLess(abs(total_courbe - p50) / p50, 0.001,
                        f'courbe {total_courbe} vs p50 publiée {p50}')

    def test_l_autoconsommation_a_baisse_face_a_l_ancienne_courbe(self):
        """La comparaison avant/après demandée, sur le profil été/hiver."""
        result = self._run()
        load = _tiled_load_curve(14000.0 / 365.0, 'residential')
        ancienne = production_horaire_zone(
            {'base_production_kwh': result['zones'][0]['base_production_kwh']})
        self.assertLess(_autoconso(load, self._production_curve(result)),
                        _autoconso(load, ancienne))

    def test_l_ombrage_reste_pondere_par_les_memes_parts_mensuelles(self):
        """La courbe et la perte d'ombrage lisent la MÊME saisonnalité."""
        matrix = [[0.9] * 24 for _ in range(12)]
        result = self._run({'shading12x24': matrix})
        share = _zone_monthly_share(_fake_tmy(0, 0))
        attendu = _weighted_shading_loss_pct(
            matrix, _zone_production_weights(share))
        self.assertAlmostEqual(
            result['zones'][0]['shading_annual_loss_pct'], attendu, places=2)
