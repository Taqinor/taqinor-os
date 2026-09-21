"""Tests CONTRAT9 — ClauseContrat (clauses résolues, ordonnées, surchargeables).

Couvre :
- Création depuis une clause-source : titre/corps RÉSOLUS côté serveur.
- Création ad hoc (sans source) : titre/corps obligatoires.
- Surcharge : éditer le texte d'une clause sourcée pose ``surchargee=True``,
  ``surchargee`` n'est jamais piloté depuis le corps de requête.
- Ordre : tri par ``ordre`` au sein d'un contrat.
- Company posée côté serveur (jamais depuis le corps).
- Isolation multi-tenant (société A ne voit pas / ne lie pas pour société B).
- Unicité conditionnelle (contrat+clause) ; clauses ad hoc multiples permises.
- Filtres : ?contrat=, ?clause=, ?surchargee=.
- Accès réservé aux Responsables/Administrateurs (rôle normal → 403).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import Clause, ClauseContrat, Contrat

User = get_user_model()

BASE = "/api/django/contrats/clauses-contrat/"


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


def make_contrat(company, objet="Contrat O&M", **kwargs):
    return Contrat.objects.create(company=company, objet=objet, **kwargs)


def make_clause(company, titre="Clause type résiliation", **kwargs):
    defaults = {
        "type_clause": "resiliation",
        "corps": "Préavis de 30 jours requis avant résiliation.",
        "actif": True,
        "ordre": 0,
    }
    defaults.update(kwargs)
    return Clause.objects.create(company=company, titre=titre, **defaults)


# ---------------------------------------------------------------------------
# Création depuis clause-source : résolution côté serveur
# ---------------------------------------------------------------------------

class ClauseContratResolutionTests(TestCase):
    """Le texte est matérialisé depuis la clause-source quand non fourni."""

    def setUp(self):
        self.co = make_company("cc-resol", "Resol")
        self.admin = make_user(self.co, "cc-resol-admin", role="admin")
        self.contrat = make_contrat(self.co)
        self.clause = make_clause(
            self.co, titre="Résiliation", corps="Préavis de 30 jours."
        )

    def test_resolves_titre_corps_from_source(self):
        """Sans titre/corps fournis, ils sont copiés depuis la clause-source."""
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {"contrat": self.contrat.id, "clause": self.clause.id, "ordre": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ClauseContrat.objects.get(id=resp.data["id"])
        self.assertEqual(obj.titre, "Résiliation")
        self.assertEqual(obj.corps, "Préavis de 30 jours.")
        self.assertFalse(obj.surchargee)

    def test_company_forced_server_side(self):
        """La company est posée côté serveur, jamais depuis le corps."""
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {"contrat": self.contrat.id, "clause": self.clause.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ClauseContrat.objects.get(id=resp.data["id"])
        self.assertEqual(obj.company, self.co)

    def test_clause_titre_exposed_read_only(self):
        """Le titre de la clause-source est renvoyé en lecture seule."""
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {"contrat": self.contrat.id, "clause": self.clause.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["clause_titre"], "Résiliation")

    def test_explicit_text_overrides_at_create(self):
        """Un corps fourni différent de la source marque surchargee=True."""
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {
                "contrat": self.contrat.id,
                "clause": self.clause.id,
                "corps": "Préavis ramené à 15 jours (négocié).",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ClauseContrat.objects.get(id=resp.data["id"])
        self.assertTrue(obj.surchargee)
        self.assertEqual(obj.corps, "Préavis ramené à 15 jours (négocié).")
        # Le titre, non fourni, reste résolu depuis la source.
        self.assertEqual(obj.titre, "Résiliation")

    def test_surchargee_not_driven_from_body(self):
        """surchargee est en lecture seule : ignoré depuis le corps."""
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {
                "contrat": self.contrat.id,
                "clause": self.clause.id,
                "surchargee": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ClauseContrat.objects.get(id=resp.data["id"])
        # Texte identique à la source → reste False malgré le corps.
        self.assertFalse(obj.surchargee)


# ---------------------------------------------------------------------------
# Création ad hoc (sans clause-source)
# ---------------------------------------------------------------------------

class ClauseContratAdHocTests(TestCase):
    """Clause saisie directement sur le contrat (sans source en bibliothèque)."""

    def setUp(self):
        self.co = make_company("cc-adhoc", "AdHoc")
        self.admin = make_user(self.co, "cc-adhoc-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_create_adhoc_requires_titre_and_corps(self):
        """Sans clause-source, titre et corps sont obligatoires."""
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {"contrat": self.contrat.id, "ordre": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_create_adhoc_with_text(self):
        """Une clause ad hoc complète est créée (clause source NULL)."""
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {
                "contrat": self.contrat.id,
                "titre": "Clause spéciale chantier",
                "corps": "Accès au site limité aux heures ouvrées.",
                "ordre": 2,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ClauseContrat.objects.get(id=resp.data["id"])
        self.assertIsNone(obj.clause_id)
        self.assertEqual(obj.titre, "Clause spéciale chantier")

    def test_multiple_adhoc_allowed_on_same_contrat(self):
        """Plusieurs clauses ad hoc (clause=NULL) sont permises sur un contrat."""
        ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, clause=None,
            titre="Ad hoc 1", corps="Texte 1", ordre=1,
        )
        ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, clause=None,
            titre="Ad hoc 2", corps="Texte 2", ordre=2,
        )
        self.assertEqual(
            ClauseContrat.objects.filter(
                contrat=self.contrat, clause__isnull=True
            ).count(),
            2,
        )


# ---------------------------------------------------------------------------
# Surcharge à la mise à jour
# ---------------------------------------------------------------------------

class ClauseContratUpdateTests(TestCase):
    """Éditer le texte d'une clause sourcée pose surchargee=True."""

    def setUp(self):
        self.co = make_company("cc-upd", "Upd")
        self.admin = make_user(self.co, "cc-upd-admin", role="admin")
        self.contrat = make_contrat(self.co)
        self.clause = make_clause(
            self.co, titre="Garantie", corps="Garantie 10 ans.",
            type_clause="garantie",
        )
        self.cc = ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, clause=self.clause,
            titre="Garantie", corps="Garantie 10 ans.", ordre=0,
        )

    def test_patch_corps_sets_surchargee(self):
        api = auth(self.admin)
        resp = api.patch(
            f"{BASE}{self.cc.id}/",
            {"corps": "Garantie portée à 12 ans."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.cc.refresh_from_db()
        self.assertTrue(self.cc.surchargee)
        self.assertEqual(self.cc.corps, "Garantie portée à 12 ans.")

    def test_patch_back_to_source_text_clears_surcharge(self):
        """Remettre exactement le texte de la source repasse surchargee=False."""
        self.cc.corps = "Garantie modifiée."
        self.cc.surchargee = True
        self.cc.save()
        api = auth(self.admin)
        resp = api.patch(
            f"{BASE}{self.cc.id}/",
            {"corps": "Garantie 10 ans."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.cc.refresh_from_db()
        self.assertFalse(self.cc.surchargee)


# ---------------------------------------------------------------------------
# Ordre
# ---------------------------------------------------------------------------

class ClauseContratOrderingTests(TestCase):
    """Les clauses d'un contrat sont triées par ordre."""

    def setUp(self):
        self.co = make_company("cc-ord", "Ord")
        self.admin = make_user(self.co, "cc-ord-admin", role="admin")
        self.contrat = make_contrat(self.co)
        self.c3 = ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, titre="C3",
            corps="x", ordre=3,
        )
        self.c1 = ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, titre="C1",
            corps="x", ordre=1,
        )
        self.c2 = ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, titre="C2",
            corps="x", ordre=2,
        )

    def test_list_ordered_by_ordre(self):
        api = auth(self.admin)
        resp = api.get(f"{BASE}?contrat={self.contrat.id}&ordering=ordre")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertEqual(ids, [self.c1.id, self.c2.id, self.c3.id])


# ---------------------------------------------------------------------------
# Unicité conditionnelle
# ---------------------------------------------------------------------------

class ClauseContratUniquenessTests(TestCase):
    """Une clause-source n'est rattachée qu'une fois par contrat."""

    def setUp(self):
        self.co = make_company("cc-uniq", "Uniq")
        self.admin = make_user(self.co, "cc-uniq-admin", role="admin")
        self.contrat = make_contrat(self.co)
        self.clause = make_clause(self.co, titre="Confidentialité")

    def test_duplicate_source_clause_rejected(self):
        ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, clause=self.clause,
            titre="Confidentialité", corps="x", ordre=0,
        )
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {"contrat": self.contrat.id, "clause": self.clause.id},
            format="json",
        )
        self.assertIn(resp.status_code, [400, 409], resp.data)

    def test_same_source_clause_on_different_contrats_ok(self):
        """La même clause-source peut être posée sur deux contrats distincts."""
        contrat2 = make_contrat(self.co, objet="Contrat 2")
        ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, clause=self.clause,
            titre="Confidentialité", corps="x", ordre=0,
        )
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {"contrat": contrat2.id, "clause": self.clause.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)


