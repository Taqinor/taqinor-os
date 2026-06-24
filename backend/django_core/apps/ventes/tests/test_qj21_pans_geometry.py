"""QJ21 — multi-pan geometry fidelity in roof_layout._pans_geometry.

build_devis_from_layout must store a ``_pans_geometry`` key in the Devis
``roof_layout`` JSON carrying the per-pan processed data (azimut_deg,
inclinaison_deg, kwc, nb_panneaux, orientation, label, roof_type) so
consumers never have to re-run extract_roof_config on the raw zones.

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \\
        python manage.py test apps.ventes.tests.test_qj21_pans_geometry -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.services import build_devis_from_layout

User = get_user_model()


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def seed_catalogue(company):
    def mk(nom, sku, prix):
        return Produit.objects.create(
            company=company, nom=nom, sku=sku,
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100)
    mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100)
    mk('Onduleur réseau Huawei 5kW Monophasé', f'ONDR-{company.pk}', 14000)


def make_multi_pan_layout():
    """Two-zone layout: Sud (12 panels, 6.6 kWc) + Est (4 panels, 2.2 kWc)."""
    return {
        'version': 1,
        'scenario': 'reseau',
        'result': {'panels': 16, 'kwc': 8.8, 'annualKwh': 14000, 'savings': 11000},
        'zones': [
            {
                'id': 'z1', 'label': 'Pan Sud',
                'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
                'obstacles': [],
                'roofType': 'pitched',
                'pitchDeg': 30,
                'facingAzimuthDeg': 0,
                'neededPanels': 12,
                'neededAuto': True,
            },
            {
                'id': 'z2', 'label': 'Pan Est',
                'vertices': [[10, 0], [16, 0], [16, 6], [10, 6]],
                'obstacles': [],
                'roofType': 'pitched',
                'pitchDeg': 25,
                'facingAzimuthDeg': -90,
                'neededPanels': 4,
                'neededAuto': True,
            },
        ],
    }


class TestQJ21PansGeometry(TestCase):
    """QJ21 — full multi-pan geometry stored in roof_layout._pans_geometry."""

    def setUp(self):
        self.company = make_company('qj21-co')
        self.user = User.objects.create_user(
            username='qj21user', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Pans', prenom='Test',
            email='pans@ex.com', **extra)

    def test_multi_pan_geometry_stored_in_roof_layout(self):
        """Two-zone layout round-trips with per-pan azimut_deg in roof_layout."""
        layout = make_multi_pan_layout()
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())

        self.assertIsNotNone(devis.roof_layout)
        pans_geo = devis.roof_layout.get('_pans_geometry')
        self.assertIsNotNone(pans_geo,
                             '_pans_geometry must be stored in roof_layout')
        self.assertEqual(len(pans_geo), 2)

        # Pan Sud — azimut 0, inclinaison 30, orientation Sud
        pan_sud = next(p for p in pans_geo if p['label'] == 'Pan Sud')
        self.assertEqual(pan_sud['azimut_deg'], 0)
        self.assertEqual(pan_sud['inclinaison_deg'], 30)
        self.assertEqual(pan_sud['orientation'], 'Sud')
        self.assertEqual(pan_sud['nb_panneaux'], 12)
        self.assertEqual(pan_sud['roof_type'], 'pitched')

        # Pan Est — azimut -90, inclinaison 25, orientation Est
        pan_est = next(p for p in pans_geo if p['label'] == 'Pan Est')
        self.assertEqual(pan_est['azimut_deg'], -90)
        self.assertEqual(pan_est['inclinaison_deg'], 25)
        self.assertEqual(pan_est['orientation'], 'Est')
        self.assertEqual(pan_est['nb_panneaux'], 4)

    def test_per_pan_azimuth_matches_etude_params_toiture(self):
        """_pans_geometry is consistent with etude_params.toiture.pans."""
        layout = make_multi_pan_layout()
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())

        pans_geo = devis.roof_layout['_pans_geometry']
        toiture_pans = devis.etude_params['toiture']['pans']
        # Both lists should carry the same per-pan data.
        self.assertEqual(len(pans_geo), len(toiture_pans))
        for g, t in zip(pans_geo, toiture_pans):
            self.assertEqual(g['azimut_deg'], t['azimut_deg'])
            self.assertEqual(g['inclinaison_deg'], t['inclinaison_deg'])
            self.assertEqual(g['orientation'], t['orientation'])
            self.assertEqual(g['nb_panneaux'], t['nb_panneaux'])

    def test_original_layout_dict_not_mutated(self):
        """build_devis_from_layout must not mutate the caller's layout dict."""
        layout = make_multi_pan_layout()
        self.assertNotIn('_pans_geometry', layout)
        build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        # Caller's dict is unchanged.
        self.assertNotIn('_pans_geometry', layout)

    def test_single_pan_layout_still_stores_geometry(self):
        """A single-pan layout also stores _pans_geometry with one entry."""
        layout = {
            'scenario': 'reseau',
            'result': {'panels': 10, 'kwc': 5.5, 'annualKwh': 9000},
            'zones': [{
                'id': 'z1', 'label': 'Toit principal',
                'vertices': [[0, 0], [8, 0], [8, 5], [0, 5]],
                'obstacles': [],
                'roofType': 'flat',
                'pitchDeg': 15,
                'facingAzimuthDeg': 0,
                'neededPanels': 10,
                'neededAuto': True,
            }],
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        pans_geo = devis.roof_layout.get('_pans_geometry')
        self.assertIsNotNone(pans_geo)
        self.assertEqual(len(pans_geo), 1)
        self.assertEqual(pans_geo[0]['azimut_deg'], 0)
        self.assertEqual(pans_geo[0]['orientation'], 'Sud')

    def test_legacy_layout_without_zones_has_no_pans_geometry(self):
        """A legacy layout (no zones/areas) should NOT add _pans_geometry."""
        layout = {
            'scenario': 'reseau',
            'result': {'panels': 8, 'kwc': 4.4, 'annualKwh': 7000},
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        # No zones → extract_roof_config returns {} → no _pans_geometry.
        self.assertNotIn('_pans_geometry', devis.roof_layout or {})

    def test_company_scoping_respected(self):
        """_pans_geometry does not leak cross-tenant data."""
        other = make_company('qj21-other')
        layout = make_multi_pan_layout()
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        self.assertEqual(devis.company_id, self.company.id)
        self.assertNotEqual(devis.company_id, other.id)
        # Geometry data contains no company-identifying information.
        pans_geo = devis.roof_layout['_pans_geometry']
        for pan in pans_geo:
            self.assertNotIn('company', pan)
