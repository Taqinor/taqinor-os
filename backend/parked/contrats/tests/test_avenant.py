"""Tests CONTRAT24 — Avenant (amendement de contrat → nouvelle version immuable).

Couvre :
- ``creer_avenant`` crée un avenant ET fige un nouvel instantané immuable
  (``VersionContrat`` — CONTRAT18), et relie l'avenant à la version créée
  (``version_creee``).
- La numérotation s'incrémente par contrat (1, 2, 3…) et est INDÉPENDANTE entre
  contrats.
- La numérotation utilise ``max(numero)+1`` (jamais ``count()+1``) : après une
  suppression DB d'un avenant intermédiaire, le suivant NE réutilise PAS un
  numéro déjà attribué.
- ``montant_delta`` est appliqué à ``Contrat.montant`` quand fourni (et ne touche
  pas le montant quand absent).
- Le ``Contrat.statut`` n'est JAMAIS modifié (préservation des statuts).
- Multi-tenant : avenants scopés société ; endpoints scopés société ; numéro,
  société et auteur posés CÔTÉ SERVEUR (jamais lus du corps).
- Endpoints : creer-avenant / lister (+ accès réservé au palier admin/responsable).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.models import (
    Avenant,
    Contrat,
    PartieContrat,
    VersionContrat,
)

User = get_user_model()

CONTRATS = "/api/django/contrats/contrats/"
AVENANTS = "/api/django/contrats/avenants/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def make_contrat(company, statut="actif", objet="Contrat test",
                 montant="80000"):
    contrat = Contrat.objects.create(
        company=company, objet=objet, montant=Decimal(montant),
        type_contrat="vente", statut=statut,
        date_debut=timezone.localdate() - timedelta(days=30))
    PartieContrat.objects.create(
        company=company, contrat=contrat,
        type_partie="client", nom="Client SARL", ordre=0)
    PartieContrat.objects.create(
        company=company, contrat=contrat,
        type_partie="prestataire", nom="Taqinor", ordre=1)
    return contrat


# ---------------------------------------------------------------------------
# Service — avenant fige une version + numérotation + delta
# ---------------------------------------------------------------------------

class CreerAvenantServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("av-svc", "AvSvc")
        self.user = make_user(self.co, "av-svc-admin", role="admin")
        self.contrat = make_contrat(self.co, objet="Contrat solaire 12 kWc")

    def test_cree_avenant_et_fige_une_version(self):
        a = services.creer_avenant(
            self.contrat, objet="Extension toiture", auteur=self.user)
        self.assertEqual(a.numero, 1)
        self.assertEqual(a.objet, "Extension toiture")
        self.assertEqual(a.company_id, self.co.id)
        self.assertEqual(a.cree_par_id, self.user.id)
        # Un instantané immuable a été figé ET relié à l'avenant.
        self.assertIsNotNone(a.version_creee)
        versions = VersionContrat.objects.filter(contrat=self.contrat)
        self.assertEqual(versions.count(), 1)
        self.assertEqual(a.version_creee_id, versions.first().id)
        # Le motif de la version porte le n° + l'objet de l'avenant.
        self.assertIn("Avenant n°1", a.version_creee.motif)
        self.assertIn("Extension toiture", a.version_creee.motif)
        # Le contenu figé reflète le contrat (corps fusionné).
        self.assertIn("Contrat solaire 12 kWc", a.version_creee.contenu)

    def test_objet_requis(self):
        with self.assertRaises(ValueError):
            services.creer_avenant(self.contrat, objet="   ", auteur=self.user)

    def test_numerotation_incrementale_par_contrat(self):
        a1 = services.creer_avenant(self.contrat, objet="A", auteur=self.user)
        a2 = services.creer_avenant(self.contrat, objet="B", auteur=self.user)
        a3 = services.creer_avenant(self.contrat, objet="C", auteur=self.user)
        self.assertEqual([a1.numero, a2.numero, a3.numero], [1, 2, 3])

    def test_numerotation_independante_entre_contrats(self):
        autre = make_contrat(self.co, objet="Autre contrat")
        services.creer_avenant(self.contrat, objet="A", auteur=self.user)
        services.creer_avenant(self.contrat, objet="B", auteur=self.user)
        a_autre = services.creer_avenant(autre, objet="X", auteur=self.user)
        # Le second contrat redémarre à 1, indépendant du premier.
        self.assertEqual(a_autre.numero, 1)

    def test_numerotation_max_plus_1_pas_count_plus_1(self):
        """``max(numero)+1`` et non ``count()+1`` : après suppression DB d'un
        avenant INTERMÉDIAIRE, on ne réutilise pas un numéro déjà attribué."""
        services.creer_avenant(self.contrat, objet="A", auteur=self.user)  # 1
        a2 = services.creer_avenant(
            self.contrat, objet="B", auteur=self.user)  # 2
        services.creer_avenant(self.contrat, objet="C", auteur=self.user)  # 3
        # Purge DB d'un avenant intermédiaire (l'API ne le permet pas).
        a2.delete()
        # Rows restantes : {1, 3} → count()=2 → count()+1 = 3 (COLLISION avec
        # l'avenant 3 existant). max(numero)+1 = 4 (correct, pas de collision).
        a_next = services.creer_avenant(
            self.contrat, objet="D", auteur=self.user)
        self.assertEqual(a_next.numero, 4)

    def test_montant_delta_applique_au_contrat(self):
        a = services.creer_avenant(
            self.contrat, objet="Ajout 2 panneaux",
            montant_delta=Decimal("15000"), auteur=self.user)
        self.contrat.refresh_from_db()
        # 80000 + 15000 = 95000.
        self.assertEqual(self.contrat.montant, Decimal("95000"))
        self.assertEqual(a.montant_delta, Decimal("15000"))

    def test_montant_delta_negatif(self):
        services.creer_avenant(
            self.contrat, objet="Retrait équipement",
            montant_delta=Decimal("-5000"), auteur=self.user)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.montant, Decimal("75000"))

    def test_sans_delta_le_montant_est_inchange(self):
        services.creer_avenant(
            self.contrat, objet="Avenant rédactionnel", auteur=self.user)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.montant, Decimal("80000"))

    def test_ne_touche_pas_le_statut(self):
        """Préservation des statuts (CONTRAT12) : un avenant ne change jamais le
        ``Contrat.statut``."""
        services.creer_avenant(
            self.contrat, objet="Extension",
            montant_delta=Decimal("1000"), auteur=self.user)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, "actif")

    def test_champs_optionnels(self):
        date_effet = timezone.localdate() + timedelta(days=10)
        a = services.creer_avenant(
            self.contrat, objet="Prolongation",
            description="Détail de la modification contractuelle.",
            date_effet=date_effet, auteur=self.user)
        self.assertEqual(a.description,
                         "Détail de la modification contractuelle.")
        self.assertEqual(a.date_effet, date_effet)


# ---------------------------------------------------------------------------
# Sélecteur — lecture seule, ordonnée, scopée société
# ---------------------------------------------------------------------------

class AvenantsSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("av-sel", "AvSel")
        self.user = make_user(self.co, "av-sel-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_avenants_ordonnes_recent_en_tete(self):
        services.creer_avenant(self.contrat, objet="A", auteur=self.user)
        services.creer_avenant(self.contrat, objet="B", auteur=self.user)
        services.creer_avenant(self.contrat, objet="C", auteur=self.user)
        nums = list(
            selectors.avenants_contrat(self.contrat)
            .values_list("numero", flat=True))
        self.assertEqual(nums, [3, 2, 1])

    def test_scope_societe(self):
        autre_co = make_company("av-sel-2", "AvSel2")
        autre = make_contrat(autre_co)
        services.creer_avenant(self.contrat, objet="A", auteur=self.user)
        services.creer_avenant(autre, objet="X")
        # Le sélecteur d'un contrat ne renvoie que SES avenants.
        self.assertEqual(selectors.avenants_contrat(self.contrat).count(), 1)


# ---------------------------------------------------------------------------
# API — creer-avenant / lister / scope / rôle
# ---------------------------------------------------------------------------

class AvenantApiTests(TestCase):
    def setUp(self):
        self.co = make_company("av-api", "AvApi")
        self.admin = make_user(self.co, "av-api-admin", role="admin")
        self.contrat = make_contrat(self.co, objet="Contrat API test")

    def test_creer_avenant_endpoint(self):
        api = auth(self.admin)
        url = f"{CONTRATS}{self.contrat.id}/creer-avenant/"
        res = api.post(
            url, {"objet": "Extension", "montant_delta": "10000"},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["numero"], 1)
        self.assertEqual(res.data["objet"], "Extension")
        self.assertIsNotNone(res.data["version_creee"])
        # Le montant du contrat a été ajusté côté serveur.
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.montant, Decimal("90000"))

    def test_numero_pose_cote_serveur_pas_du_corps(self):
        """Un ``numero`` envoyé dans le corps est IGNORÉ : le serveur calcule
        ``max+1`` (l'avenant ne peut pas être falsifié par le client)."""
        api = auth(self.admin)
        url = f"{CONTRATS}{self.contrat.id}/creer-avenant/"
        res = api.post(
            url, {"objet": "A", "numero": 99, "company": 12345},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["numero"], 1)  # pas 99
        a = Avenant.objects.get(id=res.data["id"])
        self.assertEqual(a.company_id, self.co.id)  # pas 12345

    def test_objet_requis_400(self):
        api = auth(self.admin)
        url = f"{CONTRATS}{self.contrat.id}/creer-avenant/"
        res = api.post(url, {"objet": "   "}, format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_lister_avenants_par_contrat(self):
        api = auth(self.admin)
        url = f"{CONTRATS}{self.contrat.id}/creer-avenant/"
        api.post(url, {"objet": "A"}, format="json")
        api.post(url, {"objet": "B"}, format="json")
        res = api.get(f"{CONTRATS}{self.contrat.id}/avenants/")
        self.assertEqual(res.status_code, 200)
        nums = [a["numero"] for a in res.data]
        self.assertEqual(nums, [2, 1])

    def test_viewset_avenants_lecture_seule(self):
        """La ressource ``/avenants/`` n'autorise NI création NI modification NI
        suppression (créés uniquement via l'action du contrat)."""
        a = services.creer_avenant(
            self.contrat, objet="A", auteur=self.admin)
        api = auth(self.admin)
        res_post = api.post(
            AVENANTS, {"contrat": self.contrat.id, "objet": "X", "numero": 5},
            format="json")
        self.assertEqual(res_post.status_code, 405, res_post.content)
        detail = f"{AVENANTS}{a.id}/"
        self.assertEqual(
            api.put(detail, {"objet": "x"}, format="json").status_code, 405)
        self.assertEqual(
            api.patch(detail, {"objet": "x"}, format="json").status_code, 405)
        self.assertEqual(api.delete(detail).status_code, 405)
        self.assertEqual(api.get(detail).status_code, 200)

    def test_scope_societe_endpoint(self):
        autre_co = make_company("av-api-2", "AvApi2")
        autre_admin = make_user(autre_co, "av-api-2-admin", role="admin")
        services.creer_avenant(self.contrat, objet="A", auteur=self.admin)
        api = auth(autre_admin)
        res = api.get(f"{AVENANTS}?contrat={self.contrat.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 0)
        self.assertEqual(res.data["results"], [])
        # Et l'action creer-avenant est 404 sur un contrat hors société.
        res2 = api.post(
            f"{CONTRATS}{self.contrat.id}/creer-avenant/", {"objet": "X"},
            format="json")
        self.assertEqual(res2.status_code, 404)

    def test_role_gate_refuse_non_privilegie(self):
        commercial = make_user(self.co, "av-api-com", role="commercial")
        api = auth(commercial)
        res = api.post(
            f"{CONTRATS}{self.contrat.id}/creer-avenant/", {"objet": "X"},
            format="json")
        self.assertEqual(res.status_code, 403, res.content)
        res2 = api.get(AVENANTS)
        self.assertEqual(res2.status_code, 403)

    def test_numerotation_sequentielle_sous_repetition(self):
        """Plusieurs appels successifs produisent des numéros distincts et
        croissants (séquentiel, jamais de doublon)."""
        api = auth(self.admin)
        url = f"{CONTRATS}{self.contrat.id}/creer-avenant/"
        numeros = []
        for i in range(5):
            res = api.post(url, {"objet": f"Avenant {i}"}, format="json")
            self.assertEqual(res.status_code, 201, res.content)
            numeros.append(res.data["numero"])
        self.assertEqual(numeros, [1, 2, 3, 4, 5])
        # Unicité garantie (contrainte DB + max+1).
        self.assertEqual(len(set(numeros)), 5)