# ---------------------------------------------------------------------------
# Isolation multi-tenant
# ---------------------------------------------------------------------------

class ClauseContratIsolationTests(TestCase):
    """Société A ne voit pas / ne lie pas pour société B."""

    def setUp(self):
        self.co_a = make_company("cc-iso-a", "A")
        self.co_b = make_company("cc-iso-b", "B")
        self.admin_a = make_user(self.co_a, "cc-iso-admin-a", role="admin")
        self.admin_b = make_user(self.co_b, "cc-iso-admin-b", role="admin")
        self.contrat_a = make_contrat(self.co_a)
        self.cc_a = ClauseContrat.objects.create(
            company=self.co_a, contrat=self.contrat_a, titre="A",
            corps="x", ordre=0,
        )

    def test_list_returns_only_own_company(self):
        contrat_b = make_contrat(self.co_b)
        cc_b = ClauseContrat.objects.create(
            company=self.co_b, contrat=contrat_b, titre="B", corps="x", ordre=0,
        )
        api_b = auth(self.admin_b)
        resp = api_b.get(BASE)
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(cc_b.id, ids)
        self.assertNotIn(self.cc_a.id, ids)

    def test_detail_of_other_company_404(self):
        api_b = auth(self.admin_b)
        resp = api_b.get(f"{BASE}{self.cc_a.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_cross_company_contrat_rejected(self):
        """admin_b ne peut pas rattacher une clause à un contrat de société A."""
        api_b = auth(self.admin_b)
        resp = api_b.post(
            BASE,
            {
                "contrat": self.contrat_a.id,
                "titre": "Hijack",
                "corps": "x",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_cross_company_clause_source_rejected(self):
        """Une clause-source d'une autre société est refusée."""
        contrat_b = make_contrat(self.co_b)
        clause_a = make_clause(self.co_a, titre="Clause de A")
        api_b = auth(self.admin_b)
        resp = api_b.post(
            BASE,
            {"contrat": contrat_b.id, "clause": clause_a.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)


# ---------------------------------------------------------------------------
# Filtres
# ---------------------------------------------------------------------------

class ClauseContratFiltresTests(TestCase):
    """Filtres ?contrat=, ?clause=, ?surchargee=."""

    def setUp(self):
        self.co = make_company("cc-filt", "Filt")
        self.admin = make_user(self.co, "cc-filt-admin", role="admin")
        self.contrat1 = make_contrat(self.co, objet="C1")
        self.contrat2 = make_contrat(self.co, objet="C2")
        self.clause = make_clause(self.co, titre="Source")
        self.cc1 = ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat1, clause=self.clause,
            titre="Source", corps="x", ordre=0, surchargee=False,
        )
        self.cc2 = ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat2, titre="Ad hoc",
            corps="y", ordre=0, surchargee=True,
        )

    def test_filter_by_contrat(self):
        api = auth(self.admin)
        resp = api.get(f"{BASE}?contrat={self.contrat1.id}")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(self.cc1.id, ids)
        self.assertNotIn(self.cc2.id, ids)

    def test_filter_by_clause(self):
        api = auth(self.admin)
        resp = api.get(f"{BASE}?clause={self.clause.id}")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(self.cc1.id, ids)
        self.assertNotIn(self.cc2.id, ids)

    def test_filter_by_surchargee(self):
        api = auth(self.admin)
        resp = api.get(f"{BASE}?surchargee=true")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(self.cc2.id, ids)
        self.assertNotIn(self.cc1.id, ids)


# ---------------------------------------------------------------------------
# Contrôle d'accès
# ---------------------------------------------------------------------------

class ClauseContratAccessTests(TestCase):
    """Accès réservé aux Responsables et Administrateurs."""

    def setUp(self):
        self.co = make_company("cc-access", "Acc")
        self.normal = make_user(self.co, "cc-access-normal", role="normal")

    def test_role_normal_refuse_liste(self):
        api = auth(self.normal)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 403)

    def test_role_normal_refuse_creation(self):
        api = auth(self.normal)
        resp = api.post(
            BASE,
            {"titre": "x", "corps": "y"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
