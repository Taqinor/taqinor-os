"""Tests CONTRAT14 — EtapeApprobation (étapes & workflow d'approbation interne).

Couvre :
- Lancement du workflow depuis la règle CONTRAT13 (nb d'étapes = nombre
  d'approbateurs requis, niveau hérité, statuts en_attente, ordre 1..N).
- Lancement sans règle couvrante → aucune étape créée.
- Relance refusée si un workflow est déjà en cours (pas de doublon).
- Approbation/rejet d'une étape (statut, approbateur, decision_le, commentaire).
- Avancement DANS L'ORDRE : on ne décide pas une étape hors séquence.
- Re-décision d'une étape close refusée.
- Le workflow ne touche JAMAIS au Contrat.statut (préservation des statuts).
- Multi-tenant : étapes scopées société ; endpoints scopés société.
- Endpoints : lancer / lister / approuver / rejeter (+ accès réservé).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.models import (
    Contrat,
    EtapeApprobation,
    RegleApprobation,
)

User = get_user_model()

CONTRATS = "/api/django/contrats/contrats/"


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


def make_contrat(company, montant=Decimal("80000"), type_contrat="vente",
                 objet="Contrat test"):
    return Contrat.objects.create(
        company=company, objet=objet, montant=montant,
        type_contrat=type_contrat)


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
# Service — lancement du workflow
# ---------------------------------------------------------------------------

class LancerWorkflowTests(TestCase):
    def setUp(self):
        self.co = make_company("ea-lance", "Lance")

    def test_lancement_cree_etapes_depuis_regle(self):
        make_regle(
            self.co, libelle="> 50k", montant_min=Decimal("50000"),
            niveau_approbation="administrateur", nombre_approbateurs=3)
        contrat = make_contrat(self.co, montant=Decimal("80000"))

        etapes = services.lancer_workflow_approbation(contrat)

        self.assertEqual(len(etapes), 3)
        # Niveaux 1..N, statut en_attente, niveau de rôle hérité de la règle.
        self.assertEqual([e.niveau for e in etapes], [1, 2, 3])
        for e in etapes:
            self.assertEqual(e.statut, EtapeApprobation.Statut.EN_ATTENTE)
            self.assertEqual(e.niveau_approbation, "administrateur")
            self.assertEqual(e.company_id, self.co.id)
            self.assertIsNone(e.approbateur_id)

    def test_lancement_au_moins_une_etape(self):
        make_regle(self.co, montant_max=Decimal("1000000"),
                   nombre_approbateurs=0)
        contrat = make_contrat(self.co, montant=Decimal("1000"))
        etapes = services.lancer_workflow_approbation(contrat)
        self.assertEqual(len(etapes), 1)

    def test_lancement_sans_regle_couvrante_aucune_etape(self):
        make_regle(self.co, montant_min=Decimal("100000"))
        contrat = make_contrat(self.co, montant=Decimal("500"))
        etapes = services.lancer_workflow_approbation(contrat)
        self.assertEqual(etapes, [])
        self.assertEqual(contrat.etapes_approbation.count(), 0)

    def test_relance_refusee_si_workflow_en_cours(self):
        make_regle(self.co, montant_max=Decimal("1000000"),
                   nombre_approbateurs=2)
        contrat = make_contrat(self.co, montant=Decimal("1000"))
        services.lancer_workflow_approbation(contrat)
        with self.assertRaises(services.ApprobationError):
            services.lancer_workflow_approbation(contrat)
        # Toujours 2 étapes, pas de doublon.
        self.assertEqual(contrat.etapes_approbation.count(), 2)

    def test_lancement_ne_change_pas_statut_contrat(self):
        make_regle(self.co, montant_max=Decimal("1000000"))
        contrat = make_contrat(self.co, montant=Decimal("1000"))
        statut_avant = contrat.statut
        services.lancer_workflow_approbation(contrat)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, statut_avant)


# ---------------------------------------------------------------------------
# Service — approbation / rejet / avancement
# ---------------------------------------------------------------------------

class DeciderEtapeTests(TestCase):
    def setUp(self):
        self.co = make_company("ea-decide", "Decide")
        self.user = make_user(self.co, "ea-decide-admin", role="admin")
        make_regle(self.co, montant_max=Decimal("1000000"),
                   nombre_approbateurs=2)
        self.contrat = make_contrat(self.co, montant=Decimal("1000"))
        self.etapes = services.lancer_workflow_approbation(self.contrat)

    def test_approuver_premiere_etape(self):
        etape = self.etapes[0]
        services.approuver_etape(
            etape, approbateur=self.user, commentaire="OK")
        etape.refresh_from_db()
        self.assertEqual(etape.statut, EtapeApprobation.Statut.APPROUVE)
        self.assertEqual(etape.approbateur_id, self.user.id)
        self.assertIsNotNone(etape.decision_le)
        self.assertEqual(etape.commentaire, "OK")

    def test_avancement_dans_l_ordre_refuse_saut(self):
        # Décider l'étape 2 avant l'étape 1 est refusé.
        with self.assertRaises(services.ApprobationError):
            services.approuver_etape(self.etapes[1], approbateur=self.user)

    def test_avancement_sequentiel(self):
        services.approuver_etape(self.etapes[0], approbateur=self.user)
        # Maintenant l'étape 2 est la première en attente : approuvable.
        services.approuver_etape(self.etapes[1], approbateur=self.user)
        self.assertTrue(services.workflow_complet(self.contrat))

    def test_re_decision_etape_close_refusee(self):
        services.approuver_etape(self.etapes[0], approbateur=self.user)
        with self.assertRaises(services.ApprobationError):
            services.rejeter_etape(self.etapes[0], approbateur=self.user)

    def test_rejet_pose_statut_rejete(self):
        etape = self.etapes[0]
        services.rejeter_etape(
            etape, approbateur=self.user, commentaire="Non conforme")
        etape.refresh_from_db()
        self.assertEqual(etape.statut, EtapeApprobation.Statut.REJETE)
        self.assertEqual(etape.commentaire, "Non conforme")
        self.assertFalse(services.workflow_complet(self.contrat))

    def test_decision_ne_change_pas_statut_contrat(self):
        statut_avant = self.contrat.statut
        services.approuver_etape(self.etapes[0], approbateur=self.user)
        services.approuver_etape(self.etapes[1], approbateur=self.user)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, statut_avant)

    def test_selector_etapes_ordonnees(self):
        etapes = list(selectors.etapes_approbation(self.contrat))
        self.assertEqual([e.niveau for e in etapes], [1, 2])


# ---------------------------------------------------------------------------
# Multi-tenant
# ---------------------------------------------------------------------------

class EtapeTenantTests(TestCase):
    def setUp(self):
        self.a = make_company("ea-a", "A")
        self.b = make_company("ea-b", "B")
        make_regle(self.a, montant_max=Decimal("1000000"))
        make_regle(self.b, montant_max=Decimal("1000000"))
        self.contrat_a = make_contrat(self.a, montant=Decimal("1000"))
        self.contrat_b = make_contrat(self.b, montant=Decimal("1000"))
        services.lancer_workflow_approbation(self.contrat_a)
        services.lancer_workflow_approbation(self.contrat_b)

    def test_etapes_scopees_societe(self):
        etapes_a = selectors.etapes_approbation(self.contrat_a)
        for e in etapes_a:
            self.assertEqual(e.company_id, self.a.id)
        # Aucune étape de B ne fuite dans le scope de A.
        ids_b = set(
            self.contrat_b.etapes_approbation.values_list("id", flat=True))
        ids_a = set(etapes_a.values_list("id", flat=True))
        self.assertFalse(ids_a & ids_b)

    def test_lancement_resout_regle_de_la_bonne_societe(self):
        # Le contrat de A n'utilise que les règles de A (résolveur scopé société).
        etape = self.contrat_a.etapes_approbation.first()
        self.assertEqual(etape.company_id, self.a.id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class EtapeEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("ea-ep", "EP")
        self.admin = make_user(self.co, "ea-ep-admin", role="admin")
        make_regle(self.co, montant_max=Decimal("1000000"),
                   nombre_approbateurs=2)
        self.contrat = make_contrat(self.co, montant=Decimal("1000"))

    def _url(self, suffix):
        return f"{CONTRATS}{self.contrat.id}/{suffix}/"

    def test_lancer_endpoint_cree_etapes(self):
        api = auth(self.admin)
        resp = api.post(self._url("lancer-approbation"))
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(self.contrat.etapes_approbation.count(), 2)

    def test_lancer_deux_fois_refuse(self):
        api = auth(self.admin)
        api.post(self._url("lancer-approbation"))
        resp = api.post(self._url("lancer-approbation"))
        self.assertEqual(resp.status_code, 400)

    def test_lister_etapes(self):
        api = auth(self.admin)
        api.post(self._url("lancer-approbation"))
        resp = api.get(self._url("etapes-approbation"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([e["niveau"] for e in resp.data], [1, 2])

    def test_approuver_puis_rejeter_endpoint(self):
        api = auth(self.admin)
        api.post(self._url("lancer-approbation"))
        etapes = list(self.contrat.etapes_approbation.order_by("niveau"))

        resp = api.post(
            self._url("approuver-etape"),
            {"etape": etapes[0].id, "commentaire": "go"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["statut"], "approuve")
        self.assertEqual(resp.data["approbateur"], self.admin.id)

        resp = api.post(
            self._url("rejeter-etape"),
            {"etape": etapes[1].id}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["statut"], "rejete")

    def test_approuver_hors_ordre_400(self):
        api = auth(self.admin)
        api.post(self._url("lancer-approbation"))
        etapes = list(self.contrat.etapes_approbation.order_by("niveau"))
        resp = api.post(
            self._url("approuver-etape"),
            {"etape": etapes[1].id}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_etape_autre_societe_404(self):
        autre = make_company("ea-ep-autre", "Autre")
        make_regle(autre, montant_max=Decimal("1000000"))
        contrat_autre = make_contrat(autre, montant=Decimal("1000"))
        services.lancer_workflow_approbation(contrat_autre)
        etape_autre = contrat_autre.etapes_approbation.first()

        api = auth(self.admin)
        api.post(self._url("lancer-approbation"))
        resp = api.post(
            self._url("approuver-etape"),
            {"etape": etape_autre.id}, format="json")
        # L'étape n'appartient pas au contrat courant → 404.
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_interdit(self):
        normal = make_user(self.co, "ea-ep-normal", role="commercial")
        api = auth(normal)
        resp = api.post(self._url("lancer-approbation"))
        self.assertEqual(resp.status_code, 403)
