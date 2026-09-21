"""Tests CONTRAT23 — renouvellement EFFECTIF (manuel + tacite reconduction).

Complémentaire de CONTRAT20 (préavis) et CONTRAT21 (liste « à renouveler »), qui
ne font que SURFACER les contrats : ici on PROLONGE réellement la période.

Couvre :
- ``Contrat.ajouter_mois`` (décalage, débordement d'année, bornage de jour).
- Service ``renouveler_contrat`` : durée en mois, nouvelle date explicite, durée
  de reconduction du contrat par défaut, avance date_debut, reset preavis_traite,
  snapshot version, audit chatter, compteur, refus résilié/expiré, refus calcul
  impossible, statut préservé.
- Service ``traiter_reconductions_tacites`` : auto-renouvelle les contrats dus,
  idempotent (pas de double), non-tacite ignoré, rattrapage multi-périodes,
  isolation société.
- Endpoints ``/<id>/renouveler/`` et ``/traiter-reconductions/`` : succès,
  validation 400, accès rôle 403, isolation société.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import Contrat, ContratActivity, VersionContrat

User = get_user_model()

BASE = "/api/django/contrats/contrats/"
TRAITER = BASE + "traiter-reconductions/"


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


def make_contrat(company, objet="Contrat", **kwargs):
    defaults = {"statut": Contrat.Statut.ACTIF}
    defaults.update(kwargs)
    return Contrat.objects.create(company=company, objet=objet, **defaults)


# ---------------------------------------------------------------------------
# Modèle — ajouter_mois
# ---------------------------------------------------------------------------

class AjouterMoisTests(TestCase):
    def test_simple(self):
        self.assertEqual(
            Contrat.ajouter_mois(date(2026, 1, 15), 1), date(2026, 2, 15))

    def test_debordement_annee(self):
        self.assertEqual(
            Contrat.ajouter_mois(date(2026, 11, 10), 3), date(2027, 2, 10))

    def test_douze_mois(self):
        self.assertEqual(
            Contrat.ajouter_mois(date(2026, 6, 30), 12), date(2027, 6, 30))

    def test_borne_jour_fin_de_mois(self):
        # 31 janvier + 1 mois → 28 février (2026 non bissextile).
        self.assertEqual(
            Contrat.ajouter_mois(date(2026, 1, 31), 1), date(2026, 2, 28))


# ---------------------------------------------------------------------------
# Service — renouveler_contrat
# ---------------------------------------------------------------------------

class RenouvelerContratServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("rc-svc", "Svc")
        self.user = make_user(self.co, "rc-svc-user")
        self.today = date(2026, 6, 1)

    def test_duree_mois_explicite_etend_date_fin(self):
        c = make_contrat(
            self.co, date_debut=date(2025, 6, 30), date_fin=date(2026, 6, 30),
            preavis_traite=True)
        services.renouveler_contrat(
            c, duree_mois=12, auteur=self.user, today=self.today,
            snapshot=False)
        c.refresh_from_db()
        self.assertEqual(c.date_fin, date(2027, 6, 30))
        # Nouvelle période démarre à l'ancienne fin.
        self.assertEqual(c.date_debut, date(2026, 6, 30))
        # Préavis ré-ouvert pour la nouvelle période.
        self.assertFalse(c.preavis_traite)
        self.assertEqual(c.date_dernier_renouvellement, self.today)
        self.assertEqual(c.nb_renouvellements, 1)

    def test_nouvelle_date_fin_explicite_prioritaire(self):
        c = make_contrat(self.co, date_fin=date(2026, 6, 30))
        services.renouveler_contrat(
            c, nouvelle_date_fin=date(2028, 1, 1), duree_mois=3,
            auteur=self.user, today=self.today, snapshot=False)
        c.refresh_from_db()
        self.assertEqual(c.date_fin, date(2028, 1, 1))

    def test_utilise_duree_reconduction_du_contrat_par_defaut(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 6, 30),
            tacite_reconduction=True, duree_reconduction_mois=6)
        services.renouveler_contrat(
            c, auteur=self.user, today=self.today, snapshot=False)
        c.refresh_from_db()
        self.assertEqual(c.date_fin, date(2026, 12, 30))

    def test_sans_date_fin_part_de_today(self):
        c = make_contrat(self.co)  # pas de date_fin
        services.renouveler_contrat(
            c, duree_mois=12, auteur=self.user, today=self.today,
            snapshot=False)
        c.refresh_from_db()
        self.assertEqual(c.date_fin, date(2027, 6, 1))

    def test_snapshot_cree_une_version(self):
        c = make_contrat(self.co, date_fin=date(2026, 6, 30))
        services.renouveler_contrat(
            c, duree_mois=12, auteur=self.user, today=self.today)
        v = VersionContrat.objects.filter(contrat=c).first()
        self.assertIsNotNone(v)
        self.assertEqual(v.motif, "Renouvellement")

    def test_journalise_le_chatter(self):
        c = make_contrat(self.co, date_fin=date(2026, 6, 30))
        services.renouveler_contrat(
            c, duree_mois=12, auteur=self.user, today=self.today,
            snapshot=False)
        log = ContratActivity.objects.filter(
            contrat=c, field="renouvellement").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.auteur_id, self.user.id)

    def test_statut_preserve(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 6, 30), statut=Contrat.Statut.ACTIF)
        services.renouveler_contrat(
            c, duree_mois=12, auteur=self.user, today=self.today,
            snapshot=False)
        c.refresh_from_db()
        self.assertEqual(c.statut, Contrat.Statut.ACTIF)

    def test_refus_resilie(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 6, 30),
            statut=Contrat.Statut.RESILIE)
        with self.assertRaises(services.RenouvellementError):
            services.renouveler_contrat(
                c, duree_mois=12, auteur=self.user, today=self.today)

    def test_refus_expire(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 6, 30),
            statut=Contrat.Statut.EXPIRE)
        with self.assertRaises(services.RenouvellementError):
            services.renouveler_contrat(
                c, duree_mois=12, auteur=self.user, today=self.today)

    def test_refus_calcul_impossible(self):
        # Ni nouvelle date, ni durée, ni duree_reconduction_mois.
        c = make_contrat(self.co, date_fin=date(2026, 6, 30))
        with self.assertRaises(services.RenouvellementError):
            services.renouveler_contrat(
                c, auteur=self.user, today=self.today)


# ---------------------------------------------------------------------------
# Service — traiter_reconductions_tacites
# ---------------------------------------------------------------------------

class TraiterReconductionsServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("rc-tac", "Tac")
        self.user = make_user(self.co, "rc-tac-user")
        self.today = date(2026, 6, 1)

    def test_auto_renouvelle_contrat_du(self):
        # Échéance passée + tacite + durée.
        c = make_contrat(
            self.co, date_fin=date(2026, 5, 1),
            tacite_reconduction=True, duree_reconduction_mois=12)
        res = services.traiter_reconductions_tacites(
            self.co, today=self.today, auteur=self.user)
        c.refresh_from_db()
        self.assertEqual(res["nb_traites"], 1)
        # Nouvelle fin au-delà de today.
        self.assertGreater(c.date_fin, self.today)
        self.assertEqual(c.date_fin, date(2027, 5, 1))
        self.assertEqual(c.nb_renouvellements, 1)

    def test_idempotent_pas_de_double(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 5, 1),
            tacite_reconduction=True, duree_reconduction_mois=12)
        services.traiter_reconductions_tacites(
            self.co, today=self.today, auteur=self.user)
        # Second passage le même jour : la fin est déjà > today → rien.
        res2 = services.traiter_reconductions_tacites(
            self.co, today=self.today, auteur=self.user)
        c.refresh_from_db()
        self.assertEqual(res2["nb_traites"], 0)
        self.assertEqual(c.nb_renouvellements, 1)

    def test_non_tacite_ignore(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 5, 1),
            tacite_reconduction=False, duree_reconduction_mois=12)
        res = services.traiter_reconductions_tacites(
            self.co, today=self.today, auteur=self.user)
        c.refresh_from_db()
        self.assertEqual(res["nb_traites"], 0)
        self.assertEqual(c.date_fin, date(2026, 5, 1))
        self.assertEqual(c.nb_renouvellements, 0)

    def test_echeance_future_ignoree(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 12, 31),
            tacite_reconduction=True, duree_reconduction_mois=12)
        res = services.traiter_reconductions_tacites(
            self.co, today=self.today, auteur=self.user)
        c.refresh_from_db()
        self.assertEqual(res["nb_traites"], 0)
        self.assertEqual(c.date_fin, date(2026, 12, 31))

    def test_sans_duree_ignore(self):
        make_contrat(
            self.co, date_fin=date(2026, 5, 1),
            tacite_reconduction=True, duree_reconduction_mois=None)
        res = services.traiter_reconductions_tacites(
            self.co, today=self.today, auteur=self.user)
        self.assertEqual(res["nb_traites"], 0)

    def test_resilie_ignore(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 5, 1),
            statut=Contrat.Statut.RESILIE,
            tacite_reconduction=True, duree_reconduction_mois=12)
        res = services.traiter_reconductions_tacites(
            self.co, today=self.today, auteur=self.user)
        c.refresh_from_db()
        self.assertEqual(res["nb_traites"], 0)
        self.assertEqual(c.date_fin, date(2026, 5, 1))

    def test_rattrape_plusieurs_periodes(self):
        # Fin bien dans le passé : plusieurs reconductions mensuelles pour
        # rattraper jusqu'à dépasser today.
        c = make_contrat(
            self.co, date_fin=date(2026, 1, 1),
            tacite_reconduction=True, duree_reconduction_mois=1)
        services.traiter_reconductions_tacites(
            self.co, today=self.today, auteur=self.user)
        c.refresh_from_db()
        self.assertGreater(c.date_fin, self.today)
        self.assertGreaterEqual(c.nb_renouvellements, 5)

    def test_isolation_societe(self):
        autre = make_company("rc-tac-autre", "Autre")
        c = make_contrat(
            autre, date_fin=date(2026, 5, 1),
            tacite_reconduction=True, duree_reconduction_mois=12)
        res = services.traiter_reconductions_tacites(
            self.co, today=self.today, auteur=self.user)
        c.refresh_from_db()
        self.assertEqual(res["nb_traites"], 0)
        # Le contrat de l'autre société n'a pas bougé.
        self.assertEqual(c.date_fin, date(2026, 5, 1))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class RenouvelerEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("rc-ep", "EP")
        self.other = make_company("rc-ep-other", "Other")
        self.admin = make_user(self.co, "rc-ep-admin", role="admin")

    def test_renouveler_duree_mois(self):
        c = make_contrat(self.co, date_fin=date(2026, 6, 30))
        api = auth(self.admin)
        resp = api.post(
            f"{BASE}{c.id}/renouveler/", {"duree_mois": 12}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        c.refresh_from_db()
        self.assertEqual(c.date_fin, date(2027, 6, 30))
        self.assertEqual(resp.data["nb_renouvellements"], 1)

    def test_renouveler_nouvelle_date_fin(self):
        c = make_contrat(self.co, date_fin=date(2026, 6, 30))
        api = auth(self.admin)
        resp = api.post(
            f"{BASE}{c.id}/renouveler/",
            {"nouvelle_date_fin": "2028-01-01"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        c.refresh_from_db()
        self.assertEqual(c.date_fin, date(2028, 1, 1))

    def test_renouveler_calcul_impossible_400(self):
        c = make_contrat(self.co, date_fin=date(2026, 6, 30))
        api = auth(self.admin)
        resp = api.post(f"{BASE}{c.id}/renouveler/", {}, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_renouveler_resilie_400(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 6, 30),
            statut=Contrat.Statut.RESILIE)
        api = auth(self.admin)
        resp = api.post(
            f"{BASE}{c.id}/renouveler/", {"duree_mois": 12}, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_renouveler_autre_societe_404(self):
        c = make_contrat(self.other, date_fin=date(2026, 6, 30))
        api = auth(self.admin)
        resp = api.post(
            f"{BASE}{c.id}/renouveler/", {"duree_mois": 12}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_renouveler_role_normal_403(self):
        normal = make_user(self.co, "rc-ep-normal", role="commercial")
        c = make_contrat(self.co, date_fin=date(2026, 6, 30))
        api = auth(normal)
        resp = api.post(
            f"{BASE}{c.id}/renouveler/", {"duree_mois": 12}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_traiter_reconductions_endpoint(self):
        c = make_contrat(
            self.co, date_fin=date.today() - timedelta(days=1),
            tacite_reconduction=True, duree_reconduction_mois=12)
        api = auth(self.admin)
        resp = api.post(TRAITER, {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["nb_traites"], 1)
        c.refresh_from_db()
        self.assertGreater(c.date_fin, date.today())

    def test_traiter_reconductions_role_normal_403(self):
        normal = make_user(self.co, "rc-ep-normal2", role="commercial")
        api = auth(normal)
        resp = api.post(TRAITER, {}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_traiter_reconductions_isolation_societe(self):
        # Contrat dû dans l'autre société : l'admin de self.co ne le traite pas.
        c = make_contrat(
            self.other, date_fin=date.today() - timedelta(days=1),
            tacite_reconduction=True, duree_reconduction_mois=12)
        api = auth(self.admin)
        resp = api.post(TRAITER, {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["nb_traites"], 0)
        c.refresh_from_db()
        self.assertEqual(c.date_fin, date.today() - timedelta(days=1))
