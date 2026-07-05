"""Tests XFLT23 — OCR reçu carburant -> pré-remplissage du plein (gated).

Couvre :
- Service ``ocr_pleins_active`` : faux par défaut (KEY-GATED, off).
- Service ``extraire_recu_carburant`` : lève ``RuntimeError`` sans clé (jamais
  de no-op silencieux cassant), no-op propre avec octets vides une fois activé.
- Service ``mapper_recu_vers_plein`` : projection des champs bruts OCR vers les
  clés du formulaire ``PleinCarburant`` (mock du service IA — aucune clé
  réelle nécessaire).
- Endpoint ``POST /flotte/pleins/ocr/`` :
  - sans clé -> 503 + message FR clair ;
  - avec clé mockée -> 200 + champs pré-remplis ;
  - photo manquante -> 400 ;
  - lecture accessible à tout rôle (comme les autres actions helper).
"""
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.services import (
    extraire_recu_carburant,
    mapper_recu_vers_plein,
    ocr_pleins_active,
)

User = get_user_model()

URL = "/api/django/flotte/pleins/ocr/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="normal"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


class OcrPleinsServiceTests(TestCase):
    def test_inactive_par_defaut(self):
        # KEY-GATED : aucune clé/flag -> fonctionnalité désactivée.
        self.assertFalse(ocr_pleins_active())

    def test_extraire_sans_cle_leve_runtime_error(self):
        with self.assertRaises(RuntimeError):
            extraire_recu_carburant(b"fake-bytes")

    @override_settings(FLOTTE_OCR_PLEINS_ENABLED=True)
    def test_extraire_active_sans_provider_reste_noop(self):
        # Drapeau activé mais aucun module fournisseur câblé -> dict vide,
        # jamais de crash.
        self.assertEqual(extraire_recu_carburant(b"fake-bytes"), {})

    @override_settings(FLOTTE_OCR_PLEINS_ENABLED=True)
    def test_extraire_bytes_vides_renvoie_vide(self):
        self.assertEqual(extraire_recu_carburant(b""), {})

    def test_mapper_champs_complets(self):
        champs = mapper_recu_vers_plein({
            "date": "2026-06-01",
            "litres": "40.5",
            "prix_unitaire": "12.5",
            "montant": "506.25",
            "station": "Afriquia Ain Sebaa",
        })
        self.assertEqual(champs["date_plein"], "2026-06-01")
        self.assertEqual(champs["quantite"], "40.5")
        self.assertEqual(champs["prix_total"], "506.25")
        self.assertEqual(champs["station"], "Afriquia Ain Sebaa")

    def test_mapper_calcule_montant_si_absent(self):
        champs = mapper_recu_vers_plein({
            "litres": 10, "prix_unitaire": 12.0,
        })
        self.assertEqual(champs["prix_total"], 120.0)

    def test_mapper_vide_renvoie_vide(self):
        self.assertEqual(mapper_recu_vers_plein({}), {})
        self.assertEqual(mapper_recu_vers_plein(None), {})


class OcrPleinsEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("ocr-plein", "OCR Plein")
        self.user = make_user(self.co, "ocr-user")

    def _photo(self):
        f = BytesIO(b"fake-jpeg-bytes")
        f.name = "recu.jpg"
        return f

    def test_sans_cle_503_message_clair(self):
        resp = auth(self.user).post(
            URL, {"photo": self._photo()}, format="multipart")
        self.assertEqual(resp.status_code, 503)
        self.assertIn("OCR indisponible", resp.data["detail"])

    def test_photo_manquante_400(self):
        resp = auth(self.user).post(URL, {}, format="multipart")
        self.assertEqual(resp.status_code, 400)

    @override_settings(FLOTTE_OCR_PLEINS_ENABLED=True)
    def test_avec_cle_mockee_prefill(self):
        mock_champs = {
            "date": "2026-06-01",
            "litres": "35",
            "montant": "420.00",
            "station": "Shell Maarif",
        }
        with patch(
            "apps.flotte.services.extraire_recu_carburant",
            return_value=mock_champs,
        ):
            resp = auth(self.user).post(
                URL, {"photo": self._photo()}, format="multipart")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["champs"]["station"], "Shell Maarif")
        self.assertEqual(resp.data["champs"]["quantite"], "35")

    def test_aucune_creation_automatique(self):
        # L'action ne crée jamais de PleinCarburant, quelle que soit la
        # réponse OCR — l'utilisateur valide toujours ensuite.
        from apps.flotte.models import PleinCarburant
        avant = PleinCarburant.objects.count()
        auth(self.user).post(URL, {"photo": self._photo()}, format="multipart")
        self.assertEqual(PleinCarburant.objects.count(), avant)
