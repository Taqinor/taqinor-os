"""Tests for QJ25 — OSM building-footprint roof-outline auto-detection.

All external HTTP calls are mocked; the real Overpass API is never contacted.

Test coverage:
  (a) Mocked Overpass building way → returns polygon vertices.
  (b) Overpass error / timeout → returns None (graceful degradation).
  (c) No building found (empty elements) → returns [].
  (d) Company scoping: another company's lead returns 404.
  (e) Lead with no GPS pin returns 400.
  (f) a corrected gps_lat/gps_lng (different from roof_point) wins (QJR598).
  (g) gps_lat/gps_lng used when roof_point is absent.
"""

import sys
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.crm.roof_detect import (
    _parse_geometry, batiment_non_renseigne, fetch_building_footprint,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SAMPLE_OVERPASS_WAY = {
    "elements": [
        {
            "type": "way",
            "id": 123456,
            "geometry": [
                {"lat": 33.5731, "lon": -7.5898},
                {"lat": 33.5732, "lon": -7.5897},
                {"lat": 33.5733, "lon": -7.5898},
                {"lat": 33.5731, "lon": -7.5898},
            ],
        }
    ]
}

_SAMPLE_OVERPASS_EMPTY = {"elements": []}


def _fake_requests_success(response_json):
    """Return a fake `requests` module whose .post() returns a successful response."""
    fake = MagicMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = response_json
    fake.post.return_value = mock_resp
    return fake


# ---------------------------------------------------------------------------
# Unit tests for roof_detect._parse_geometry
# ---------------------------------------------------------------------------

class ParseGeometryTests(TestCase):
    """_parse_geometry parses Overpass JSON directly — no HTTP."""

    def test_valid_way_returns_vertices(self):
        result = _parse_geometry(_SAMPLE_OVERPASS_WAY)["polygon"]
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], {"lat": 33.5731, "lng": -7.5898})
        self.assertEqual(result[1], {"lat": 33.5732, "lng": -7.5897})

    def test_empty_elements_returns_empty_list(self):
        result = _parse_geometry(_SAMPLE_OVERPASS_EMPTY)
        self.assertEqual(result["polygon"], [])

    def test_way_without_geometry_key_skipped(self):
        data = {"elements": [{"type": "way", "id": 1}]}
        self.assertEqual(_parse_geometry(data)["polygon"], [])

    def test_node_type_elements_skipped(self):
        data = {
            "elements": [
                {"type": "node", "id": 1, "lat": 33.0, "lon": -7.0},
            ]
        }
        self.assertEqual(_parse_geometry(data)["polygon"], [])

    def test_fewer_than_3_vertices_skipped(self):
        data = {
            "elements": [
                {
                    "type": "way",
                    "id": 1,
                    "geometry": [
                        {"lat": 33.0, "lon": -7.0},
                        {"lat": 33.1, "lon": -7.1},
                    ],
                }
            ]
        }
        self.assertEqual(_parse_geometry(data)["polygon"], [])

    def test_malformed_node_skipped_gracefully(self):
        """First node is malformed (ValueError on float("bad")) — skipped;
        remaining 3 nodes form a valid polygon."""
        data = {
            "elements": [
                {
                    "type": "way",
                    "id": 1,
                    "geometry": [
                        {"lat": "bad", "lon": -7.0},
                        {"lat": 33.1, "lon": -7.1},
                        {"lat": 33.2, "lon": -7.2},
                        {"lat": 33.3, "lon": -7.3},
                    ],
                }
            ]
        }
        result = _parse_geometry(data)["polygon"]
        self.assertEqual(len(result), 3)


# ---------------------------------------------------------------------------
# Unit tests for fetch_building_footprint (HTTP mocked via sys.modules)
# ---------------------------------------------------------------------------

class FetchBuildingFootprintTests(TestCase):
    """fetch_building_footprint — mocks the requests module in sys.modules."""

    def test_building_found_returns_polygon(self):
        """(a) Mocked Overpass building way → returns polygon vertices."""
        fake_requests = _fake_requests_success(_SAMPLE_OVERPASS_WAY)

        with patch.dict(sys.modules, {"requests": fake_requests}):
            result = fetch_building_footprint(33.5731, -7.5898)

        self.assertIsNotNone(result)
        # CALX106 — la fonction rend {"polygon": [...], "batiment": {...}}.
        self.assertGreaterEqual(len(result["polygon"]), 3)
        self.assertIn("lat", result["polygon"][0])
        self.assertIn("lng", result["polygon"][0])
        self.assertIn("batiment", result)

    def test_network_error_returns_none(self):
        """(b) Overpass timeout/error → returns None."""
        fake_requests = MagicMock()
        fake_requests.post.side_effect = Exception("Connection timeout")

        with patch.dict(sys.modules, {"requests": fake_requests}):
            result = fetch_building_footprint(33.5731, -7.5898)

        self.assertIsNone(result)

    def test_no_building_returns_empty_list(self):
        """(c) No building near the pin → returns an empty polygon."""
        fake_requests = _fake_requests_success(_SAMPLE_OVERPASS_EMPTY)

        with patch.dict(sys.modules, {"requests": fake_requests}):
            result = fetch_building_footprint(33.5731, -7.5898)

        self.assertEqual(result["polygon"], [])
        # CALX106 — le bloc `batiment` est servi MÊME sans bâtiment : toutes
        # ses valeurs sont nulles et leur motif est nommé.
        self.assertIsNone(result["batiment"]["height_m"])
        self.assertIsNone(result["batiment"]["source"])

    def test_http_error_status_returns_none(self):
        """HTTP 429 / 503 → raise_for_status raises → returns None."""
        fake_requests = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 429 Too Many Requests")
        fake_requests.post.return_value = mock_resp

        with patch.dict(sys.modules, {"requests": fake_requests}):
            result = fetch_building_footprint(33.5731, -7.5898)

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# View tests (company scoping + endpoint behaviour)
# ---------------------------------------------------------------------------
#
# ALEA38 — these used to mock ``Lead.objects`` and the user (MagicMock), so
# they could not see the permission and scope guards. They now run on REAL
# rows (company, legacy responsable account, lead); only
# ``fetch_building_footprint`` (the outbound Overpass call) is patched.


