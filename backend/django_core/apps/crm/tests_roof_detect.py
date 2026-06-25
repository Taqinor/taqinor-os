"""Tests for QJ25 — OSM building-footprint roof-outline auto-detection.

All external HTTP calls are mocked; the real Overpass API is never contacted.

Test coverage:
  (a) Mocked Overpass building way → returns polygon vertices.
  (b) Overpass error / timeout → returns None (graceful degradation).
  (c) No building found (empty elements) → returns [].
  (d) Company scoping: another company's lead returns 404.
  (e) Lead with no GPS pin returns 400.
  (f) roof_point preferred over gps_lat/gps_lng.
  (g) gps_lat/gps_lng used when roof_point is absent.
"""

import json
import sys
from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory
from rest_framework.test import force_authenticate

from apps.crm.roof_detect import fetch_building_footprint, _parse_geometry


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
        result = _parse_geometry(_SAMPLE_OVERPASS_WAY)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], {"lat": 33.5731, "lng": -7.5898})
        self.assertEqual(result[1], {"lat": 33.5732, "lng": -7.5897})

    def test_empty_elements_returns_empty_list(self):
        result = _parse_geometry(_SAMPLE_OVERPASS_EMPTY)
        self.assertEqual(result, [])

    def test_way_without_geometry_key_skipped(self):
        data = {"elements": [{"type": "way", "id": 1}]}
        self.assertEqual(_parse_geometry(data), [])

    def test_node_type_elements_skipped(self):
        data = {
            "elements": [
                {"type": "node", "id": 1, "lat": 33.0, "lon": -7.0},
            ]
        }
        self.assertEqual(_parse_geometry(data), [])

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
        self.assertEqual(_parse_geometry(data), [])

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
        result = _parse_geometry(data)
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
        self.assertGreaterEqual(len(result), 3)
        self.assertIn("lat", result[0])
        self.assertIn("lng", result[0])

    def test_network_error_returns_none(self):
        """(b) Overpass timeout/error → returns None."""
        fake_requests = MagicMock()
        fake_requests.post.side_effect = Exception("Connection timeout")

        with patch.dict(sys.modules, {"requests": fake_requests}):
            result = fetch_building_footprint(33.5731, -7.5898)

        self.assertIsNone(result)

    def test_no_building_returns_empty_list(self):
        """(c) No building near the pin → returns []."""
        fake_requests = _fake_requests_success(_SAMPLE_OVERPASS_EMPTY)

        with patch.dict(sys.modules, {"requests": fake_requests}):
            result = fetch_building_footprint(33.5731, -7.5898)

        self.assertEqual(result, [])

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

