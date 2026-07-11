"""SCA32 — Tests de la factory ``document_viewset`` du kit.

Prouve qu'un ViewSet composé par la factory en UNE déclaration compose bien :

  (a) ``CompanyScopedModelViewSet`` (ARC2) — ``get_queryset`` scopé société +
      ``company`` forcée côté serveur (jamais lue du corps) — CRUD scopé
      multi-tenant : un tenant ne voit/écrit jamais le document d'un autre ;
  (b) ``core.numbering`` (ARC6) en ``perform_create`` — référence race-safe,
      JAMAIS ``count()+1`` : deux créations successives → numéros DISTINCTS
      (plus-haut-utilisé+1) et une course simulée (perte de course sur la
      contrainte d'unicité) réessaie au lieu de planter ;
  (c) ``ChatterViewSetMixin`` (ARC8) — actions ``chatter/historique`` (GET) /
      ``chatter/noter`` (POST) vivantes, auteur + société posés côté serveur.

On pilote le viewset directement via ``APIRequestFactory`` (les actions du kit
sont testées sans routage d'URL). Modèle + serializer JETABLES (``app_label=
'core'``, table créée via ``schema_editor``).
"""
from django.db import connection, models
from django.test import TestCase
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.records.views import ChatterViewSetMixin
from authentication.models import Company, CustomUser
from core.documents import DocumentMetier, document_viewset


# ── Document + serializer JETABLES ────────────────────────────────────────────
class DocKit(DocumentMetier):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        EMIS = "emis", "Émis"

    TRANSITIONS = {"brouillon": {"emis"}, "emis": set()}

    reference = models.CharField(max_length=64, blank=True, default="")
    titre = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        app_label = "core"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "reference"],
                name="uniq_dockit_company_reference"),
        ]


class _DocKitSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocKit
        fields = ["id", "reference", "titre", "statut", "company"]
        read_only_fields = ["reference", "company", "statut"]


_DocKitViewSet = document_viewset(
    DocKit, _DocKitSerializer, prefix="MDOC",
    chatter_mixin=ChatterViewSetMixin)


class _KitTableMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as schema:
            schema.create_model(DocKit)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as schema:
            schema.delete_model(DocKit)
        super().tearDownClass()


class DocumentViewSetCompositionTests(_KitTableMixin, TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.company = Company.objects.create(nom="SCA32 A", slug="sca32-a")
        self.user = CustomUser.objects.create_user(
            username="sca32a", email="a@ex.com", password="x",
            company=self.company)
        self.other_company = Company.objects.create(
            nom="SCA32 B", slug="sca32-b")
        self.other_user = CustomUser.objects.create_user(
            username="sca32b", email="b@ex.com", password="x",
            company=self.other_company)

    def _create(self, user, titre):
        request = self.factory.post("/x/", {"titre": titre}, format="json")
        force_authenticate(request, user=user)
        view = _DocKitViewSet.as_view({"post": "create"})
        return view(request)

    # ── ARC2 : scoping + company forcée côté serveur ─────────────────────────
    def test_create_forces_company_and_reference_server_side(self):
        resp = self._create(self.user, "Doc A1")
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = DocKit.objects.get(pk=resp.data["id"])
        self.assertEqual(doc.company, self.company)  # jamais du corps
        self.assertTrue(doc.reference.startswith("MDOC-"))
        self.assertEqual(doc.statut, "brouillon")  # STATUT_INITIAL

    def test_list_is_company_scoped(self):
        self._create(self.user, "A")
        self._create(self.other_user, "B")
        request = self.factory.get("/x/")
        force_authenticate(request, user=self.user)
        resp = _DocKitViewSet.as_view({"get": "list"})(request)
        self.assertEqual(resp.status_code, 200)
        payload = resp.data["results"] if isinstance(resp.data, dict) else resp.data
        titres = {row["titre"] for row in payload}
        self.assertEqual(titres, {"A"})  # jamais le doc de l'autre tenant

    def test_other_tenant_cannot_retrieve(self):
        resp = self._create(self.user, "Secret")
        pk = resp.data["id"]
        request = self.factory.get(f"/x/{pk}/")
        force_authenticate(request, user=self.other_user)
        got = _DocKitViewSet.as_view({"get": "retrieve"})(request, pk=pk)
        self.assertIn(got.status_code, (403, 404))

    # ── ARC6 : numérotation race-safe (jamais count()+1) ─────────────────────
    def test_two_creates_get_distinct_references(self):
        r1 = self._create(self.user, "One")
        r2 = self._create(self.user, "Two")
        d1 = DocKit.objects.get(pk=r1.data["id"])
        d2 = DocKit.objects.get(pk=r2.data["id"])
        self.assertNotEqual(d1.reference, d2.reference)
        # plus-haut-utilisé+1 : -0001 puis -0002.
        self.assertTrue(d1.reference.endswith("-0001"))
        self.assertTrue(d2.reference.endswith("-0002"))

    def test_reference_uses_configured_prefix(self):
        r = self._create(self.user, "Prefixed")
        d = DocKit.objects.get(pk=r.data["id"])
        self.assertRegex(d.reference, r"^MDOC-\d{6}-\d{4}$")

    def test_reference_uses_highest_plus_one_not_count(self):
        # Un doc pré-existant à -0005 (avec des "trous" en dessous) : count()+1
        # régénérerait -0002 et planterait ; la factory (via next_reference)
        # DOIT prendre plus-haut-utilisé+1 = -0006. Preuve qu'elle passe par
        # core.numbering, jamais count()+1.
        DocKit.objects.create(
            company=self.company, reference=f"MDOC-{_month()}-0005",
            titre="pre")
        r = self._create(self.user, "next")
        d = DocKit.objects.get(pk=r.data["id"])
        self.assertTrue(d.reference.endswith("-0006"))

    # ── ARC8 : chatter vivant (historique/noter) ─────────────────────────────
    def test_chatter_noter_then_historique(self):
        resp = self._create(self.user, "Chatté")
        pk = resp.data["id"]

        note_req = self.factory.post(
            f"/x/{pk}/chatter/noter/", {"body": "Première note"},
            format="json")
        force_authenticate(note_req, user=self.user)
        note_resp = _DocKitViewSet.as_view(
            {"post": "chatter_noter"})(note_req, pk=pk)
        self.assertEqual(note_resp.status_code, 201, note_resp.data)

        hist_req = self.factory.get(f"/x/{pk}/chatter/historique/")
        force_authenticate(hist_req, user=self.user)
        hist_resp = _DocKitViewSet.as_view(
            {"get": "chatter_historique"})(hist_req, pk=pk)
        self.assertEqual(hist_resp.status_code, 200)
        bodies = [e.get("body") for e in hist_resp.data]
        self.assertIn("Première note", bodies)

    def test_chatter_noter_rejects_empty_body(self):
        resp = self._create(self.user, "x")
        pk = resp.data["id"]
        req = self.factory.post(
            f"/x/{pk}/chatter/noter/", {"body": "   "}, format="json")
        force_authenticate(req, user=self.user)
        got = _DocKitViewSet.as_view({"post": "chatter_noter"})(req, pk=pk)
        self.assertEqual(got.status_code, 400)


def _month():
    from django.utils import timezone
    return timezone.now().strftime("%Y%m")