class LeadRoofFootprintViewTests(TestCase):
    """Endpoint behaviour on real rows; Overpass is the only stand-in."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from authentication.models import Company

        self.company = Company.objects.create(
            nom='Taqinor roof', slug='taqinor-roof-view')
        self.autre = Company.objects.create(
            nom='Autre roof', slug='autre-roof-view')
        self.user = get_user_model().objects.create_user(
            username='roof-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _lead(self, company=None, **champs):
        from apps.crm.models import Lead
        return Lead.objects.create(
            company=company or self.company, nom='Toit', **champs)

    def _get(self, lead_id):
        return self.api.get(f"/api/django/crm/leads/{lead_id}/roof-footprint/")

    def test_company_scoped_returns_polygon(self):
        """(a+d) Correct company + mocked fetch → 200 with polygon."""
        lead = self._lead(roof_point={"lat": 33.5731, "lng": -7.5898})
        polygon = [
            {"lat": 33.5731, "lng": -7.5898},
            {"lat": 33.5732, "lng": -7.5897},
            {"lat": 33.5733, "lng": -7.5898},
        ]
        from apps.crm import roof_views as rv
        empreinte = {"polygon": polygon,
                     "batiment": batiment_non_renseigne("exemple de test")}
        with patch.object(rv, "fetch_building_footprint",
                          return_value=empreinte):
            response = self._get(lead.pk)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "osm")
        self.assertEqual(len(data["polygon"]), 3)
        # CALX106 — la réponse porte toujours le bloc `batiment`.
        self.assertIn("batiment", data)

    def test_wrong_company_returns_404(self):
        """(d) Lead belongs to another company → 404, Overpass untouched."""
        lead = self._lead(company=self.autre,
                          roof_point={"lat": 33.5731, "lng": -7.5898})
        from apps.crm import roof_views as rv
        with patch.object(rv, "fetch_building_footprint") as fetch:
            response = self._get(lead.pk)

        self.assertEqual(response.status_code, 404)
        fetch.assert_not_called()

    def test_no_gps_returns_400(self):
        """(e) Lead has neither roof_point nor gps_lat/lng → 400."""
        lead = self._lead()
        self.assertEqual(self._get(lead.pk).status_code, 400)

    def test_overpass_failure_returns_empty_polygon(self):
        """(b) Overpass unreachable → 200 with empty polygon + message."""
        lead = self._lead(roof_point={"lat": 33.5731, "lng": -7.5898})
        from apps.crm import roof_views as rv
        with patch.object(rv, "fetch_building_footprint", return_value=None):
            response = self._get(lead.pk)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["polygon"], [])
        self.assertIn("message", data)
        # CALX106 — Overpass injoignable : le bloc est servi quand même, tout
        # à `null`, avec le motif qui le dit.
        self.assertIsNone(data["batiment"]["height_m"])
        self.assertIn("height_m", data["batiment"]["non_renseignes"])

    def _captures(self, lead):
        captured = []

        def mock_fetch(lat, lng):
            captured.append((lat, lng))
            return {"polygon": [],
                    "batiment": batiment_non_renseigne("exemple de test")}

        from apps.crm import roof_views as rv
        with patch.object(rv, "fetch_building_footprint",
                          side_effect=mock_fetch):
            self._get(lead.pk)
        return captured

    def test_corrected_gps_preferred_over_roof_point(self):
        """(f) QJR598 — a GPS different from roof_point is a correction: it wins."""
        lead = self._lead(roof_point={"lat": 33.9999, "lng": -7.9999},
                          gps_lat='33.000000', gps_lng='-7.000000')
        captured = self._captures(lead)
        self.assertAlmostEqual(float(captured[0][0]), 33.0)
        self.assertAlmostEqual(float(captured[0][1]), -7.0)

    def test_gps_fields_used_when_no_roof_point(self):
        """(g) When roof_point is absent, gps_lat/gps_lng are used."""
        lead = self._lead(gps_lat='33.123400', gps_lng='-7.432100')
        captured = self._captures(lead)
        self.assertAlmostEqual(float(captured[0][0]), 33.1234)
        self.assertAlmostEqual(float(captured[0][1]), -7.4321)
