"""Tests WIR65 — calendrier marketing unifié : les 5 SOURCE_TYPES.

``CalendrierMarketingView`` n'agrégeait que ``Campagne`` + ``PostSocial`` ; les
filtres etape_sequence/evenement/relance du frontend affichaient toujours zéro.
On vérifie ici que les 5 sources apparaissent réellement quand elles ont des
données, avec les bonnes dates, la fenêtre ?from=&to= respectée et le scope
société étanche.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.marketing.models import (
    Campagne, EtapeSequence, EvenementMarketing, InscriptionSequence,
    PostSocial, RelanceDevisAbandonne, SequenceRelance,
)

User = get_user_model()

URL = "/api/django/compta/calendrier-marketing/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def aware(y, m, d, h=12):
    return timezone.make_aware(datetime.datetime(y, m, d, h, 0))


class CalendrierMarketingSourcesTests(TestCase):
    def setUp(self):
        self.co = make_company("wir65", "WIR65")
        self.admin = make_user(self.co, "wir65-admin")

        # campagne (planifiee_le) — dans la fenêtre, brouillon → éditable.
        self.campagne = Campagne.objects.create(
            company=self.co, nom="Réveil base froide", canal="email",
            planifiee_le=aware(2026, 7, 10))
        # post social (date_planifiee).
        self.post = PostSocial.objects.create(
            company=self.co, reseau="facebook", texte="Promo été",
            date_planifiee=aware(2026, 7, 11))
        # étape de séquence due : declenchee_le + delai_jours.
        self.seq = SequenceRelance.objects.create(
            company=self.co, nom="Relance devis")
        self.etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=3,
            canal="email")
        self.insc = InscriptionSequence.objects.create(
            company=self.co, sequence=self.seq, lead_id=1,
            etape_courante=self.etape)
        # declenchee_le est auto_now_add → forcé via update pour un dû stable.
        InscriptionSequence.objects.filter(id=self.insc.id).update(
            declenchee_le=aware(2026, 7, 5))
        # événement marketing (date_debut).
        self.evenement = EvenementMarketing.objects.create(
            company=self.co, nom="Salon solaire", date_debut=aware(2026, 7, 15))
        # relance devis abandonné (date_relance auto_now_add → forcée).
        self.relance = RelanceDevisAbandonne.objects.create(
            company=self.co, devis_id=42, devis_reference="DV-42",
            jours_sans_reponse=7, canal="email")
        RelanceDevisAbandonne.objects.filter(id=self.relance.id).update(
            date_relance=aware(2026, 7, 20))

    def _events(self, params=None):
        resp = auth(self.admin).get(URL, params or {"from": "2026-07-01", "to": "2026-07-31"})
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.data["events"]

    def test_les_5_sources_apparaissent(self):
        events = self._events()
        by_source = {e["source"]: e for e in events}
        self.assertEqual(
            set(by_source),
            {"campagne", "post_social", "etape_sequence", "evenement", "relance"})

    def test_etape_sequence_due_calculee(self):
        events = self._events()
        etape = next(e for e in events if e["source"] == "etape_sequence")
        # declenchee_le 2026-07-05 + delai_jours 3 = 2026-07-08.
        self.assertEqual(etape["date"], "2026-07-08")
        self.assertEqual(etape["obj_id"], self.insc.id)
        self.assertEqual(etape["link_type"], "etape_sequence")

    def test_evenement_et_relance_datees(self):
        events = self._events()
        evenement = next(e for e in events if e["source"] == "evenement")
        relance = next(e for e in events if e["source"] == "relance")
        self.assertEqual(evenement["date"], "2026-07-15")
        self.assertEqual(evenement["title"], "Salon solaire")
        self.assertEqual(relance["date"], "2026-07-20")
        self.assertIn("DV-42", relance["title"])

    def test_fenetre_exclut_hors_plage(self):
        # Fenêtre qui ne contient AUCUNE des dates ci-dessus.
        events = self._events({"from": "2026-08-01", "to": "2026-08-31"})
        self.assertEqual(events, [])

    def test_scope_societe_etanche(self):
        autre = make_company("wir65-b", "WIR65 B")
        autre_admin = make_user(autre, "wir65-b-admin")
        resp = auth(autre_admin).get(URL, {"from": "2026-07-01", "to": "2026-07-31"})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["events"], [])
