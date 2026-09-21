"""Tests CONTRAT8 — Clause (bibliothèque de clauses réutilisables).

Couvre :
- Création d'une Clause (company posée côté serveur, jamais depuis le corps).
- Isolation multi-tenant (société A ne voit pas les clauses de société B).
- CRUD basique (liste, détail, mise à jour, suppression).
- Filtres : ?actif=, ?type_clause=, ?categorie=.
- Recherche plein texte : ?search=.
- Liaison ModeleContratClause : attacher/détacher une clause d'un gabarit,
  avec ordre, unicité (modele+clause), et isolation multi-tenant.
- Accès réservé aux Responsables/Administrateurs (rôle normal → 403).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import Clause, ModeleContrat, ModeleContratClause

User = get_user_model()

BASE_CLAUSES = "/api/django/contrats/clauses/"
BASE_MC_CLAUSES = "/api/django/contrats/modele-clauses/"


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


def make_clause(company, titre="Clause type résiliation", **kwargs):
    defaults = {
        "type_clause": "resiliation",
        "corps": "En cas de résiliation anticipée, un préavis de 30 jours est requis.",
        "actif": True,
        "ordre": 0,
    }
    defaults.update(kwargs)
    return Clause.objects.create(company=company, titre=titre, **defaults)


def make_modele(company, nom="Gabarit O&M", **kwargs):
    defaults = {
        "type_contrat_defaut": "om",
        "corps": "Corps O&M.",
        "clauses": "",
        "actif": True,
        "ordre": 0,
    }
    defaults.update(kwargs)
    return ModeleContrat.objects.create(company=company, nom=nom, **defaults)


# ---------------------------------------------------------------------------
# Tests de création (company posée côté serveur)
# ---------------------------------------------------------------------------

class ClauseCreateTests(TestCase):
    """La company est toujours posée côté serveur, jamais depuis le corps."""

    def setUp(self):
        self.co = make_company("cl-create", "Create")
        self.admin = make_user(self.co, "cl-create-admin", role="admin")

    def _payload(self, **kwargs):
        payload = {
            "titre": "Clause de résiliation anticipée",
            "type_clause": "resiliation",
            "corps": "Préavis de 30 jours.",
        }
        payload.update(kwargs)
        return payload

    def test_create_forces_company_server_side(self):
        """La company est posée côté serveur même si le client en fournit une autre."""
        api = auth(self.admin)
        resp = api.post(BASE_CLAUSES, self._payload(), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Clause.objects.get(id=resp.data["id"])
        self.assertEqual(obj.company, self.co)

    def test_create_sets_default_values(self):
        """Les valeurs par défaut (actif=True, ordre=0) s'appliquent."""
        api = auth(self.admin)
        resp = api.post(BASE_CLAUSES, self._payload(), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Clause.objects.get(id=resp.data["id"])
        self.assertTrue(obj.actif)
        self.assertEqual(obj.ordre, 0)

    def test_create_with_all_fields(self):
        """Création avec tous les champs optionnels."""
        api = auth(self.admin)
        payload = self._payload(
            categorie="Conditions générales",
            type_clause="garantie",
            ordre=3,
            actif=False,
        )
        resp = api.post(BASE_CLAUSES, payload, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Clause.objects.get(id=resp.data["id"])
        self.assertEqual(obj.categorie, "Conditions générales")
        self.assertEqual(obj.type_clause, "garantie")
        self.assertEqual(obj.ordre, 3)
        self.assertFalse(obj.actif)

    def test_display_field_in_response(self):
        """Le champ type_clause_display est renvoyé en lecture seule."""
        api = auth(self.admin)
        resp = api.post(BASE_CLAUSES, self._payload(), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn("type_clause_display", resp.data)
        self.assertEqual(resp.data["type_clause"], "resiliation")
        self.assertEqual(resp.data["type_clause_display"], "Résiliation")

    def test_corps_required(self):
        """Le champ corps est obligatoire."""
        api = auth(self.admin)
        payload = {"titre": "Sans corps", "type_clause": "generale"}
        resp = api.post(BASE_CLAUSES, payload, format="json")
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Tests d'isolation multi-tenant
# ---------------------------------------------------------------------------

class ClauseIsolationTests(TestCase):
    """Société A ne voit pas les clauses de société B."""

    def setUp(self):
        self.co_a = make_company("cl-iso-a", "A")
        self.co_b = make_company("cl-iso-b", "B")
        self.admin_a = make_user(self.co_a, "cl-iso-admin-a", role="admin")
        self.admin_b = make_user(self.co_b, "cl-iso-admin-b", role="admin")
        self.clause_a = make_clause(self.co_a, titre="Clause A")
        self.clause_b = make_clause(self.co_b, titre="Clause B")

    def test_list_returns_only_own_company_clauses(self):
        """La liste ne renvoie que les clauses de la société de l'utilisateur."""
        api_b = auth(self.admin_b)
        resp = api_b.get(BASE_CLAUSES)
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(self.clause_b.id, ids)
        self.assertNotIn(self.clause_a.id, ids)

    def test_detail_of_other_company_returns_404(self):
        """Le détail d'une clause d'une autre société renvoie 404."""
        api_b = auth(self.admin_b)
        resp = api_b.get(f"{BASE_CLAUSES}{self.clause_a.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_update_other_company_returns_404(self):
        """La mise à jour d'une clause d'une autre société renvoie 404."""
        api_b = auth(self.admin_b)
        resp = api_b.patch(
            f"{BASE_CLAUSES}{self.clause_a.id}/",
            {"titre": "Tentative hijack"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_other_company_returns_404(self):
        """La suppression d'une clause d'une autre société renvoie 404."""
        api_b = auth(self.admin_b)
        resp = api_b.delete(f"{BASE_CLAUSES}{self.clause_a.id}/")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Tests de filtres et recherche
# ---------------------------------------------------------------------------

class ClauseFiltresTests(TestCase):
    """Filtres ?actif=, ?type_clause=, ?categorie= et recherche ?search=."""

    def setUp(self):
        self.co = make_company("cl-filtres", "F")
        self.admin = make_user(self.co, "cl-filtres-admin", role="admin")
        self.c_actif = make_clause(
            self.co,
            titre="Clause garantie active",
            type_clause="garantie",
            categorie="Conditions générales",
            actif=True,
        )
        self.c_inactif = make_clause(
            self.co,
            titre="Clause résiliation inactive",
            type_clause="resiliation",
            categorie="Résiliation",
            actif=False,
        )

    def test_filtre_actif_true(self):
        api = auth(self.admin)
        resp = api.get(f"{BASE_CLAUSES}?actif=true")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(self.c_actif.id, ids)
        self.assertNotIn(self.c_inactif.id, ids)

    def test_filtre_actif_false(self):
        api = auth(self.admin)
        resp = api.get(f"{BASE_CLAUSES}?actif=false")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertNotIn(self.c_actif.id, ids)
        self.assertIn(self.c_inactif.id, ids)

    def test_filtre_type_clause(self):
        api = auth(self.admin)
        resp = api.get(f"{BASE_CLAUSES}?type_clause=garantie")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(self.c_actif.id, ids)
        self.assertNotIn(self.c_inactif.id, ids)

    def test_filtre_categorie(self):
        api = auth(self.admin)
        resp = api.get(f"{BASE_CLAUSES}?categorie=g%C3%A9n%C3%A9rales")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(self.c_actif.id, ids)
        self.assertNotIn(self.c_inactif.id, ids)

    def test_search_by_titre(self):
        api = auth(self.admin)
        resp = api.get(f"{BASE_CLAUSES}?search=garantie+active")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(self.c_actif.id, ids)
        self.assertNotIn(self.c_inactif.id, ids)


# ---------------------------------------------------------------------------
# Tests de liaison ModeleContratClause
# ---------------------------------------------------------------------------

class ModeleContratClauseTests(TestCase):
    """Liaison ordonnée ModeleContrat ↔ Clause."""

    def setUp(self):
        self.co = make_company("mc-clause", "MC")
        self.admin = make_user(self.co, "mc-clause-admin", role="admin")
        self.modele = make_modele(self.co)
        self.clause1 = make_clause(self.co, titre="Clause 1", ordre=1)
        self.clause2 = make_clause(self.co, titre="Clause 2", ordre=2)

    def _link_payload(self, modele_id, clause_id, ordre=0):
        return {"modele": modele_id, "clause": clause_id, "ordre": ordre}

    def test_create_link(self):
        """On peut lier une clause à un gabarit avec un ordre."""
        api = auth(self.admin)
        resp = api.post(
            BASE_MC_CLAUSES,
            self._link_payload(self.modele.id, self.clause1.id, ordre=1),
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            ModeleContratClause.objects.filter(
                modele=self.modele, clause=self.clause1
            ).exists()
        )

    def test_company_forced_server_side(self):
        """La company de la liaison est posée côté serveur."""
        api = auth(self.admin)
        resp = api.post(
            BASE_MC_CLAUSES,
            self._link_payload(self.modele.id, self.clause1.id),
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        lien = ModeleContratClause.objects.get(id=resp.data["id"])
        self.assertEqual(lien.company, self.co)

    def test_duplicate_link_rejected(self):
        """On ne peut pas lier deux fois la même clause au même gabarit."""
        ModeleContratClause.objects.create(
            company=self.co,
            modele=self.modele,
            clause=self.clause1,
            ordre=0,
        )
        api = auth(self.admin)
        resp = api.post(
            BASE_MC_CLAUSES,
            self._link_payload(self.modele.id, self.clause1.id, ordre=5),
            format="json",
        )
        self.assertIn(resp.status_code, [400, 409])

    def test_filter_by_modele(self):
        """Le filtre ?modele= renvoie uniquement les clauses du gabarit."""
        mc1 = ModeleContratClause.objects.create(
            company=self.co, modele=self.modele, clause=self.clause1, ordre=1
        )
        mc2 = ModeleContratClause.objects.create(
            company=self.co, modele=self.modele, clause=self.clause2, ordre=2
        )
        api = auth(self.admin)
        resp = api.get(f"{BASE_MC_CLAUSES}?modele={self.modele.id}")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(mc1.id, ids)
        self.assertIn(mc2.id, ids)

    def test_delete_link(self):
        """On peut supprimer une liaison."""
        lien = ModeleContratClause.objects.create(
            company=self.co, modele=self.modele, clause=self.clause1, ordre=0
        )
        api = auth(self.admin)
        resp = api.delete(f"{BASE_MC_CLAUSES}{lien.id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(ModeleContratClause.objects.filter(id=lien.id).exists())

    def test_cross_company_modele_rejected(self):
        """On ne peut pas lier la clause d'une autre société."""
        co_b = make_company("mc-clause-b", "B")
        admin_b = make_user(co_b, "mc-clause-admin-b", role="admin")
        modele_b = make_modele(co_b, nom="Gabarit B")
        clause_a = make_clause(self.co, titre="Clause société A")

        # admin_b essaie d'utiliser un modele de la société B avec une clause de A.
        api_b = auth(admin_b)
        resp = api_b.post(
            BASE_MC_CLAUSES,
            self._link_payload(modele_b.id, clause_a.id),
            format="json",
        )
        # La clause clause_a n'appartient pas à co_b → rejet.
        self.assertEqual(resp.status_code, 400)

    def test_cross_company_isolation_list(self):
        """La liste des liaisons ne renvoie que celles de la société de l'utilisateur."""
        co_b = make_company("mc-clause-iso-b", "B")
        admin_b = make_user(co_b, "mc-clause-iso-admin-b", role="admin")
        modele_b = make_modele(co_b, nom="Gabarit B")
        clause_b = make_clause(co_b, titre="Clause B")
        lien_a = ModeleContratClause.objects.create(
            company=self.co, modele=self.modele, clause=self.clause1, ordre=0
        )
        lien_b = ModeleContratClause.objects.create(
            company=co_b, modele=modele_b, clause=clause_b, ordre=0
        )

        api_b = auth(admin_b)
        resp = api_b.get(BASE_MC_CLAUSES)
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(lien_b.id, ids)
        self.assertNotIn(lien_a.id, ids)


# ---------------------------------------------------------------------------
# Tests de contrôle d'accès
# ---------------------------------------------------------------------------

class ClauseAccessTests(TestCase):
    """Accès réservé aux Responsables et Administrateurs."""

    def setUp(self):
        self.co = make_company("cl-access", "Acc")
        self.normal = make_user(self.co, "cl-access-normal", role="normal")

    def test_role_normal_refuse_liste_clauses(self):
        api = auth(self.normal)
        resp = api.get(BASE_CLAUSES)
        self.assertEqual(resp.status_code, 403)

    def test_role_normal_refuse_creation_clause(self):
        api = auth(self.normal)
        resp = api.post(
            BASE_CLAUSES,
            {"titre": "Tentative", "type_clause": "generale", "corps": "x"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_role_normal_refuse_liste_mc_clauses(self):
        api = auth(self.normal)
        resp = api.get(BASE_MC_CLAUSES)
        self.assertEqual(resp.status_code, 403)
