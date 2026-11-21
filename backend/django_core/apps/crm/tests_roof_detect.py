"""Tests for QJ25 — OSM building-footprint roof-outline auto-detection.

All external HTTP calls are mocked; the real Overpass API is never contacted.

Test coverage:
  (a) Mocked Overpass building way → returns polygon vertices.
  (b) Overpass error / timeout → returns None (graceful degradation).
  (c) No building found (empty elements) → returns [].
  (d) Company scoping: another company's lead returns 404.
  (e) Lead with no GPS pin returns 409 (ERR-ENF11-FUZZ-CRM).
  (f) a corrected gps_lat/gps_lng (different from roof_point) wins (QJR598).
  (g) gps_lat/gps_lng used when roof_point is absent.
"""

import sys
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

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

    def test_user_agent_identifie(self):
        """ACAL421 — Overpass rend HTTP 406 à l'User-Agent par défaut de
        python-requests : la requête porte un User-Agent identifié, générique
        (aucun nom ni adresse de personne)."""
        fake_requests = _fake_requests_success(_SAMPLE_OVERPASS_EMPTY)

        with patch.dict(sys.modules, {"requests": fake_requests}):
            fetch_building_footprint(33.5731, -7.5898)

        entetes = fake_requests.post.call_args.kwargs.get("headers") or {}
        agent = entetes.get("User-Agent", "")
        self.assertTrue(agent.startswith("solar-erp-calepinage/"), agent)
        self.assertNotIn("TAQINOR", agent.upper())  # marque blanche (SCA29)
        self.assertNotIn("@", agent)


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

    def test_no_gps_returns_409(self):
        """(e) Lead has neither roof_point nor gps_lat/lng → 409."""
        lead = self._lead()
        self.assertEqual(self._get(lead.pk).status_code, 409)

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
        # ACAL421 — un échec réseau n'est jamais présenté comme « aucun
        # bâtiment » : le message nomme OpenStreetMap injoignable.
        self.assertNotEqual(data["message"], rv._MSG_NO_BUILDING)
        self.assertEqual(data["message"], rv._MSG_OSM_INJOIGNABLE)
        self.assertNotIn("Aucun bâtiment", data["message"])

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


# ---------------------------------------------------------------------------
# ACAL421 — la recherche en TÂCHE DE FOND (décision fondateur du 21/11/2026)
# ---------------------------------------------------------------------------


class DelaiTacheTests(SimpleTestCase):
    """Le chemin synchrone garde 5 s ; la tâche passe 60 s à Overpass."""

    def test_delai_synchrone_inchange_et_delai_tache(self):
        from apps.crm import roof_detect as rd

        fake = _fake_requests_success(_SAMPLE_OVERPASS_EMPTY)
        with patch.dict(sys.modules, {"requests": fake}):
            fetch_building_footprint(33.5731, -7.5898)
            fetch_building_footprint(33.5731, -7.5898,
                                     delai_s=rd.DELAI_TACHE_S)
        synchrone, tache = fake.post.call_args_list
        self.assertEqual(synchrone.kwargs["timeout"], (3, 5))
        self.assertIn("[timeout:5]", synchrone.kwargs["data"]["data"])
        self.assertEqual(tache.kwargs["timeout"], (10, 60))
        self.assertIn("[timeout:60]", tache.kwargs["data"]["data"])

    def test_corps_recherche_deux_refus_distincts(self):
        from apps.crm.roof_views import corps_recherche

        injoignable = corps_recherche(None)
        vide = corps_recherche({"polygon": [],
                                "batiment": batiment_non_renseigne("x")})
        pret = corps_recherche({"polygon": [{"lat": 1, "lng": 2}] * 3,
                                "batiment": batiment_non_renseigne("x")})
        self.assertEqual((injoignable["statut"], injoignable["motif"]),
                         ("refus", "osm_injoignable"))
        self.assertEqual((vide["statut"], vide["motif"]),
                         ("refus", "aucun_batiment"))
        self.assertNotEqual(injoignable["message"], vide["message"])
        self.assertEqual((pret["statut"], len(pret["polygon"])), ("pret", 3))


