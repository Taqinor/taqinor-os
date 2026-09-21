"""Tests CONTRAT18 — VersionContrat (versionnage IMMUABLE des rendus).

Couvre :
- ``creer_version`` fige un instantané du contenu rendu (corps fusionné) et,
  optionnellement, une clé de rendu PDF + un motif.
- La numérotation s'incrémente par contrat (1, 2, 3…) et est INDÉPENDANTE entre
  contrats.
- La numérotation utilise ``max(version)+1`` (jamais ``count()+1``) : après une
  suppression DB de la dernière version, la suivante NE réutilise PAS un numéro.
- Une version est IMMUABLE : aucun PUT/PATCH/DELETE n'est exposé par l'API.
- Un instantané est figé automatiquement à la bascule « signé » (sans casser
  CONTRAT16/17).
- Multi-tenant : versions scopées société ; endpoints scopés société.
- Numéro de version, société et auteur posés CÔTÉ SERVEUR (jamais lus du corps).
- Endpoints : creer-version / lister (+ accès réservé au palier admin/responsable).
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
    Contrat,
    PartieContrat,
    VersionContrat,
)

User = get_user_model()

CONTRATS = "/api/django/contrats/contrats/"
VERSIONS = "/api/django/contrats/versions/"


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


def make_contrat(company, statut="en_approbation", objet="Contrat test",
                 avec_parties=True):
    """Contrat prêt à signer : en approbation + 2 parties (client/prestataire)."""
    contrat = Contrat.objects.create(
        company=company, objet=objet, montant=Decimal("80000"),
        type_contrat="vente", statut=statut,
        date_debut=timezone.localdate() + timedelta(days=30))
    if avec_parties:
        PartieContrat.objects.create(
            company=company, contrat=contrat,
            type_partie="client", nom="Client SARL", ordre=0)
        PartieContrat.objects.create(
            company=company, contrat=contrat,
            type_partie="prestataire", nom="Taqinor", ordre=1)
    return contrat


# ---------------------------------------------------------------------------
# Service — instantané du contenu + numérotation
# ---------------------------------------------------------------------------

class CreerVersionServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("ver-svc", "VerSvc")
        self.user = make_user(self.co, "ver-svc-admin", role="admin")
        self.contrat = make_contrat(self.co, objet="Contrat solaire 12 kWc")

    def test_fige_le_contenu_rendu(self):
        v = services.creer_version(self.contrat, cree_par=self.user)
        self.assertEqual(v.version, 1)
        # Le contenu figé est le corps fusionné (contient l'objet du contrat).
        self.assertIn("Contrat solaire 12 kWc", v.contenu)
        self.assertEqual(v.company_id, self.co.id)
        self.assertEqual(v.cree_par_id, self.user.id)
        self.assertIsNotNone(v.cree_le)

    def test_contenu_explicite_court_circuite_le_rendu(self):
        v = services.creer_version(
            self.contrat, contenu="GELÉ À LA MAIN", cree_par=self.user)
        self.assertEqual(v.contenu, "GELÉ À LA MAIN")

    def test_motif_et_fichier_key(self):
        v = services.creer_version(
            self.contrat, motif="Envoi client",
            fichier_key="contrats/2026/abc.pdf", cree_par=self.user)
        self.assertEqual(v.motif, "Envoi client")
        self.assertEqual(v.fichier_key, "contrats/2026/abc.pdf")

    def test_numerotation_incrementale_par_contrat(self):
        v1 = services.creer_version(self.contrat, cree_par=self.user)
        v2 = services.creer_version(self.contrat, cree_par=self.user)
        v3 = services.creer_version(self.contrat, cree_par=self.user)
        self.assertEqual([v1.version, v2.version, v3.version], [1, 2, 3])

    def test_numerotation_independante_entre_contrats(self):
        autre = make_contrat(self.co, objet="Autre contrat")
        services.creer_version(self.contrat, cree_par=self.user)
        services.creer_version(self.contrat, cree_par=self.user)
        v_autre = services.creer_version(autre, cree_par=self.user)
        # Le second contrat redémarre à 1, indépendant du premier.
        self.assertEqual(v_autre.version, 1)

    def test_numerotation_max_plus_1_pas_count_plus_1(self):
        """``max(version)+1`` et non ``count()+1`` : après suppression DB d'une
        version INTERMÉDIAIRE, on ne réutilise pas un numéro déjà attribué."""
        services.creer_version(self.contrat, cree_par=self.user)  # v1
        v2 = services.creer_version(self.contrat, cree_par=self.user)  # v2
        services.creer_version(self.contrat, cree_par=self.user)  # v3
        # Purge DB d'une version intermédiaire (l'API ne le permet pas).
        v2.delete()
        # Rows restantes : {1, 3} → count()=2 → count()+1 donnerait 3 (COLLISION
        # avec la v3 existante). max(version)+1 = 4 (correct, pas de collision).
        v_next = services.creer_version(self.contrat, cree_par=self.user)
        self.assertEqual(v_next.version, 4)

    def test_versions_immuables_en_base(self):
        """Le modèle n'expose aucune voie d'écriture API ; le service ne met
        jamais à jour une version existante."""
        v1 = services.creer_version(self.contrat, cree_par=self.user)
        services.creer_version(self.contrat, cree_par=self.user)
        v1.refresh_from_db()
        # v1 reste exactement ce qu'elle était (numéro et contenu intacts).
        self.assertEqual(v1.version, 1)


# ---------------------------------------------------------------------------
# Snapshot automatique à la signature (sans casser CONTRAT16/17)
# ---------------------------------------------------------------------------

class SnapshotASignatureTests(TestCase):
    def setUp(self):
        self.co = make_company("ver-sign", "VerSign")
        self.user = make_user(self.co, "ver-sign-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_bascule_signe_fige_une_version(self):
        # Client signe (partiel — pas de bascule, pas de version).
        services.signer_contrat(
            self.contrat, signataire_nom="Client", role_signataire="client",
            auteur=self.user)
        self.assertEqual(
            VersionContrat.objects.filter(contrat=self.contrat).count(), 0)
        # Prestataire signe → bascule « signé » → instantané figé.
        res = services.signer_contrat(
            self.contrat, signataire_nom="Taqinor",
            role_signataire="prestataire", auteur=self.user)
        self.assertTrue(res["contrat_signe"])
        versions = VersionContrat.objects.filter(contrat=self.contrat)
        self.assertEqual(versions.count(), 1)
        self.assertEqual(versions.first().version, 1)
        self.assertEqual(versions.first().motif, "Signature du contrat")
        # CONTRAT16 préservé : le contrat est bien « signé ».
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, "signe")


# ---------------------------------------------------------------------------
# Sélecteur — lecture seule, ordonnée, scopée société
# ---------------------------------------------------------------------------

class VersionsSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("ver-sel", "VerSel")
        self.user = make_user(self.co, "ver-sel-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_versions_ordonnees_recent_en_tete(self):
        services.creer_version(self.contrat, cree_par=self.user)
        services.creer_version(self.contrat, cree_par=self.user)
        services.creer_version(self.contrat, cree_par=self.user)
        nums = list(
            selectors.versions_contrat(self.contrat)
            .values_list("version", flat=True))
        self.assertEqual(nums, [3, 2, 1])

    def test_scope_societe(self):
        autre_co = make_company("ver-sel-2", "VerSel2")
        autre = make_contrat(autre_co)
        services.creer_version(self.contrat, cree_par=self.user)
        services.creer_version(autre)
        # Le sélecteur d'un contrat ne renvoie que SES versions.
        self.assertEqual(selectors.versions_contrat(self.contrat).count(), 1)


# ---------------------------------------------------------------------------
# API — creer-version / lister / immuabilité / scope / rôle
# ---------------------------------------------------------------------------

class VersionApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ver-api", "VerApi")
        self.admin = make_user(self.co, "ver-api-admin", role="admin")
        self.contrat = make_contrat(self.co, objet="Contrat API test")

    def test_creer_version_endpoint(self):
        api = auth(self.admin)
        url = f"{CONTRATS}{self.contrat.id}/creer-version/"
        res = api.post(url, {"motif": "Envoi client"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["version"], 1)
        self.assertEqual(res.data["motif"], "Envoi client")
        self.assertIn("Contrat API test", res.data["contenu"])

    def test_contenu_pose_cote_serveur_pas_du_corps(self):
        """Un ``contenu`` envoyé dans le corps est IGNORÉ : le serveur fige le
        rendu (l'instantané immuable ne peut pas être falsifié par le client)."""
        api = auth(self.admin)
        url = f"{CONTRATS}{self.contrat.id}/creer-version/"
        res = api.post(
            url, {"contenu": "FALSIFIÉ", "version": 99}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["version"], 1)  # pas 99
        self.assertNotEqual(res.data["contenu"], "FALSIFIÉ")
        self.assertIn("Contrat API test", res.data["contenu"])

    def test_lister_versions_par_contrat(self):
        api = auth(self.admin)
        url = f"{CONTRATS}{self.contrat.id}/creer-version/"
        api.post(url, {}, format="json")
        api.post(url, {}, format="json")
        res = api.get(f"{CONTRATS}{self.contrat.id}/versions/")
        self.assertEqual(res.status_code, 200)
        nums = [v["version"] for v in res.data]
        self.assertEqual(nums, [2, 1])

    def test_viewset_versions_lecture_seule(self):
        """La ressource ``/versions/`` n'autorise NI création NI modification NI
        suppression (versions immuables)."""
        v = services.creer_version(self.contrat, cree_par=self.admin)
        api = auth(self.admin)
        # POST direct interdit.
        res_post = api.post(
            VERSIONS, {"contrat": self.contrat.id, "version": 5},
            format="json")
        self.assertEqual(res_post.status_code, 405, res_post.content)
        # PUT / PATCH / DELETE interdits.
        detail = f"{VERSIONS}{v.id}/"
        self.assertEqual(
            api.put(detail, {"contenu": "x"}, format="json").status_code, 405)
        self.assertEqual(
            api.patch(detail, {"motif": "x"}, format="json").status_code, 405)
        self.assertEqual(api.delete(detail).status_code, 405)
        # GET (retrieve) reste autorisé.
        self.assertEqual(api.get(detail).status_code, 200)

    def test_scope_societe_endpoint(self):
        autre_co = make_company("ver-api-2", "VerApi2")
        autre_admin = make_user(autre_co, "ver-api-2-admin", role="admin")
        services.creer_version(self.contrat, cree_par=self.admin)
        # Un admin d'une AUTRE société ne voit pas les versions de ce contrat.
        api = auth(autre_admin)
        res = api.get(f"{VERSIONS}?contrat={self.contrat.id}")
        self.assertEqual(res.status_code, 200)
        # Réponse paginée (PageNumberPagination global) : la société tierce ne
        # voit AUCUNE version de ce contrat (scoping TenantMixin).
        self.assertEqual(res.data["count"], 0)
        self.assertEqual(res.data["results"], [])
        # Et l'action creer-version est 404 sur un contrat hors société.
        res2 = api.post(
            f"{CONTRATS}{self.contrat.id}/creer-version/", {}, format="json")
        self.assertEqual(res2.status_code, 404)

    def test_role_gate_refuse_non_privilegie(self):
        commercial = make_user(self.co, "ver-api-com", role="commercial")
        api = auth(commercial)
        res = api.post(
            f"{CONTRATS}{self.contrat.id}/creer-version/", {}, format="json")
        self.assertEqual(res.status_code, 403, res.content)
        res2 = api.get(VERSIONS)
        self.assertEqual(res2.status_code, 403)
