"""Tests CONTRAT20 — dates clés (préavis) & tacite reconduction.

Couvre :
- Calcul de l'échéance de préavis (``date_fin − preavis_jours``) sur le modèle.
- ``jours_avant_preavis`` (à venir / aujourd'hui / dépassé / non calculable).
- Sélecteur ``contrats_a_preavis`` : dans / hors de la fenêtre, exclusions
  (sans date_fin, sans préavis, déjà traité, résilié/expiré), ordre d'urgence.
- Isolation multi-tenant du sélecteur (société A ne voit pas B).
- Drapeau ``tacite_reconduction`` exposé et persistant.
- Endpoint ``/preavis/?within=N`` : liste scopée société, fenêtre, accès rôle.
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
PREAVIS = BASE + "preavis/"


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
# Modèle — calcul de l'échéance de préavis
# ---------------------------------------------------------------------------

class EcheancePreavisModelTests(TestCase):
    def setUp(self):
        self.co = make_company("cp-mod", "Mod")

    def test_echeance_preavis_calculee(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 12, 31), preavis_jours=30)
        self.assertEqual(c.echeance_preavis(), date(2026, 12, 1))

    def test_echeance_none_sans_date_fin(self):
        c = make_contrat(self.co, preavis_jours=30)
        self.assertIsNone(c.echeance_preavis())

    def test_echeance_none_sans_preavis(self):
        c = make_contrat(self.co, date_fin=date(2026, 12, 31))
        self.assertIsNone(c.echeance_preavis())

    def test_jours_avant_preavis_a_venir(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 12, 31), preavis_jours=30)
        # Échéance = 2026-12-01 ; 10 jours avant.
        self.assertEqual(
            c.jours_avant_preavis(today=date(2026, 11, 21)), 10)

    def test_jours_avant_preavis_depasse(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 12, 31), preavis_jours=30)
        # Échéance = 2026-12-01 ; 5 jours après → négatif.
        self.assertEqual(
            c.jours_avant_preavis(today=date(2026, 12, 6)), -5)

    def test_jours_avant_preavis_non_calculable(self):
        c = make_contrat(self.co, date_fin=date(2026, 12, 31))
        self.assertIsNone(c.jours_avant_preavis(today=date(2026, 1, 1)))


# ---------------------------------------------------------------------------
# Sélecteur — contrats_a_preavis
# ---------------------------------------------------------------------------

class ContratsAPreavisSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("cp-sel", "Sel")
        self.today = date(2026, 6, 1)

    def test_contrat_dans_la_fenetre_remonte(self):
        # Échéance = date_fin(2026-06-25) − 10j = 2026-06-15, dans 14 jours.
        c = make_contrat(
            self.co, date_fin=date(2026, 6, 25), preavis_jours=10)
        ids = [x.id for x in selectors.contrats_a_preavis(
            self.co, within_days=30, today=self.today)]
        self.assertIn(c.id, ids)

    def test_contrat_hors_fenetre_exclu(self):
        # Échéance = 2026-12-21, bien au-delà de 30 jours.
        c = make_contrat(
            self.co, date_fin=date(2026, 12, 31), preavis_jours=10)
        ids = [x.id for x in selectors.contrats_a_preavis(
            self.co, within_days=30, today=self.today)]
        self.assertNotIn(c.id, ids)

    def test_echeance_deja_passee_exclue(self):
        # Échéance = 2026-05-15 < today (2026-06-01).
        c = make_contrat(
            self.co, date_fin=date(2026, 5, 25), preavis_jours=10)
        ids = [x.id for x in selectors.contrats_a_preavis(
            self.co, within_days=30, today=self.today)]
        self.assertNotIn(c.id, ids)

    def test_sans_date_fin_ou_preavis_exclu(self):
        c1 = make_contrat(self.co, objet="sans fin", preavis_jours=10)
        c2 = make_contrat(
            self.co, objet="sans preavis", date_fin=date(2026, 6, 10))
        ids = [x.id for x in selectors.contrats_a_preavis(
            self.co, within_days=60, today=self.today)]
        self.assertNotIn(c1.id, ids)
        self.assertNotIn(c2.id, ids)

    def test_preavis_traite_exclu(self):
        c = make_contrat(
            self.co, date_fin=date(2026, 6, 25), preavis_jours=10,
            preavis_traite=True)
        ids = [x.id for x in selectors.contrats_a_preavis(
            self.co, within_days=30, today=self.today)]
        self.assertNotIn(c.id, ids)

    def test_resilie_ou_expire_exclu(self):
        c1 = make_contrat(
            self.co, date_fin=date(2026, 6, 25), preavis_jours=10,
            statut=Contrat.Statut.RESILIE)
        c2 = make_contrat(
            self.co, date_fin=date(2026, 6, 25), preavis_jours=10,
            statut=Contrat.Statut.EXPIRE)
        ids = [x.id for x in selectors.contrats_a_preavis(
            self.co, within_days=30, today=self.today)]
        self.assertNotIn(c1.id, ids)
        self.assertNotIn(c2.id, ids)

    def test_ordre_par_urgence(self):
        # Échéances : tard = 2026-06-25 ; tot = 2026-06-05.
        tard = make_contrat(
            self.co, objet="tard", date_fin=date(2026, 7, 5),
            preavis_jours=10)
        tot = make_contrat(
            self.co, objet="tot", date_fin=date(2026, 6, 15),
            preavis_jours=10)
        ids = [x.id for x in selectors.contrats_a_preavis(
            self.co, within_days=60, today=self.today)]
        self.assertEqual(ids.index(tot.id) < ids.index(tard.id), True)

    def test_within_negatif_ramene_a_zero(self):
        # Échéance dans 14 jours, mais within<0 → fenêtre [today, today].
        make_contrat(
            self.co, date_fin=date(2026, 6, 25), preavis_jours=10)
        ids = [x.id for x in selectors.contrats_a_preavis(
            self.co, within_days=-5, today=self.today)]
        self.assertEqual(ids, [])

    def test_isolation_societe(self):
        autre = make_company("cp-sel-autre", "Autre")
        make_contrat(
            autre, date_fin=date(2026, 6, 25), preavis_jours=10)
        ids = [x.id for x in selectors.contrats_a_preavis(
            self.co, within_days=30, today=self.today)]
        self.assertEqual(ids, [])


# ---------------------------------------------------------------------------
# Tacite reconduction — persistance via l'API
# ---------------------------------------------------------------------------

class TaciteReconductionTests(TestCase):
    def setUp(self):
        self.co = make_company("cp-tac", "Tac")
        self.admin = make_user(self.co, "cp-tac-admin", role="admin")

    def test_create_avec_tacite_reconduction(self):
        api = auth(self.admin)
        resp = api.post(BASE, {
            "objet": "Bail O&M",
            "date_fin": "2026-12-31",
            "preavis_jours": 60,
            "tacite_reconduction": True,
            "duree_reconduction_mois": 12,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        c = Contrat.objects.get(id=resp.data["id"])
        self.assertTrue(c.tacite_reconduction)
        self.assertEqual(c.duree_reconduction_mois, 12)
        self.assertEqual(c.preavis_jours, 60)
        self.assertEqual(resp.data["echeance_preavis"], "2026-11-01")

    def test_defaut_pas_de_reconduction(self):
        c = make_contrat(self.co, date_fin=date(2026, 12, 31))
        self.assertFalse(c.tacite_reconduction)
        self.assertFalse(c.preavis_traite)


# ---------------------------------------------------------------------------
# Endpoint /preavis/
# ---------------------------------------------------------------------------

class PreavisEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("cp-ep", "EP")
        self.other = make_company("cp-ep-other", "Other")
        self.admin = make_user(self.co, "cp-ep-admin", role="admin")
        # Échéance proche (par rapport à aujourd'hui) : date_fin = aujourd'hui
        # + 5 jours, préavis 3 jours → échéance dans 2 jours.
        self.proche = make_contrat(
            self.co, objet="proche",
            date_fin=date.today() + timedelta(days=5), preavis_jours=3)
        # Échéance lointaine (1 an).
        self.loin = make_contrat(
            self.co, objet="loin",
            date_fin=date.today() + timedelta(days=365), preavis_jours=3)
        # Contrat d'une autre société (ne doit jamais apparaître).
        self.autre = make_contrat(
            self.other, objet="autre",
            date_fin=date.today() + timedelta(days=5), preavis_jours=3)

    def test_preavis_liste_fenetre_par_defaut(self):
        api = auth(self.admin)
        resp = api.get(PREAVIS)
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r["id"] for r in rows(resp)}
        self.assertIn(self.proche.id, ids)
        self.assertNotIn(self.loin.id, ids)
        self.assertNotIn(self.autre.id, ids)

    def test_preavis_within_large_inclut_loin(self):
        api = auth(self.admin)
        resp = api.get(PREAVIS, {"within": 400})
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in rows(resp)}
        self.assertIn(self.proche.id, ids)
        self.assertIn(self.loin.id, ids)
        self.assertNotIn(self.autre.id, ids)

    def test_preavis_within_invalide_retombe_defaut(self):
        api = auth(self.admin)
        resp = api.get(PREAVIS, {"within": "abc"})
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in rows(resp)}
        self.assertIn(self.proche.id, ids)
        self.assertNotIn(self.loin.id, ids)

    def test_preavis_role_normal_interdit(self):
        normal = make_user(self.co, "cp-ep-normal", role="commercial")
        api = auth(normal)
        resp = api.get(PREAVIS)
        self.assertEqual(resp.status_code, 403)
