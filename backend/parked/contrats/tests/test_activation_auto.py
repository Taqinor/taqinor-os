"""Tests CONTRAT17 — Activation automatique « signé → actif » sur signature.

Couvre :
- Signature COMPLÈTE (client + prestataire) d'un contrat dont la prise d'effet
  est atteinte (``date_debut`` absente ou ≤ aujourd'hui) → le contrat passe à
  ``signe`` PUIS s'active automatiquement à ``actif`` via la machine d'états
  gardée (CONTRAT12), jamais un funnel STAGES.py (rule #2).
- Garde de date : une prise d'effet FUTURE laisse le contrat à ``signe`` (pas
  d'activation tant que la date n'est pas atteinte).
- Signature PARTIELLE : ni ``signe`` ni ``actif`` (statut préservé).
- La bascule d'activation est journalisée dans le chatter (CONTRAT15).
- Multi-tenant : l'activation reste scopée à la société du contrat.
- L'endpoint ``signer`` renvoie ``contrat_actif`` et le ``statut`` final.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import Contrat, ContratActivity, PartieContrat

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


def make_contrat(company, statut="en_approbation", date_debut=None,
                 avec_parties=True):
    """Contrat prêt à signer : en approbation + 2 parties (client/prestataire).

    ``date_debut`` non posée (``None``) = prise d'effet immédiate.
    """
    contrat = Contrat.objects.create(
        company=company, objet="Contrat CONTRAT17", montant=Decimal("80000"),
        type_contrat="vente", statut=statut, date_debut=date_debut)
    if avec_parties:
        PartieContrat.objects.create(
            company=company, contrat=contrat,
            type_partie="client", nom="Client SARL", ordre=0)
        PartieContrat.objects.create(
            company=company, contrat=contrat,
            type_partie="prestataire", nom="Taqinor", ordre=1)
    return contrat


def _signer_les_deux(contrat, **kw):
    services.signer_contrat(
        contrat, signataire_nom="Client", role_signataire="client", **kw)
    return services.signer_contrat(
        contrat, signataire_nom="Presta", role_signataire="prestataire", **kw)


# ---------------------------------------------------------------------------
# Service — activation automatique sur signature complète
# ---------------------------------------------------------------------------

class ActivationAutoServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("act-svc", "ActSvc")
        self.user = make_user(self.co, "act-svc-admin", role="admin")

    def test_signature_complete_active_automatiquement(self):
        # date_debut absente = effet immédiat → signe puis actif.
        contrat = make_contrat(self.co, date_debut=None)
        res = _signer_les_deux(contrat, auteur=self.user)
        contrat.refresh_from_db()
        self.assertTrue(res["contrat_signe"])
        self.assertTrue(res["contrat_actif"])
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_date_debut_passee_active(self):
        hier = timezone.localdate() - timedelta(days=1)
        contrat = make_contrat(self.co, date_debut=hier)
        res = _signer_les_deux(contrat)
        contrat.refresh_from_db()
        self.assertTrue(res["contrat_actif"])
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_date_debut_aujourdhui_active(self):
        contrat = make_contrat(self.co, date_debut=timezone.localdate())
        res = _signer_les_deux(contrat)
        contrat.refresh_from_db()
        self.assertTrue(res["contrat_actif"])
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_date_debut_future_reste_signe(self):
        # Prise d'effet future : on bascule à « signe » mais PAS à « actif ».
        futur = timezone.localdate() + timedelta(days=15)
        contrat = make_contrat(self.co, date_debut=futur)
        res = _signer_les_deux(contrat)
        contrat.refresh_from_db()
        self.assertTrue(res["contrat_signe"])
        self.assertFalse(res["contrat_actif"])
        self.assertEqual(contrat.statut, Contrat.Statut.SIGNE)

    def test_today_injectable_garde_respectee(self):
        # date_debut = dans 5 jours, mais on évalue « today » = dans 10 jours :
        # la prise d'effet est alors atteinte → activation.
        debut = timezone.localdate() + timedelta(days=5)
        contrat = make_contrat(self.co, date_debut=debut)
        services.signer_contrat(
            contrat, signataire_nom="Client", role_signataire="client",
            today=timezone.localdate() + timedelta(days=10))
        res = services.signer_contrat(
            contrat, signataire_nom="Presta", role_signataire="prestataire",
            today=timezone.localdate() + timedelta(days=10))
        contrat.refresh_from_db()
        self.assertTrue(res["contrat_actif"])
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_signature_partielle_ni_signe_ni_actif(self):
        contrat = make_contrat(self.co, date_debut=None)
        res = services.signer_contrat(
            contrat, signataire_nom="Client", role_signataire="client")
        contrat.refresh_from_db()
        self.assertFalse(res["contrat_signe"])
        self.assertFalse(res["contrat_actif"])
        self.assertEqual(contrat.statut, "en_approbation")

    def test_activation_journalisee_dans_le_chatter(self):
        contrat = make_contrat(self.co, date_debut=None)
        _signer_les_deux(contrat, auteur=self.user)
        # Chatter (CONTRAT15) : 2 entrées « statut » (signe + actif).
        champs = list(contrat.activites.values_list("field", flat=True))
        self.assertEqual(champs.count("statut"), 2)
        # L'entrée d'activation porte le bon couple ancien → nouveau.
        activation = contrat.activites.filter(
            field="statut", new_value=Contrat.Statut.ACTIF).first()
        self.assertIsNotNone(activation)
        self.assertEqual(activation.old_value, Contrat.Statut.SIGNE)
        self.assertEqual(activation.type, ContratActivity.Kind.LOG)
        self.assertEqual(activation.auteur_id, self.user.id)
        self.assertEqual(activation.company_id, self.co.id)

    def test_peut_activer_automatiquement_garde(self):
        # Sur un contrat non « signe », la garde renvoie toujours False.
        brouillon = make_contrat(self.co, statut="brouillon", date_debut=None)
        self.assertFalse(
            services.peut_activer_automatiquement(brouillon))
        # Un contrat « signe » à effet immédiat est activable.
        signe = make_contrat(self.co, statut="signe", date_debut=None)
        self.assertTrue(services.peut_activer_automatiquement(signe))
        # Un contrat « signe » à effet futur ne l'est pas.
        futur = make_contrat(
            self.co, statut="signe",
            date_debut=timezone.localdate() + timedelta(days=3))
        self.assertFalse(services.peut_activer_automatiquement(futur))


# ---------------------------------------------------------------------------
# Multi-tenant
# ---------------------------------------------------------------------------

class ActivationTenantTests(TestCase):
    def test_activation_scopee_societe(self):
        a = make_company("act-a", "A")
        b = make_company("act-b", "B")
        contrat_a = make_contrat(a, date_debut=None)
        contrat_b = make_contrat(b, date_debut=None)
        _signer_les_deux(contrat_a)
        # b non signé : reste en approbation, l'activation de a ne déborde pas.
        contrat_a.refresh_from_db()
        contrat_b.refresh_from_db()
        self.assertEqual(contrat_a.statut, Contrat.Statut.ACTIF)
        self.assertEqual(contrat_b.statut, "en_approbation")
        # L'entrée d'activation reste scopée à la société de a.
        activation = contrat_a.activites.filter(
            field="statut", new_value=Contrat.Statut.ACTIF).first()
        self.assertEqual(activation.company_id, a.id)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

class ActivationEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("act-ep", "EP")
        self.admin = make_user(self.co, "act-ep-admin", role="admin")

    def _url(self, contrat, suffix):
        return f"{CONTRATS}{contrat.id}/{suffix}/"

    def test_signer_les_deux_active_et_renvoie_actif(self):
        contrat = make_contrat(self.co, date_debut=None)
        api = auth(self.admin)
        api.post(
            self._url(contrat, "signer"),
            {"signataire_nom": "Client", "role_signataire": "client"},
            format="json")
        resp = api.post(
            self._url(contrat, "signer"),
            {"signataire_nom": "Presta", "role_signataire": "prestataire"},
            format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data["contrat_signe"])
        self.assertTrue(resp.data["contrat_actif"])
        self.assertEqual(resp.data["statut"], Contrat.Statut.ACTIF)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_signer_date_future_reste_signe(self):
        futur = timezone.localdate() + timedelta(days=20)
        contrat = make_contrat(self.co, date_debut=futur)
        api = auth(self.admin)
        api.post(
            self._url(contrat, "signer"),
            {"signataire_nom": "Client", "role_signataire": "client"},
            format="json")
        resp = api.post(
            self._url(contrat, "signer"),
            {"signataire_nom": "Presta", "role_signataire": "prestataire"},
            format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data["contrat_signe"])
        self.assertFalse(resp.data["contrat_actif"])
        self.assertEqual(resp.data["statut"], Contrat.Statut.SIGNE)
