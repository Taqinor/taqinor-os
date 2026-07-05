"""Tests ZPAI11 — Duplication des rubriques récurrentes vers une nouvelle période.

Couvre :
* ``reporter_elements_periode`` — copie les éléments ``reconduire=True`` de
  M-1 vers la période cible, une seule fois (idempotent : re-run ne
  duplique pas) ; un élément non-reconductible n'est jamais copié ; no-op
  si aucune période précédente.
* API ``periodes/<id>/reporter-elements/``.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import ElementVariable, PeriodePaie, ProfilPaie
from apps.paie.services import ensure_defaults, reporter_elements_periode
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


class ReconductionServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('reconduit')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='RC1', nom='Test', prenom='Reconduit')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'))
        self.periode_m1 = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=5)
        self.periode_m = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.element_reconductible = ElementVariable.objects.create(
            company=self.co, periode=self.periode_m1, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, libelle='Prime de transport',
            montant=Decimal('300'), reconduire=True)
        self.element_non_reconductible = ElementVariable.objects.create(
            company=self.co, periode=self.periode_m1, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, libelle='Prime exceptionnelle',
            montant=Decimal('500'), reconduire=False)

    def test_copie_element_reconductible(self):
        copies = reporter_elements_periode(self.periode_m)
        self.assertEqual(len(copies), 1)
        copie = copies[0]
        self.assertEqual(copie.periode_id, self.periode_m.id)
        self.assertEqual(copie.libelle, 'Prime de transport')
        self.assertEqual(copie.montant, Decimal('300'))
        self.assertEqual(copie.reconduit_depuis_id, self.element_reconductible.id)
        self.assertEqual(copie.source, ElementVariable.SOURCE_MANUEL)

    def test_element_non_reconductible_non_copie(self):
        reporter_elements_periode(self.periode_m)
        self.assertFalse(
            ElementVariable.objects.filter(
                periode=self.periode_m,
                libelle='Prime exceptionnelle').exists())

    def test_idempotent_re_run(self):
        premiere = reporter_elements_periode(self.periode_m)
        self.assertEqual(len(premiere), 1)
        seconde = reporter_elements_periode(self.periode_m)
        self.assertEqual(len(seconde), 0)
        self.assertEqual(
            ElementVariable.objects.filter(
                periode=self.periode_m,
                reconduit_depuis=self.element_reconductible).count(),
            1)

    def test_noop_sans_periode_precedente(self):
        periode_isolee = PeriodePaie.objects.create(
            company=self.co, annee=2030, mois=1)
        copies = reporter_elements_periode(periode_isolee)
        self.assertEqual(copies, [])


class ReconductionApiTests(TestCase):
    BASE = '/api/django/paie/periodes/'

    def setUp(self):
        self.co = make_company('reconduit-api')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='RC2', nom='Test', prenom='Api')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'))
        self.periode_m1 = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=5)
        self.periode_m = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        ElementVariable.objects.create(
            company=self.co, periode=self.periode_m1, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, libelle='Prime de transport',
            montant=Decimal('300'), reconduire=True)
        self.user = make_user(self.co, 'reconduit-api-user')

    def test_action_api(self):
        resp = auth(self.user).post(
            f'{self.BASE}{self.periode_m.id}/reporter-elements/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nombre'], 1)

    def test_action_api_idempotente(self):
        auth(self.user).post(
            f'{self.BASE}{self.periode_m.id}/reporter-elements/',
            {}, format='json')
        resp2 = auth(self.user).post(
            f'{self.BASE}{self.periode_m.id}/reporter-elements/',
            {}, format='json')
        self.assertEqual(resp2.data['nombre'], 0)