class RechercheEmpriseEnFondTests(TestCase):
    """POST lance le job (202), GET dit en_cours / pret / refus nommé."""

    POLYGONE = [{"lat": 33.5731, "lng": -7.5898},
                {"lat": 33.5732, "lng": -7.5897},
                {"lat": 33.5733, "lng": -7.5898}]
    _lead = LeadRoofFootprintViewTests._lead

    def setUp(self):
        LeadRoofFootprintViewTests.setUp(self)
        from erp_agentique.celery import app as celery_app

        prev = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        self.addCleanup(setattr, celery_app.conf, "task_always_eager", prev)
        from apps.crm import roof_detect as rd

        pause = patch.object(rd, "PAUSE_ENTRE_ESSAIS_S", 0)
        pause.start()
        self.addCleanup(pause.stop)

    def _lancer(self, lead_id, fetch):
        from apps.crm import roof_detect as rd

        with patch.object(rd, "fetch_building_footprint",
                          side_effect=fetch) as appel:
            reponse = self.api.post(
                f"/api/django/crm/leads/{lead_id}/roof-footprint/recherche/",
                {}, format="json")
        return reponse, appel

    def _statut(self, job_id, api=None):
        return (api or self.api).get(
            f"/api/django/crm/leads/roof-footprint/recherche/{job_id}/")

    def test_contour_pret_par_la_tache(self):
        lead = self._lead(roof_point={"lat": 33.5731, "lng": -7.5898})
        reponse, appel = self._lancer(lead.pk, lambda lat, lng, delai_s: {
            "polygon": self.POLYGONE, "batiment": batiment_non_renseigne("x")})
        self.assertEqual(reponse.status_code, 202)
        corps = reponse.json()
        self.assertEqual(corps["statut"], "en_cours")
        self.assertEqual(appel.call_args.kwargs["delai_s"], 60)
        statut = self._statut(corps["job_id"])
        self.assertEqual(statut.status_code, 200)
        self.assertEqual(statut.json()["statut"], "pret")
        self.assertEqual(statut.json()["polygon"], self.POLYGONE)

    def test_essais_bornes_puis_refus_osm_injoignable(self):
        lead = self._lead(roof_point={"lat": 33.5731, "lng": -7.5898})
        reponse, appel = self._lancer(lead.pk,
                                      lambda lat, lng, delai_s: None)
        self.assertEqual(appel.call_count, 2)
        corps = self._statut(reponse.json()["job_id"]).json()
        self.assertEqual((corps["statut"], corps["motif"]),
                         ("refus", "osm_injoignable"))

    def test_second_essai_reussit(self):
        lead = self._lead(roof_point={"lat": 33.5731, "lng": -7.5898})
        issues = iter([None, {"polygon": self.POLYGONE,
                              "batiment": batiment_non_renseigne("x")}])
        reponse, appel = self._lancer(lead.pk,
                                      lambda lat, lng, delai_s: next(issues))
        self.assertEqual(appel.call_count, 2)
        self.assertEqual(
            self._statut(reponse.json()["job_id"]).json()["statut"], "pret")

    def test_aucun_batiment_nomme(self):
        lead = self._lead(roof_point={"lat": 33.5731, "lng": -7.5898})
        reponse, _ = self._lancer(lead.pk, lambda lat, lng, delai_s: {
            "polygon": [], "batiment": batiment_non_renseigne("x")})
        corps = self._statut(reponse.json()["job_id"]).json()
        self.assertEqual((corps["statut"], corps["motif"]),
                         ("refus", "aucun_batiment"))

    def test_gardes_404_409_et_job_d_un_autre(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        etranger = self._lead(company=self.autre,
                              roof_point={"lat": 33.5, "lng": -7.5})
        reponse, appel = self._lancer(etranger.pk, lambda *a, **k: None)
        self.assertEqual(reponse.status_code, 404)
        appel.assert_not_called()
        sans_epingle = self._lancer(self._lead().pk, lambda *a, **k: None)[0]
        self.assertEqual(sans_epingle.status_code, 409)
        lead = self._lead(roof_point={"lat": 33.5731, "lng": -7.5898})
        job_id = self._lancer(lead.pk, lambda *a, **k: None)[0].json()["job_id"]
        collegue = get_user_model().objects.create_user(
            username='roof-collegue', password='x', company=self.company,
            role_legacy='responsable')
        autre_api = APIClient()
        autre_api.force_authenticate(collegue)
        self.assertEqual(self._statut(job_id, autre_api).status_code, 404)

    def test_file_injoignable_503(self):
        lead = self._lead(roof_point={"lat": 33.5731, "lng": -7.5898})
        with patch("core.jobs.submit", side_effect=RuntimeError("broker")):
            reponse = self.api.post(
                f"/api/django/crm/leads/{lead.pk}/roof-footprint/recherche/",
                {}, format="json")
        self.assertEqual(reponse.status_code, 503)
