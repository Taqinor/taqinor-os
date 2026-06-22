"""Q3 — build_devis_from_layout() turns a finalized layout into a Devis.

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_build_from_layout -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.services import build_devis_from_layout

User = get_user_model()


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def seed_catalogue(company, with_prices=True):
    """Minimal seeded catalogue mirroring seed_catalogue naming."""
    def mk(nom, sku, prix):
        return Produit.objects.create(
            company=company, nom=nom, sku=sku,
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100)
    mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100)
    mk('Onduleur réseau Huawei 5kW Monophasé', f'ONDR-{company.pk}', 14000)
    mk('Onduleur hybride Deye 5kW Monophasé', f'ONDH-{company.pk}', 17000)
    mk('Batterie Deyness 5 kWh', f'BAT-{company.pk}', 17000)


class TestBuildFromLayout(TestCase):
    def setUp(self):
        self.company = make_company('q3-co')
        self.user = User.objects.create_user(
            username='q3user', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Layout', prenom='Lead',
            email='layout@ex.com', **extra)

    def test_residential_reseau(self):
        layout = {
            'scenario': 'reseau',
            'result': {'panels': 12, 'kwc': 6.6,
                       'annualKwh': 10800, 'savings': 9200},
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        self.assertEqual(devis.statut, 'brouillon')
        self.assertEqual(devis.company_id, self.company.id)
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('Panneau' in d for d in desigs))
        self.assertTrue(any('réseau' in d for d in desigs))
        self.assertFalse(any('Batterie' in d for d in desigs))
        # production stored
        self.assertEqual(devis.etude_params['production_annuelle'], 10800)
        # panel qty matches the layout
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), 12)
        # totals coherent (non-zero)
        self.assertGreater(devis.total_ttc, 0)
        # reference uses the DEV-YYYYMM-NNNN scheme (never count()+1)
        self.assertTrue(devis.reference.startswith('DEV-'))

    def test_hybride_with_battery(self):
        layout = {
            'scenario': 'avec_batterie',
            'result': {'panels': 10, 'kwc': 5.5,
                       'annualKwh': 9000, 'savings': 8000},
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('hybride' in d for d in desigs))
        self.assertTrue(any('Batterie' in d for d in desigs))
        self.assertFalse(any('réseau' in d for d in desigs))

    def test_priceless_product_never_quoted(self):
        # A price-less panel must be skipped even if it matches the keyword.
        Produit.objects.filter(nom__startswith='Panneau').update(prix_vente=0)
        # add an alternative priced panel so we can confirm selection skips 0.
        Produit.objects.create(
            company=self.company, nom='Panneau Pricey 550W',
            sku=f'PANP-{self.company.pk}', prix_vente=Decimal('1200'),
            prix_achat=Decimal('1'), quantite_stock=10)
        layout = {'scenario': 'reseau',
                  'result': {'panels': 8, 'kwc': 4.4}}
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertGreater(panel.prix_unitaire, 0)
        self.assertEqual(panel.designation, 'Panneau Pricey 550W')

    def test_all_priceless_skips_line(self):
        Produit.objects.all().update(prix_vente=0)
        layout = {'scenario': 'reseau',
                  'result': {'panels': 8, 'kwc': 4.4}}
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        self.assertEqual(devis.lignes.count(), 0)

    def test_client_resolved_from_lead_no_duplicate(self):
        lead = self._lead()
        d1 = build_devis_from_layout(
            layout={'result': {'panels': 4, 'kwc': 2.2}},
            user=self.user, company=self.company, lead=lead)
        d2 = build_devis_from_layout(
            layout={'result': {'panels': 4, 'kwc': 2.2}},
            user=self.user, company=self.company, lead=lead)
        self.assertEqual(d1.client_id, d2.client_id)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 1)

    def test_other_tenant_catalogue_not_used(self):
        other = make_company('q3-other')
        # other company's products must not leak into this company's quote
        Produit.objects.create(
            company=other, nom='Panneau Foreign 550W', sku='PAN-FOR',
            prix_vente=Decimal('1'), prix_achat=Decimal('1'),
            quantite_stock=1)
        layout = {'result': {'panels': 6, 'kwc': 3.3}}
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        for li in devis.lignes.all():
            self.assertNotIn('Foreign', li.designation)


class TestFG248RoofBridge(TestCase):
    """FG248 — pont 3D toiture web → ERP : import surface/pans/orientation/kWc."""

    def setUp(self):
        self.company = make_company('fg248-co')
        self.user = User.objects.create_user(
            username='fg248user', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Roof', prenom='Lead',
            email='roof@ex.com', **extra)

    def test_extract_roof_config_pure(self):
        from apps.ventes.services import extract_roof_config
        layout = {
            'areas': [
                {'label': 'Pan Sud', 'roofType': 'pitched', 'pitchDeg': 30,
                 'facingAzimuthDeg': 0,
                 'result': {'count': 12, 'kwc': 6.6, 'areaM2': 24.0}},
                {'label': 'Pan Est', 'roofType': 'pitched', 'pitchDeg': 25,
                 'facingAzimuthDeg': -90,
                 'result': {'count': 4, 'kwc': 2.2, 'areaM2': 9.0}},
            ],
        }
        cfg = extract_roof_config(layout)
        self.assertEqual(cfg['nb_pans'], 2)
        self.assertEqual(cfg['nb_panneaux'], 16)
        self.assertAlmostEqual(cfg['surface_m2'], 33.0, places=1)
        self.assertAlmostEqual(cfg['kwc'], 8.8, places=2)
        # Orientation principale = pan le plus puissant (Sud).
        self.assertEqual(cfg['orientation_principale'], 'Sud')
        self.assertEqual(cfg['azimut_deg'], 0)
        self.assertEqual(cfg['inclinaison_deg'], 30)
        self.assertEqual(len(cfg['pans']), 2)
        self.assertEqual(cfg['pans'][1]['orientation'], 'Est')

    def test_extract_empty_layout_is_empty(self):
        from apps.ventes.services import extract_roof_config
        self.assertEqual(extract_roof_config({}), {})
        self.assertEqual(extract_roof_config(
            {'result': {'panels': 8}}), {})
        self.assertEqual(extract_roof_config({'areas': []}), {})

    def test_roof_config_stored_in_devis(self):
        layout = {
            'scenario': 'reseau',
            'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800},
            'areas': [
                {'label': 'Toiture', 'roofType': 'pitched', 'pitchDeg': 20,
                 'facingAzimuthDeg': 0,
                 'result': {'count': 12, 'kwc': 6.6, 'areaM2': 24.0}},
            ],
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        toiture = devis.etude_params['toiture']
        self.assertEqual(toiture['nb_panneaux'], 12)
        self.assertEqual(toiture['orientation_principale'], 'Sud')
        self.assertAlmostEqual(toiture['surface_m2'], 24.0, places=1)

    def test_panels_fallback_from_pans_when_result_missing(self):
        """Layout 3D sans bloc result : les panneaux viennent des pans."""
        layout = {
            'scenario': 'reseau',
            'areas': [
                {'roofType': 'pitched', 'pitchDeg': 30, 'facingAzimuthDeg': 0,
                 'result': {'count': 10, 'kwc': 5.5, 'areaM2': 20.0}},
            ],
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        panel = next((li for li in devis.lignes.all()
                      if 'Panneau' in li.designation), None)
        self.assertIsNotNone(panel)
        self.assertEqual(int(panel.quantite), 10)
        self.assertEqual(devis.etude_params['toiture']['nb_pans'], 1)

    def test_legacy_layout_unchanged(self):
        """Layout sans géométrie → pas de clé toiture (rétro-compat)."""
        layout = {'scenario': 'reseau',
                  'result': {'panels': 8, 'kwc': 4.4, 'annualKwh': 7000}}
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        self.assertNotIn('toiture', devis.etude_params or {})
        self.assertEqual(devis.etude_params['production_annuelle'], 7000)
