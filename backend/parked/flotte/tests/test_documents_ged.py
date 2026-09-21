"""Tests FLOTTE34 — Documents véhicule (GED).

Couvre :
- Selector ``documents_ged_pour_actif`` :
  - actif sans document lié → queryset vide ;
  - documents GED liés à l'actif (via DocumentLien) remontés, scopés société ;
  - actif d'une autre société → vide.
- Endpoint ``/actifs/<id>/documents/`` (GET, tout rôle).
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.ged.models import Document, DocumentLien
from apps.ged.services import ensure_cabinet, ensure_root_folder
from apps.flotte.models import ActifFlotte, Vehicule
from apps.flotte.selectors import documents_ged_pour_actif

User = get_user_model()


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


def make_actif(company, immat="DOC-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


def make_document(company, nom="Carte grise"):
    cabinet = ensure_cabinet(company, "Flotte")
    folder = ensure_root_folder(company, cabinet=cabinet, nom="Véhicules")
    return Document.objects.create(company=company, folder=folder, nom=nom)


def lier(document, actif):
    ct = ContentType.objects.get_for_model(ActifFlotte)
    return DocumentLien.objects.create(
        document=document, content_type=ct, object_id=actif.id)


class DocumentsGedSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("doc-sel", "Doc Sel")
        self.actif = make_actif(self.co, "DSEL")

    def test_actif_sans_document(self):
        qs = documents_ged_pour_actif(self.co, self.actif.id)
        self.assertEqual(qs.count(), 0)

    def test_documents_lies(self):
        doc = make_document(self.co, "Carte grise")
        lier(doc, self.actif)
        qs = documents_ged_pour_actif(self.co, self.actif.id)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().id, doc.id)

    def test_actif_autre_societe(self):
        autre = make_company("doc-sel-b", "B")
        actif_b = make_actif(autre, "B")
        qs = documents_ged_pour_actif(self.co, actif_b.id)
        self.assertEqual(qs.count(), 0)


class DocumentsGedApiTests(TestCase):
    def test_endpoint(self):
        co = make_company("doc-api", "Doc Api")
        admin = make_user(co, "doc-admin", "admin")
        actif = make_actif(co, "DAPI")
        doc = make_document(co, "Assurance")
        lier(doc, actif)
        api = auth(admin)
        resp = api.get(f"/api/django/flotte/actifs/{actif.id}/documents/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["nom"], "Assurance")
