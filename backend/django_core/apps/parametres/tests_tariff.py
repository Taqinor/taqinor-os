"""N64/N65 — tests de la Tarification & ROI.

Couvre : le modèle de facturation ONEE (progressif ≤150, sélectif >150 au tarif
unique de la tranche atteinte, tolérance 10 kWh décalant les bornes opératoires
à 210/310/510), la classe force motrice/agricole (séparée et moins chère), le
défaut ``surplus_injecte_compense=False`` (surplus = 0), le ROI conservateur,
le repli PVGIS hors-ligne (aucun accès réseau), et les endpoints (company posée
côté serveur, versionnement, écriture réservée à l'admin)."""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import SettingsAuditLog
from apps.parametres.models_tariff import TariffSettings
from apps.parametres import tariff as tariff_service
from apps.parametres import pvgis as pvgis_client

User = get_user_model()

GET_URL = '/api/django/parametres/tarification/'
PUT_URL = '/api/django/parametres/tarification/update/'
ROI_URL = '/api/django/parametres/tarification/roi/'
PROD_URL = '/api/django/parametres/tarification/productible/'


def _company(slug='tarif-co', nom='Tarif Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _auth(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


# ── Modèle & scoping société ──────────────────────────────────────────────────
class TariffSettingsModelTest(TestCase):
    def test_get_creates_one_per_company(self):
        c1, c2 = _company('c1', 'C1'), _company('c2', 'C2')
        a = TariffSettings.get(company=c1)
        b = TariffSettings.get(company=c1)
        d = TariffSettings.get(company=c2)
        self.assertEqual(a.pk, b.pk)           # singleton par société
        self.assertNotEqual(a.pk, d.pk)        # isolé par société
        self.assertEqual(a.version, 1)

    def test_surplus_compense_default_false(self):
        # Pas de net-metering par défaut : surplus non compensé.
        s = TariffSettings.get(company=_company())
        self.assertFalse(s.surplus_injecte_compense)
        self.assertEqual(s.surplus_prix_kwh_ttc, Decimal('0.0000'))

    def test_default_tiers_seeded(self):
        s = TariffSettings.get(company=_company())
        tiers = s.effective_tiers()
        # 6 paliers ; premier à 0.9010, palier ouvert à 1.5958.
        self.assertEqual(tiers[0]['max_kwh'], 100)
        self.assertEqual(tiers[0]['prix_kwh_ttc'], Decimal('0.9010'))
        self.assertIsNone(tiers[-1]['max_kwh'])
        self.assertEqual(tiers[-1]['prix_kwh_ttc'], Decimal('1.5958'))


# ── Modèle de facturation ONEE ────────────────────────────────────────────────
class BillingModelTest(TestCase):
    def setUp(self):
        self.s = TariffSettings.get(company=_company())

    def test_progressive_below_threshold(self):
        # 120 kWh ≤ 150 → progressif : 100×0.9010 + 20×1.0732.
        expected = Decimal('100') * Decimal('0.9010') \
            + Decimal('20') * Decimal('1.0732')
        bill = tariff_service.monthly_bill_residentiel(self.s, 120)
        self.assertEqual(bill, expected.quantize(Decimal('0.01')))

    def test_progressive_exactly_at_threshold(self):
        # 150 kWh (≤150) → progressif : 100×0.9010 + 50×1.0732.
        expected = Decimal('100') * Decimal('0.9010') \
            + Decimal('50') * Decimal('1.0732')
        bill = tariff_service.monthly_bill_residentiel(self.s, 150)
        self.assertEqual(bill, expected.quantize(Decimal('0.01')))

    def test_selective_whole_month_at_bracket_rate(self):
        # 250 kWh > 150 → SÉLECTIF : tout le mois au tarif de 211–310
        # (1.1676), PAS de progressivité.
        bill = tariff_service.monthly_bill_residentiel(self.s, 250)
        self.assertEqual(bill, (Decimal('250') * Decimal('1.1676'))
                         .quantize(Decimal('0.01')))

    def test_selective_is_not_progressive(self):
        # Vérifie explicitement que le sélectif n'empile PAS les tranches :
        # une facture progressive de 250 serait bien inférieure.
        selective = tariff_service.monthly_bill_residentiel(self.s, 250)
        progressive = (Decimal('100') * Decimal('0.9010')
                       + Decimal('50') * Decimal('1.0732')
                       + Decimal('60') * Decimal('1.0732')
                       + Decimal('40') * Decimal('1.1676'))
        self.assertGreater(selective, progressive.quantize(Decimal('0.01')))

    def test_tolerance_bound_at_210(self):
        # 205 kWh : sans tolérance tomberait dans 211–310 ; AVEC tolérance 10
        # la borne opératoire est 210 → reste au tarif 151–210 (1.0732).
        bill = tariff_service.monthly_bill_residentiel(self.s, 205)
        self.assertEqual(bill, (Decimal('205') * Decimal('1.0732'))
                         .quantize(Decimal('0.01')))

    def test_tolerance_bound_at_310(self):
        # 305 kWh : borne opératoire 310 → tarif 211–310 (1.1676).
        bill = tariff_service.monthly_bill_residentiel(self.s, 305)
        self.assertEqual(bill, (Decimal('305') * Decimal('1.1676'))
                         .quantize(Decimal('0.01')))

    def test_tolerance_bound_at_510(self):
        # 505 kWh : borne opératoire 510 → tarif 311–510 (1.3817).
        bill = tariff_service.monthly_bill_residentiel(self.s, 505)
        self.assertEqual(bill, (Decimal('505') * Decimal('1.3817'))
                         .quantize(Decimal('0.01')))

    def test_above_all_bounds_top_rate(self):
        # 600 kWh > 510 → tarif du palier ouvert (1.5958).
        bill = tariff_service.monthly_bill_residentiel(self.s, 600)
        self.assertEqual(bill, (Decimal('600') * Decimal('1.5958'))
                         .quantize(Decimal('0.01')))

    def test_zero_kwh_is_zero(self):
        self.assertEqual(
            tariff_service.monthly_bill_residentiel(self.s, 0),
            Decimal('0.00'))


# ── Classe force motrice / agricole ───────────────────────────────────────────
class ForceMotriceTest(TestCase):
    def setUp(self):
        self.s = TariffSettings.get(company=_company())

    def test_force_motrice_uses_cheap_flat_rate(self):
        bill = tariff_service.monthly_bill_force_motrice(self.s, 1000)
        self.assertEqual(bill, (Decimal('1000') * Decimal('0.9500'))
                         .quantize(Decimal('0.01')))

    def test_force_motrice_cheaper_than_residential_high(self):
        # À forte conso, la force motrice est bien moins chère que le haut
        # barème résidentiel.
        kwh = 1000
        fm = tariff_service.monthly_bill_force_motrice(self.s, kwh)
        res = tariff_service.monthly_bill_residentiel(self.s, kwh)
        self.assertLess(fm, res)

    def test_classe_dispatch(self):
        kwh = 500
        self.assertEqual(
            tariff_service.monthly_bill(self.s, kwh, 'agricole'),
            tariff_service.monthly_bill_force_motrice(self.s, kwh))
        self.assertEqual(
            tariff_service.monthly_bill(self.s, kwh, 'residentiel'),
            tariff_service.monthly_bill_residentiel(self.s, kwh))


# ── ROI conservateur ──────────────────────────────────────────────────────────
class RoiTest(TestCase):
    def setUp(self):
        self.s = TariffSettings.get(company=_company())

    def test_roi_surplus_zero_when_not_compensated(self):
        # Surplus non compensé (défaut) → valorisation du surplus = 0.
        r = tariff_service.compute_roi(
            self.s, kwc=10, conso_mensuelle_kwh=300,
            cout_total_ttc=100000)
        self.assertEqual(r['valorisation_surplus'], Decimal('0.00'))
        self.assertEqual(r['economie_totale_annuelle'],
                         r['economie_annuelle_ttc'])

    def test_roi_uses_manual_productible_by_default(self):
        # Sans PVGIS, productible = repli manuel (1500) × kWc.
        r = tariff_service.compute_roi(
            self.s, kwc=10, conso_mensuelle_kwh=300, cout_total_ttc=100000)
        self.assertEqual(r['production_annuelle_kwh'],
                         Decimal('15000.00'))

    def test_roi_pvgis_productible_overrides(self):
        r = tariff_service.compute_roi(
            self.s, kwc=10, conso_mensuelle_kwh=300, cout_total_ttc=100000,
            productible_kwh_kwc=1800)
        self.assertEqual(r['production_annuelle_kwh'],
                         Decimal('18000.00'))

    def test_roi_surplus_valued_when_compensated(self):
        self.s.surplus_injecte_compense = True
        self.s.surplus_prix_kwh_ttc = Decimal('0.8000')
        self.s.save()
        r = tariff_service.compute_roi(
            self.s, kwc=20, conso_mensuelle_kwh=50, cout_total_ttc=100000)
        # Grosse prod, petite conso → surplus non nul → valorisé.
        self.assertGreater(r['surplus_kwh'], Decimal('0'))
        self.assertGreater(r['valorisation_surplus'], Decimal('0'))

    def test_roi_payback_none_without_economy(self):
        r = tariff_service.compute_roi(
            self.s, kwc=0, conso_mensuelle_kwh=300, cout_total_ttc=100000)
        self.assertIsNone(r['payback_annees'])


# ── PVGIS — repli hors-ligne (jamais de réseau dans les tests) ────────────────
class PvgisFallbackTest(TestCase):
    def setUp(self):
        self.s = TariffSettings.get(company=_company())

    def test_fallback_when_pvgis_disabled(self):
        # PVGIS désactivé → repli manuel, sans aucun appel réseau.
        self.s.pvgis_actif = False
        self.s.save()
        res = pvgis_client.fetch_productible(self.s, 33.5, -7.6)
        self.assertEqual(res['source'], 'manual')
        self.assertEqual(res['productible_kwh_kwc'], 1500.0)

    def test_fallback_on_invalid_coords(self):
        res = pvgis_client.fetch_productible(self.s, None, None)
        self.assertEqual(res['source'], 'manual')
        self.assertIn('GPS', res['reason'])

    def test_fallback_on_network_error_offline(self):
        # Forcer l'indisponibilité réseau : on remplace l'URL par une adresse
        # injoignable + timeout court → repli manuel, JAMAIS d'exception.
        original = pvgis_client.PVGIS_BASE
        try:
            pvgis_client.PVGIS_BASE = 'http://127.0.0.1:1/PVcalc'
            res = pvgis_client.fetch_productible(self.s, 33.5, -7.6)
        finally:
            pvgis_client.PVGIS_BASE = original
        self.assertEqual(res['source'], 'manual')
        self.assertEqual(res['productible_kwh_kwc'], 1500.0)
        self.assertIsNotNone(res['reason'])

    def test_manual_fallback_respects_edited_value(self):
        self.s.pvgis_actif = False
        self.s.productible_manuel_kwh_kwc = Decimal('1700.0')
        self.s.save()
        res = pvgis_client.fetch_productible(self.s, 33.5, -7.6)
        self.assertEqual(res['productible_kwh_kwc'], 1700.0)


# ── Endpoints ─────────────────────────────────────────────────────────────────
class TariffApiTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = User.objects.create_user(
            username='tarif_admin', password='x',
            role_legacy='admin', company=self.company)
        self.api = _auth(self.admin)

    def test_get_returns_defaults(self):
        r = self.api.get(GET_URL)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['surplus_injecte_compense'])
        self.assertEqual(r.data['version'], 1)
        self.assertNotIn('company', r.data)   # company jamais exposée

    def test_update_persists_and_bumps_version(self):
        r = self.api.patch(
            PUT_URL, {'tolerance_kwh': 15}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['tolerance_kwh'], 15)
        self.assertEqual(r.data['version'], 2)
        s = TariffSettings.get(company=self.company)
        self.assertEqual(s.tolerance_kwh, 15)

    def test_update_no_change_keeps_version(self):
        self.api.patch(PUT_URL, {'tolerance_kwh': 12}, format='json')
        r = self.api.patch(PUT_URL, {'tolerance_kwh': 12}, format='json')
        self.assertEqual(r.data['version'], 2)

    def test_update_writes_audit_log(self):
        self.api.patch(
            PUT_URL, {'surplus_injecte_compense': True}, format='json')
        logs = SettingsAuditLog.objects.filter(
            company=self.company, section='tarification',
            field='surplus_injecte_compense')
        self.assertEqual(logs.count(), 1)

    def test_company_forced_server_side(self):
        other = _company('other', 'Other')
        r = self.api.patch(
            PUT_URL, {'tolerance_kwh': 20, 'company': other.id},
            format='json')
        self.assertEqual(r.status_code, 200)
        s = TariffSettings.get(company=self.company)
        self.assertEqual(s.tolerance_kwh, 20)
        self.assertEqual(s.company_id, self.company.id)

    def test_invalid_tiers_rejected(self):
        r = self.api.patch(
            PUT_URL, {'residential_tiers': 'pas-une-liste'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_custom_tiers_persist_and_drive_calc(self):
        r = self.api.patch(PUT_URL, {'residential_tiers': [
            {'max_kwh': 100, 'prix_kwh_ttc': '1.0000'},
            {'max_kwh': None, 'prix_kwh_ttc': '2.0000'},
        ]}, format='json')
        self.assertEqual(r.status_code, 200)
        s = TariffSettings.get(company=self.company)
        # 80 kWh ≤ seuil → progressif : 80 × 1.0 = 80.
        self.assertEqual(
            tariff_service.monthly_bill_residentiel(s, 80),
            Decimal('80.00'))

    def test_compute_roi_endpoint(self):
        r = self.api.post(ROI_URL, {
            'kwc': 10, 'conso_mensuelle_kwh': 300, 'cout_total_ttc': 100000,
        }, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('economie_totale_annuelle', r.data)
        self.assertIn('facture_mensuelle_ttc', r.data)
        # Surplus non compensé → valorisation 0.
        self.assertEqual(r.data['valorisation_surplus'], '0.00')

    def test_productible_endpoint_offline_fallback(self):
        # Endpoint ne dépend pas du réseau : avec PVGIS désactivé → manual.
        self.api.patch(PUT_URL, {'pvgis_actif': False}, format='json')
        r = self.api.get(PROD_URL, {'lat': 33.5, 'lon': -7.6})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['source'], 'manual')

    def test_non_admin_cannot_update(self):
        limited = User.objects.create_user(
            username='tarif_limited', password='x',
            role_legacy='commercial', company=self.company)
        api = _auth(limited)
        r = api.patch(PUT_URL, {'tolerance_kwh': 99}, format='json')
        self.assertIn(r.status_code, (401, 403))

    def test_non_admin_can_read_and_compute(self):
        limited = User.objects.create_user(
            username='tarif_reader', password='x',
            role_legacy='commercial', company=self.company)
        api = _auth(limited)
        self.assertEqual(api.get(GET_URL).status_code, 200)
        r = api.post(ROI_URL, {
            'kwc': 5, 'conso_mensuelle_kwh': 200, 'cout_total_ttc': 50000,
        }, format='json')
        self.assertEqual(r.status_code, 200)
