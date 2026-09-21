"""Tests CONTRAT21 — calcul des échéances & contrats « à renouveler ».

Vue complémentaire de CONTRAT20 (préavis) : ici on regarde la FIN du contrat
(``date_fin``) elle-même, pas la date limite de préavis.

Couvre :
- Modèle ``Contrat.jours_avant_echeance`` (à venir / aujourd'hui / dépassé /
  non calculable sans ``date_fin``).
- Sélecteur ``contrats_a_renouveler`` : dans / hors de la fenêtre, exclusions
  (sans date_fin, résilié/expiré), within<0, ordre par échéance, tacite
  reconduction toujours listée.
- Isolation multi-tenant du sélecteur (société A ne voit pas B).
- Champ sérialiseur ``jours_avant_echeance``.
- Endpoint ``/a-renouveler/?within=N`` : liste scopée société, fenêtre, within
  invalide, accès rôle (403).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors
from apps.contrats.models import Contrat

User = get_user_model()

BASE = "/api/django/contrats/contrats/"
RENOUVELER = BASE + "a-renouveler/"


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


def make_contrat(company, objet="Contrat", **kwargs):
    defaults = {"statut": Contrat.Statut.ACTIF}
    defaults.update(kwargs)
    return Contrat.objects.create(company=company, objet=objet, **defaults)


# ---------------------------------------------------------------------------
# Modèle — jours_avant_echeance
# ---------------------------------------------------------------------------

class JoursAvantEcheanceModelTests(TestCase):
    def setUp(self):
        self.co = make_company("cr-mod", "Mod")

    def test_a_venir(self):
        c = make_contrat(self.co, date_fin=date(2026, 12, 31))
        self.assertEqual(c.jours_avant_echeance(today=date(2026, 12, 21)), 10)

    def test_aujourdhui(self):
        c = make_contrat(self.co, date_fin=date(2026, 12, 31))
        self.assertEqual(c.jours_avant_echeance(today=date(2026, 12, 31)), 0)

    def test_depasse(self):
        c = make_contrat(self.co, date_fin=date(2026, 12, 31))
        self.assertEqual(c.jours_avant_echeance(today=date(2027, 1, 5)), -5)

    def test_non_calculable_sans_date_fin(self):
        c = make_contrat(self.co)
        self.assertIsNone(c.jours_avant_echeance(today=date(2026, 1, 1)))


# ---------------------------------------------------------------------------
# Sélecteur — contrats_a_renouveler
# ---------------------------------------------------------------------------

class ContratsARenouvelerSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("cr-sel", "Sel")
        self.today = date(2026, 6, 1)

    def test_dans_la_fenetre_remonte(self):
        # date_fin dans 14 jours.
        c = make_contrat(self.co, date_fin=date(2026, 6, 15))
        ids = [x.id for x in selectors.contrats_a_renouveler(
            self.co, within_days=30, today=self.today)]
        self.assertIn(c.id, ids)

    def test_aujourdhui_inclus(self):
        c = make_contrat(self.co, date_fin=self.today)
        ids = [x.id for x in selectors.contrats_a_renouveler(
            self.co, within_days=30, today=self.today)]
        self.assertIn(c.id, ids)

    def test_hors_fenetre_exclu(self):
        c = make_contrat(self.co, date_fin=date(2026, 12, 31))
        ids = [x.id for x in selectors.contrats_a_renouveler(
            self.co, within_days=30, today=self.today)]
        self.assertNotIn(c.id, ids)

    def test_echeance_passee_exclue(self):
        # date_fin avant aujourd'hui.
        c = make_contrat(self.co, date_fin=date(2026, 5, 15))
        ids = [x.id for x in selectors.contrats_a_renouveler(
            self.co, within_days=30, today=self.today)]
        self.assertNotIn(c.id, ids)

    def test_sans_date_fin_exclu(self):
        c = make_contrat(self.co, objet="sans fin")
        ids = [x.id for x in selectors.contrats_a_renouveler(
            self.co, within_days=60, today=self.today)]
        self.assertNotIn(c.id, ids)

    def test_resilie_ou_expire_exclu(self):
        c1 = make_contrat(
            self.co, date_fin=date(2026, 6, 15),
            statut=Contrat.Statut.RESILIE)
        c2 = make_contrat(
            self.co, date_fin=date(2026, 6, 15),
            statut=Contrat.Statut.EXPIRE)
        ids = [x.id for x in selectors.contrats_a_renouveler(
            self.co, within_days=30, today=self.today)]
        self.assertNotIn(c1.id, ids)
        self.assertNotIn(c2.id, ids)

    def test_tacite_reconduction_toujours_listee(self):
        # Un contrat en tacite reconduction reste listé (l'UI saura via le flag).
        c = make_contrat(
            self.co, date_fin=date(2026, 6, 15), tacite_reconduction=True)
        ids = [x.id for x in selectors.contrats_a_renouveler(
            self.co, within_days=30, today=self.today)]
        self.assertIn(c.id, ids)

    def test_ordre_par_echeance(self):
        tard = make_contrat(
            self.co, objet="tard", date_fin=date(2026, 6, 25))
        tot = make_contrat(
            self.co, objet="tot", date_fin=date(2026, 6, 5))
        ids = [x.id for x in selectors.contrats_a_renouveler(
            self.co, within_days=60, today=self.today)]
        self.assertTrue(ids.index(tot.id) < ids.index(tard.id))

    def test_within_negatif_ramene_a_zero(self):
        # date_fin dans 14 jours, mais within<0 → fenêtre [today, today].
        make_contrat(self.co, date_fin=date(2026, 6, 15))
        ids = [x.id for x in selectors.contrats_a_renouveler(
            self.co, within_days=-5, today=self.today)]
        self.assertEqual(ids, [])

    def test_isolation_societe(self):
        autre = make_company("cr-sel-autre", "Autre")
        make_contrat(autre, date_fin=date(2026, 6, 15))
        ids = [x.id for x in selectors.contrats_a_renouveler(
            self.co, within_days=30, today=self.today)]
        self.assertEqual(ids, [])


# ---------------------------------------------------------------------------
# Sérialiseur — jours_avant_echeance exposé
# ---------------------------------------------------------------------------

class JoursAvantEcheanceSerializerTests(TestCase):
    def setUp(self):
        self.co = make_company("cr-ser", "Ser")
        self.admin = make_user(self.co, "cr-ser-admin", role="admin")

    def test_champ_present_dans_la_reponse(self):
        c = make_contrat(
            self.co, date_fin=date.today() + timedelta(days=10))
        api = auth(self.admin)
        resp = api.get(f"{BASE}{c.id}/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn("jours_avant_echeance", resp.data)
        self.assertEqual(resp.data["jours_avant_echeance"], 10)

    def test_champ_none_sans_date_fin(self):
        c = make_contrat(self.co)
        api = auth(self.admin)
        resp = api.get(f"{BASE}{c.id}/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data["jours_avant_echeance"])


# ---------------------------------------------------------------------------
# Endpoint /a-renouveler/
# ---------------------------------------------------------------------------

class ARenouvelerEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("cr-ep", "EP")
        self.other = make_company("cr-ep-other", "Other")
        self.admin = make_user(self.co, "cr-ep-admin", role="admin")
        # Échéance proche : date_fin = aujourd'hui + 5 jours.
        self.proche = make_contrat(
            self.co, objet="proche",
            date_fin=date.today() + timedelta(days=5))
        # Échéance lointaine (1 an).
        self.loin = make_contrat(
            self.co, objet="loin",
            date_fin=date.today() + timedelta(days=365))
        # Contrat d'une autre société (ne doit jamais apparaître).
        self.autre = make_contrat(
            self.other, objet="autre",
            date_fin=date.today() + timedelta(days=5))

    def test_liste_fenetre_par_defaut(self):
        api = auth(self.admin)
        resp = api.get(RENOUVELER)
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r["id"] for r in rows(resp)}
        self.assertIn(self.proche.id, ids)
        self.assertNotIn(self.loin.id, ids)
        self.assertNotIn(self.autre.id, ids)

    def test_within_large_inclut_loin(self):
        api = auth(self.admin)
        resp = api.get(RENOUVELER, {"within": 400})
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in rows(resp)}
        self.assertIn(self.proche.id, ids)
        self.assertIn(self.loin.id, ids)
        self.assertNotIn(self.autre.id, ids)

    def test_within_invalide_retombe_defaut(self):
        api = auth(self.admin)
        resp = api.get(RENOUVELER, {"within": "abc"})
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in rows(resp)}
        self.assertIn(self.proche.id, ids)
        self.assertNotIn(self.loin.id, ids)

    def test_role_normal_interdit(self):
        normal = make_user(self.co, "cr-ep-normal", role="commercial")
        api = auth(normal)
        resp = api.get(RENOUVELER)
        self.assertEqual(resp.status_code, 403)
