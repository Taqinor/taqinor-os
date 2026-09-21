"""Tests FLOTTE27 — Point d'intégration télématique (no-op sans fournisseur).

Couvre :
- Modèle ``ReleveTelematique`` :
  - création manuelle simple + valeurs par défaut (source='manuel') ;
  - validations ``clean`` (actif d'une autre société, odomètre/heures négatifs,
    carburant hors 0–100 %).
- Service ``telematique_active`` / ``synchroniser_releves`` :
  - ``telematique_active()`` faux par défaut (KEY-GATED, off) ;
  - ``synchroniser_releves`` est un NO-OP : renvoie 0, ne lève pas, ne crée
    aucun relevé (aucun appel réseau / dépendance) ;
  - reste no-op même drapeau ``TELEMATIQUE_ENABLED`` activé tant qu'aucun
    fournisseur n'est câblé.
- Selector ``releves_telematiques_de_la_societe`` : scope société + filtres.
- Endpoints API ``/releves-telematiques/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - actif d'une autre société refusé ;
  - filtres ``?actif_flotte=`` / ``?source=`` ;
  - action ``synchroniser`` no-op (active=False, importes=0).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    ReleveTelematique,
    Vehicule,
)
from apps.flotte.selectors import releves_telematiques_de_la_societe
from apps.flotte.services import synchroniser_releves, telematique_active

User = get_user_model()

URL = "/api/django/flotte/releves-telematiques/"
SYNC_URL = URL + "synchroniser/"

H = datetime.datetime(2026, 6, 1, 8, 0, 0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


def make_actif(company, immat="TEL-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


# ── Modèle : création manuelle + validations ───────────────────────────────────

class ReleveTelematiqueModelTests(TestCase):
    def setUp(self):
        self.co = make_company("tel-model", "Tel Model")
        self.actif = make_actif(self.co, "TMOD")

    def test_creation_manuelle_defaults(self):
        r = ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif, horodatage=H,
            odometre="12345.5")
        self.assertEqual(r.source, ReleveTelematique.Source.MANUEL)
        self.assertEqual(r.raw_payload, {})
        self.assertIsNone(r.position_lat)
        self.assertIsNone(r.heures_moteur)

    def test_actif_autre_societe_rejete(self):
        autre = make_company("tel-model-b", "Tel Model B")
        actif_b = make_actif(autre, "B")
        r = ReleveTelematique(
            company=self.co, actif_flotte=actif_b, horodatage=H)
        with self.assertRaises(ValidationError):
            r.full_clean()

    def test_odometre_negatif_rejete(self):
        r = ReleveTelematique(
            company=self.co, actif_flotte=self.actif, horodatage=H,
            odometre=-1)
        with self.assertRaises(ValidationError):
            r.full_clean()

    def test_heures_moteur_negatif_rejete(self):
        r = ReleveTelematique(
            company=self.co, actif_flotte=self.actif, horodatage=H,
            heures_moteur=-1)
        with self.assertRaises(ValidationError):
            r.full_clean()

    def test_carburant_hors_bornes_rejete(self):
        r = ReleveTelematique(
            company=self.co, actif_flotte=self.actif, horodatage=H,
            niveau_carburant="150.0")
        with self.assertRaises(ValidationError):
            r.full_clean()


# ── Service : no-op gating (default off) ───────────────────────────────────────

class TelematiqueServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("tel-svc", "Tel Svc")

    def test_inactive_par_defaut(self):
        # KEY-GATED : aucune clé/flag → fonctionnalité désactivée.
        self.assertFalse(telematique_active())

    def test_synchroniser_noop_renvoie_zero(self):
        # No-op total : 0 relevé importé, aucune exception, aucune création.
        avant = ReleveTelematique.objects.count()
        self.assertEqual(synchroniser_releves(self.co), 0)
        self.assertEqual(ReleveTelematique.objects.count(), avant)

    @override_settings(TELEMATIQUE_ENABLED=True)
    def test_reste_noop_sans_fournisseur_cable(self):
        # Drapeau activé mais aucun module fournisseur câblé → toujours no-op.
        self.assertFalse(telematique_active())
        self.assertEqual(synchroniser_releves(self.co), 0)


# ── Selector : scope société + filtres ─────────────────────────────────────────

class TelematiqueSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("tel-sel", "Tel Sel")
        self.actif = make_actif(self.co, "TSEL")
        self.r1 = ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif, horodatage=H,
            source=ReleveTelematique.Source.MANUEL)
        self.r2 = ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif,
            horodatage=H - datetime.timedelta(days=1),
            source=ReleveTelematique.Source.TELEMATIQUE)

    def test_scope_societe(self):
        autre = make_company("tel-sel-b", "Tel Sel B")
        actif_b = make_actif(autre, "B")
        ReleveTelematique.objects.create(
            company=autre, actif_flotte=actif_b, horodatage=H)
        self.assertEqual(
            releves_telematiques_de_la_societe(self.co).count(), 2)
        self.assertEqual(
            releves_telematiques_de_la_societe(autre).count(), 1)

    def test_filtre_par_source(self):
        qs = releves_telematiques_de_la_societe(
            self.co, source=ReleveTelematique.Source.TELEMATIQUE)
        self.assertEqual([r.id for r in qs], [self.r2.id])

    def test_filtre_par_actif(self):
        actif2 = make_actif(self.co, "TSEL-2")
        autre = ReleveTelematique.objects.create(
            company=self.co, actif_flotte=actif2, horodatage=H)
        qs = releves_telematiques_de_la_societe(
            self.co, actif_flotte_id=actif2.id)
        self.assertEqual([r.id for r in qs], [autre.id])


# ── API : CRUD scopé + role gate + filtres + synchro no-op ─────────────────────

class TelematiqueApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("tel-a", "Tel A")
        self.co_b = make_company("tel-b", "Tel B")
        self.admin_a = make_user(self.co_a, "tel-admin-a", "admin")
        self.user_a = make_user(self.co_a, "tel-user-a", "normal")
        self.actif = make_actif(self.co_a, "API")

    def test_create_manuel_company_server_side(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "horodatage": "2026-06-01T08:00:00Z",
            "odometre": "12345.0",
            "niveau_carburant": "80.0",
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        r = ReleveTelematique.objects.get()
        self.assertEqual(r.company_id, self.co_a.id)
        self.assertEqual(resp.data["source"], "manuel")
        self.assertIn("source_display", resp.data)
        self.assertIn("actif_label", resp.data)

    def test_create_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "actif_flotte": self.actif.id,
            "horodatage": "2026-06-01T08:00:00Z",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(ReleveTelematique.objects.count(), 0)

    def test_actif_autre_societe_refuse(self):
        actif_b = make_actif(self.co_b, "B")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": actif_b.id,
            "horodatage": "2026-06-01T08:00:00Z",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_scoped_and_read_any_role(self):
        ReleveTelematique.objects.create(
            company=self.co_a, actif_flotte=self.actif, horodatage=H)
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "tel-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL)), [])

    def test_update_and_delete(self):
        r = ReleveTelematique.objects.create(
            company=self.co_a, actif_flotte=self.actif, horodatage=H)
        resp = auth(self.admin_a).patch(
            f"{URL}{r.id}/", {"odometre": "99999.0"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        r.refresh_from_db()
        self.assertEqual(str(r.odometre), "99999.0")
        resp = auth(self.admin_a).delete(f"{URL}{r.id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(ReleveTelematique.objects.count(), 0)

    def test_filtre_par_source(self):
        ReleveTelematique.objects.create(
            company=self.co_a, actif_flotte=self.actif, horodatage=H,
            source="manuel")
        ReleveTelematique.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            horodatage=H - datetime.timedelta(days=1), source="telematique")
        resp = auth(self.admin_a).get(f"{URL}?source=telematique")
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_par_actif_flotte(self):
        actif2 = make_actif(self.co_a, "API-2")
        ReleveTelematique.objects.create(
            company=self.co_a, actif_flotte=self.actif, horodatage=H)
        ReleveTelematique.objects.create(
            company=self.co_a, actif_flotte=actif2, horodatage=H)
        resp = auth(self.admin_a).get(f"{URL}?actif_flotte={self.actif.id}")
        self.assertEqual(len(rows(resp)), 1)

    def test_synchroniser_noop(self):
        # KEY-GATED : aucune synchro réelle, aucun relevé importé.
        resp = auth(self.admin_a).post(SYNC_URL, {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data["active"])
        self.assertEqual(resp.data["importes"], 0)
        self.assertEqual(ReleveTelematique.objects.count(), 0)

    def test_synchroniser_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(SYNC_URL, {}, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
