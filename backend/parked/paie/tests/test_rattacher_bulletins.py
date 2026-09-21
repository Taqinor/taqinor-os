"""Tests ZPAI10 — Assistant « Ajouter des bulletins existants à une période ».

Couvre :
* ``rattacher_bulletins`` — rattache des bulletins orphelins (brouillon,
  périodes hors-cycle p. ex.) à une période cible, même société ; refuse une
  période cible clôturée, un bulletin d'une autre société, un bulletin déjà
  validé (figé), un doublon (période, profil).
* API ``periodes/<id>/rattacher-bulletins/``.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    cloturer_periode_paie,
    ensure_defaults,
    generer_bulletin,
    rattacher_bulletins,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_profil(company, matricule):
    dossier = DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom=matricule)
    return ProfilPaie.objects.create(
        company=company, employe=dossier,
        type_remuneration=ProfilPaie.TYPE_MENSUEL,
        salaire_base=Decimal('8000'))


class RattacherBulletinsServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('rattach')
        ensure_defaults(self.co)
        self.p1 = make_profil(self.co, 'RT1')
        self.p2 = make_profil(self.co, 'RT2')
        # Bulletins « orphelins » sur une période hors-cycle distincte.
        self.periode_hors_cycle = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6,
            type_run=PeriodePaie.TYPE_RUN_HORS_CYCLE)
        self.bulletin1 = generer_bulletin(self.p1, self.periode_hors_cycle)
        self.bulletin2 = generer_bulletin(self.p2, self.periode_hors_cycle)
        self.periode_cible = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_rattache_bulletins_orphelins(self):
        rattaches = rattacher_bulletins(
            self.periode_cible, [self.bulletin1.id, self.bulletin2.id])
        self.assertEqual(len(rattaches), 2)
        self.bulletin1.refresh_from_db()
        self.bulletin2.refresh_from_db()
        self.assertEqual(self.bulletin1.periode_id, self.periode_cible.id)
        self.assertEqual(self.bulletin2.periode_id, self.periode_cible.id)

    def test_refuse_periode_cible_cloturee(self):
        cloturer_periode_paie(self.periode_cible)
        with self.assertRaises(ValueError):
            rattacher_bulletins(self.periode_cible, [self.bulletin1.id])

    def test_refuse_bulletin_autre_societe(self):
        autre_co = make_company('rattach-autre')
        ensure_defaults(autre_co)
        p_autre = make_profil(autre_co, 'AUTRE1')
        periode_autre = PeriodePaie.objects.create(
            company=autre_co, annee=2026, mois=6,
            type_run=PeriodePaie.TYPE_RUN_HORS_CYCLE)
        bulletin_autre = generer_bulletin(p_autre, periode_autre)
        with self.assertRaises(ValueError):
            rattacher_bulletins(self.periode_cible, [bulletin_autre.id])

    def test_refuse_bulletin_valide(self):
        valider_bulletin(self.bulletin1)
        with self.assertRaises(ValueError):
            rattacher_bulletins(self.periode_cible, [self.bulletin1.id])

    def test_refuse_doublon_periode_profil(self):
        # p1 a déjà un bulletin sur periode_cible.
        generer_bulletin(self.p1, self.periode_cible)
        with self.assertRaises(ValueError):
            rattacher_bulletins(self.periode_cible, [self.bulletin1.id])

    def test_refuse_liste_vide(self):
        with self.assertRaises(ValueError):
            rattacher_bulletins(self.periode_cible, [])


class RattacherBulletinsApiTests(TestCase):
    BASE = '/api/django/paie/periodes/'

    def setUp(self):
        self.co = make_company('rattach-api')
        ensure_defaults(self.co)
        self.p1 = make_profil(self.co, 'RA1')
        self.periode_hors_cycle = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6,
            type_run=PeriodePaie.TYPE_RUN_HORS_CYCLE)
        self.bulletin1 = generer_bulletin(self.p1, self.periode_hors_cycle)
        self.periode_cible = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.user = make_user(self.co, 'rattach-api-user')

    def test_action_api(self):
        resp = auth(self.user).post(
            f'{self.BASE}{self.periode_cible.id}/rattacher-bulletins/',
            {'bulletins': [self.bulletin1.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['id'], self.bulletin1.id)

    def test_action_api_liste_vide_400(self):
        resp = auth(self.user).post(
            f'{self.BASE}{self.periode_cible.id}/rattacher-bulletins/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)
