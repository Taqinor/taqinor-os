"""Tests CONTRAT13 — RegleApprobation (règle d'approbation par montant/type).

Couvre :
- Création d'une règle (company posée côté serveur, jamais depuis le corps).
- Isolation multi-tenant (société A ne voit pas les règles de société B).
- Résolution par montant (intervalle de bornes, bornes ouvertes).
- Résolution par type de contrat (règle ciblée prime sur « tous types »).
- Spécificité : intervalle le plus étroit gagne ; priorité départage.
- Le résolveur est scopé société (jamais la règle d'une autre société).
- Validation des bornes (min ≤ max).
- Accès réservé aux Responsables/Administrateurs (rôle normal → 403).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors
from apps.contrats.models import RegleApprobation

User = get_user_model()

BASE = "/api/django/contrats/regles-approbation/"
RESOUDRE = BASE + "resoudre/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="responsable"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def rows(resp):
    data = resp.data
    return data["results"] if isinstance(data, dict) and "results" in data else data


def make_regle(company, libelle="Règle", **kwargs):
    defaults = {
        "type_contrat": "",
        "montant_min": None,
        "montant_max": None,
        "niveau_approbation": "responsable",
        "nombre_approbateurs": 1,
        "priorite": 0,
        "actif": True,
    }
    defaults.update(kwargs)
    return RegleApprobation.objects.create(
        company=company, libelle=libelle, **defaults)


# ---------------------------------------------------------------------------
# Création — company posée côté serveur
# ---------------------------------------------------------------------------

class RegleCreateTests(TestCase):
    def setUp(self):
        self.co = make_company("ra-create", "Create")
        self.other = make_company("ra-create-other", "Other")
        self.admin = make_user(self.co, "ra-create-admin", role="admin")

    def test_create_pose_company_serveur(self):
        api = auth(self.admin)
        resp = api.post(BASE, {
            "libelle": "Gros contrats",
            "montant_min": "100000.00",
            "niveau_approbation": "administrateur",
            "nombre_approbateurs": 2,
            # Tentative d'injection d'une autre société : doit être ignorée.
            "company": self.other.id,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        regle = RegleApprobation.objects.get(id=resp.data["id"])
        self.assertEqual(regle.company_id, self.co.id)
        self.assertEqual(regle.montant_min, Decimal("100000.00"))

    def test_create_min_sup_max_refuse(self):
        api = auth(self.admin)
        resp = api.post(BASE, {
            "libelle": "Bornes incohérentes",
            "montant_min": "500.00",
            "montant_max": "100.00",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_role_normal_interdit(self):
        normal = make_user(self.co, "ra-create-normal", role="commercial")
        api = auth(normal)
        resp = api.post(BASE, {"libelle": "X"}, format="json")
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Isolation multi-tenant
# ---------------------------------------------------------------------------

class RegleTenantTests(TestCase):
    def setUp(self):
        self.a = make_company("ra-a", "A")
        self.b = make_company("ra-b", "B")
        self.admin_a = make_user(self.a, "ra-a-admin", role="admin")
        self.regle_a = make_regle(self.a, libelle="A")
        self.regle_b = make_regle(self.b, libelle="B")

    def test_liste_scopee_societe(self):
        api = auth(self.admin_a)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in rows(resp)}
        self.assertIn(self.regle_a.id, ids)
        self.assertNotIn(self.regle_b.id, ids)

    def test_detail_autre_societe_404(self):
        api = auth(self.admin_a)
        resp = api.get(f"{BASE}{self.regle_b.id}/")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Résolution — montant / type / spécificité (sélecteur)
# ---------------------------------------------------------------------------

class ResoudreSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("ra-res", "Res")

    def test_resolution_par_montant(self):
        petite = make_regle(
            self.co, libelle="≤ 50k", montant_max=Decimal("50000"),
            niveau_approbation="responsable")
        grosse = make_regle(
            self.co, libelle="> 50k", montant_min=Decimal("50000.01"),
            niveau_approbation="administrateur")
        r = selectors.resoudre_regle_approbation(self.co, Decimal("10000"))
        self.assertEqual(r.id, petite.id)
        r = selectors.resoudre_regle_approbation(self.co, Decimal("80000"))
        self.assertEqual(r.id, grosse.id)

    def test_aucune_regle_couvrante_renvoie_none(self):
        make_regle(self.co, montant_min=Decimal("100000"))
        r = selectors.resoudre_regle_approbation(self.co, Decimal("500"))
        self.assertIsNone(r)

    def test_type_cible_prime_sur_tous_types(self):
        tous = make_regle(
            self.co, libelle="Tous", montant_min=Decimal("0"),
            montant_max=Decimal("1000000"))
        cible = make_regle(
            self.co, libelle="Vente", type_contrat="vente",
            montant_min=Decimal("0"), montant_max=Decimal("1000000"))
        r = selectors.resoudre_regle_approbation(
            self.co, Decimal("5000"), type_contrat="vente")
        self.assertEqual(r.id, cible.id)
        # Un type non ciblé retombe sur la règle « tous types ».
        r = selectors.resoudre_regle_approbation(
            self.co, Decimal("5000"), type_contrat="om")
        self.assertEqual(r.id, tous.id)

    def test_intervalle_plus_etroit_gagne(self):
        large = make_regle(
            self.co, libelle="Large", montant_min=Decimal("0"),
            montant_max=Decimal("1000000"))
        etroite = make_regle(
            self.co, libelle="Étroite", montant_min=Decimal("9000"),
            montant_max=Decimal("11000"))
        r = selectors.resoudre_regle_approbation(self.co, Decimal("10000"))
        self.assertEqual(r.id, etroite.id)
        # Hors de l'intervalle étroit → la large s'applique.
        r = selectors.resoudre_regle_approbation(self.co, Decimal("500000"))
        self.assertEqual(r.id, large.id)

    def test_priorite_departage(self):
        a = make_regle(
            self.co, libelle="P0", montant_min=Decimal("0"),
            montant_max=Decimal("100"), priorite=0)
        b = make_regle(
            self.co, libelle="P5", montant_min=Decimal("0"),
            montant_max=Decimal("100"), priorite=5)
        r = selectors.resoudre_regle_approbation(self.co, Decimal("50"))
        self.assertEqual(r.id, b.id)
        self.assertNotEqual(r.id, a.id)

    def test_regle_inactive_ignoree(self):
        make_regle(
            self.co, libelle="Inactive", montant_max=Decimal("100000"),
            actif=False)
        r = selectors.resoudre_regle_approbation(self.co, Decimal("10000"))
        self.assertIsNone(r)

    def test_resolution_scopee_societe(self):
        autre = make_company("ra-res-autre", "Autre")
        make_regle(autre, libelle="Autre société", montant_max=Decimal("1000000"))
        r = selectors.resoudre_regle_approbation(self.co, Decimal("10000"))
        self.assertIsNone(r)


# ---------------------------------------------------------------------------
# Résolution — endpoint /resoudre/
# ---------------------------------------------------------------------------

class ResoudreEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("ra-ep", "EP")
        self.admin = make_user(self.co, "ra-ep-admin", role="admin")
        self.grosse = make_regle(
            self.co, libelle="> 50k", montant_min=Decimal("50000"),
            niveau_approbation="administrateur", nombre_approbateurs=2)

    def test_resoudre_renvoie_regle(self):
        api = auth(self.admin)
        resp = api.get(RESOUDRE, {"montant": "80000"})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data["regle"])
        self.assertEqual(resp.data["regle"]["id"], self.grosse.id)
        self.assertEqual(resp.data["regle"]["nombre_approbateurs"], 2)

    def test_resoudre_aucune_regle_null(self):
        api = auth(self.admin)
        resp = api.get(RESOUDRE, {"montant": "100"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["regle"])

    def test_resoudre_montant_requis(self):
        api = auth(self.admin)
        resp = api.get(RESOUDRE)
        self.assertEqual(resp.status_code, 400)
