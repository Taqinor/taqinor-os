"""Tests PAIE35 — Coffre-fort bulletins (self-service employé, scopé user).

Couvre :
* Un salarié authentifié ne voit QUE ses propres bulletins VALIDÉS via
  ``/api/.../paie/mes-bulletins/`` (rapproché par employe.user).
* Les bulletins d'un collègue ne sont JAMAIS visibles (isolation user, pas
  seulement société).
* Les bulletins en BROUILLON ne sont pas exposés au salarié.
* Un utilisateur sans dossier employé voit une liste vide.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye

User = get_user_model()


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def auth_client(user):
    client = APIClient()
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


class CoffreFortTests(TestCase):
    def setUp(self):
        self.co = make_company('coffre')
        ensure_defaults(self.co)
        # Salarié A (rattaché à un compte user).
        self.user_a = User.objects.create_user(
            username='salarie_a', password='x', company=self.co)
        self.dossier_a = DossierEmploye.objects.create(
            company=self.co, matricule='CA', nom='Salarié', prenom='A',
            user=self.user_a)
        self.profil_a = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier_a,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)
        # Salarié B (autre compte).
        self.user_b = User.objects.create_user(
            username='salarie_b', password='x', company=self.co)
        self.dossier_b = DossierEmploye.objects.create(
            company=self.co, matricule='CB', nom='Salarié', prenom='B',
            user=self.user_b)
        self.profil_b = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier_b,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _bulletin_valide(self, profil):
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def test_salarie_voit_seulement_ses_bulletins(self):
        ba = self._bulletin_valide(self.profil_a)
        self._bulletin_valide(self.profil_b)
        client = auth_client(self.user_a)
        resp = client.get('/api/django/paie/mes-bulletins/')
        self.assertEqual(resp.status_code, 200)
        ids = [b['id'] for b in resp.json().get('results', resp.json())]
        self.assertEqual(ids, [ba.id])

    def test_brouillon_non_expose(self):
        # Bulletin A en brouillon (non validé).
        generer_bulletin(self.profil_a, self.periode)
        client = auth_client(self.user_a)
        resp = client.get('/api/django/paie/mes-bulletins/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json().get('results', resp.json())
        self.assertEqual(len(data), 0)

    def test_acces_direct_collegue_404(self):
        self._bulletin_valide(self.profil_a)
        bb = self._bulletin_valide(self.profil_b)
        client = auth_client(self.user_a)
        # A tente d'accéder au bulletin de B → introuvable (scopé user).
        resp = client.get(f'/api/django/paie/mes-bulletins/{bb.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_user_sans_dossier_voit_vide(self):
        sans_dossier = User.objects.create_user(
            username='sans', password='x', company=self.co)
        self._bulletin_valide(self.profil_a)
        client = auth_client(sans_dossier)
        resp = client.get('/api/django/paie/mes-bulletins/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json().get('results', resp.json())
        self.assertEqual(len(data), 0)