class LeadRoofFootprintViewTests(TestCase):
    """Integration-style tests for lead_roof_footprint view (mocked Lead ORM)."""

    def setUp(self):
        self.factory = RequestFactory()

    def _make_request(self, user, lead_id):
        request = self.factory.get(f"/api/django/crm/leads/{lead_id}/roof-footprint/")
        request.user = user
        # DRF (@api_view) ré-exécute l'authentification sur la requête brute :
        # force_authenticate fait respecter l'utilisateur au lieu de retomber
        # sur AnonymousUser (sinon 401 avant d'atteindre la vue).
        force_authenticate(request, user=user)
        return request

    def _company_user(self):
        company = MagicMock()
        company.pk = 1
        user = MagicMock()
        user.is_authenticated = True
        user.company = company
        return user

    def test_company_scoped_returns_polygon(self):
        """(a+d) Correct company + mocked fetch → 200 with polygon."""
        user = self._company_user()

        lead = MagicMock()
        lead.roof_point = {"lat": 33.5731, "lng": -7.5898}
        lead.gps_lat = None
        lead.gps_lng = None

        polygon = [
            {"lat": 33.5731, "lng": -7.5898},
            {"lat": 33.5732, "lng": -7.5897},
            {"lat": 33.5733, "lng": -7.5898},
        ]

        with patch("apps.crm.models.Lead.objects") as mock_mgr:
            mock_mgr.get.return_value = lead
            request = self._make_request(user, 42)
            from apps.crm import roof_views as rv
            with patch.object(rv, "fetch_building_footprint", return_value=polygon):
                response = rv.lead_roof_footprint(request, lead_id=42)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["source"], "osm")
        self.assertEqual(len(data["polygon"]), 3)

    def test_wrong_company_returns_404(self):
        """(d) Lead belongs to company_b; user is company_a → 404."""
        user = self._company_user()

        from apps.crm.models import Lead

        with patch("apps.crm.models.Lead.objects") as mock_mgr:
            mock_mgr.get.side_effect = Lead.DoesNotExist
            request = self._make_request(user, 99)
            from apps.crm import roof_views as rv
            response = rv.lead_roof_footprint(request, lead_id=99)

        self.assertEqual(response.status_code, 404)

    def test_no_gps_returns_400(self):
        """(e) Lead has neither roof_point nor gps_lat/lng → 400."""
        user = self._company_user()

        lead = MagicMock()
        lead.roof_point = None
        lead.gps_lat = None
        lead.gps_lng = None

        with patch("apps.crm.models.Lead.objects") as mock_mgr:
            mock_mgr.get.return_value = lead
            request = self._make_request(user, 7)
            from apps.crm import roof_views as rv
            response = rv.lead_roof_footprint(request, lead_id=7)

        self.assertEqual(response.status_code, 400)

    def test_overpass_failure_returns_empty_polygon(self):
        """(b) Overpass unreachable → 200 with empty polygon + message."""
        user = self._company_user()

        lead = MagicMock()
        lead.roof_point = {"lat": 33.5731, "lng": -7.5898}
        lead.gps_lat = None
        lead.gps_lng = None

        with patch("apps.crm.models.Lead.objects") as mock_mgr:
            mock_mgr.get.return_value = lead
            request = self._make_request(user, 5)
            from apps.crm import roof_views as rv
            with patch.object(rv, "fetch_building_footprint", return_value=None):
                response = rv.lead_roof_footprint(request, lead_id=5)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["polygon"], [])
        self.assertIn("message", data)

    def test_roof_point_preferred_over_gps_fields(self):
        """(f) roof_point takes priority over gps_lat/gps_lng."""
        user = self._company_user()

        lead = MagicMock()
        lead.roof_point = {"lat": 33.9999, "lng": -7.9999}
        lead.gps_lat = 33.0000  # should NOT be used
        lead.gps_lng = -7.0000

        captured = []

        def mock_fetch(lat, lng):
            captured.append((lat, lng))
            return []

        with patch("apps.crm.models.Lead.objects") as mock_mgr:
            mock_mgr.get.return_value = lead
            request = self._make_request(user, 3)
            from apps.crm import roof_views as rv
            with patch.object(rv, "fetch_building_footprint", side_effect=mock_fetch):
                rv.lead_roof_footprint(request, lead_id=3)

        self.assertAlmostEqual(captured[0][0], 33.9999)
        self.assertAlmostEqual(captured[0][1], -7.9999)

    def test_gps_fields_used_when_no_roof_point(self):
        """(g) When roof_point is absent, gps_lat/gps_lng are used."""
        user = self._company_user()

        lead = MagicMock()
        lead.roof_point = None
        lead.gps_lat = 33.1234
        lead.gps_lng = -7.4321

        captured = []

        def mock_fetch(lat, lng):
            captured.append((lat, lng))
            return []

        with patch("apps.crm.models.Lead.objects") as mock_mgr:
            mock_mgr.get.return_value = lead
            request = self._make_request(user, 4)
            from apps.crm import roof_views as rv
            with patch.object(rv, "fetch_building_footprint", side_effect=mock_fetch):
                rv.lead_roof_footprint(request, lead_id=4)

        self.assertAlmostEqual(captured[0][0], 33.1234)
        self.assertAlmostEqual(captured[0][1], -7.4321)
