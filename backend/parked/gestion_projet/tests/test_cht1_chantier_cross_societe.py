"""CHT1 — Étanchéité multi-sociétés du lien chantier ↔ projet.

Avant ce fix : ``ProjetChantier.chantier_id`` et ``CompteRenduReunion.
chantier_id`` sont des références LÂCHES (aucun FK dur, donc aucune validation
DRF et aucune contrainte de base). Un utilisateur de la société A pouvait donc
POSTer l'id (devinable) d'un chantier de la société B et le rattacher à SON
projet — puis en agréger les montants (P&L, DGD, budget d'avenant).

Couvre :
* POST ``projet-chantiers`` avec le chantier d'une autre société → 400 ;
* PATCH ``projet-chantiers`` vers un chantier d'une autre société → 400 ;
* non-régression : le chantier de SA PROPRE société passe (201) ;
* idem pour le compte-rendu de réunion (le jumeau du trou), y compris
  ``chantier_id`` absent/nul (champ optionnel : traverse).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import CompteRenduReunion, Projet, ProjetChantier

User = get_user_model()

BASE_PC = '/api/django/gestion-projet/projet-chantiers/'
BASE_CR = '/api/django/gestion-projet/comptes-rendus/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_chantier(company, reference):
    from apps.installations.models import Installation
    return Installation.objects.create(company=company, reference=reference)


class ChantierIdCrossSocieteTests(TestCase):
    def setUp(self):
        self.co_a = make_company('gp-cht1-a', 'A')
        self.co_b = make_company('gp-cht1-b', 'B')
        self.user_a = make_user(self.co_a, 'cht1-a')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-CHT1-A', nom='A')
        self.chantier_a = make_chantier(self.co_a, 'CH-CHT1-A')
        self.chantier_b = make_chantier(self.co_b, 'CH-CHT1-B')

    # ── ProjetChantier ────────────────────────────────────────────────────
    def test_post_projet_chantier_autre_societe_refuse(self):
        api = auth(self.user_a)
        resp = api.post(BASE_PC, {
            'projet': self.projet_a.id,
            'chantier_id': self.chantier_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        self.assertIn('chantier_id', resp.data)
        self.assertFalse(ProjetChantier.objects.filter(
            chantier_id=self.chantier_b.id).exists())

    def test_post_projet_chantier_id_inconnu_refuse(self):
        api = auth(self.user_a)
        resp = api.post(BASE_PC, {
            'projet': self.projet_a.id,
            'chantier_id': 9_999_999,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)

    def test_patch_projet_chantier_vers_autre_societe_refuse(self):
        pc = ProjetChantier.objects.create(
            company=self.co_a, projet=self.projet_a,
            chantier_id=self.chantier_a.id)
        api = auth(self.user_a)
        resp = api.patch(f'{BASE_PC}{pc.id}/', {
            'chantier_id': self.chantier_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        pc.refresh_from_db()
        self.assertEqual(pc.chantier_id, self.chantier_a.id)

    def test_post_projet_chantier_meme_societe_passe(self):
        api = auth(self.user_a)
        resp = api.post(BASE_PC, {
            'projet': self.projet_a.id,
            'chantier_id': self.chantier_a.id,
            'libelle': 'Chantier légitime',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        pc = ProjetChantier.objects.get(id=resp.data['id'])
        self.assertEqual(pc.chantier_id, self.chantier_a.id)
        self.assertEqual(pc.company_id, self.co_a.id)

    # ── CompteRenduReunion (le jumeau du trou) ────────────────────────────
    def test_post_compte_rendu_autre_societe_refuse(self):
        api = auth(self.user_a)
        resp = api.post(BASE_CR, {
            'projet': self.projet_a.id,
            'titre': 'Réunion S12',
            'date_reunion': '2026-03-20',
            'chantier_id': self.chantier_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        self.assertIn('chantier_id', resp.data)
        self.assertFalse(CompteRenduReunion.objects.exists())

    def test_post_compte_rendu_meme_societe_passe(self):
        api = auth(self.user_a)
        resp = api.post(BASE_CR, {
            'projet': self.projet_a.id,
            'titre': 'Réunion S13',
            'date_reunion': '2026-03-27',
            'chantier_id': self.chantier_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        cr = CompteRenduReunion.objects.get(id=resp.data['id'])
        self.assertEqual(cr.chantier_id, self.chantier_a.id)

    def test_post_compte_rendu_sans_chantier_passe(self):
        api = auth(self.user_a)
        resp = api.post(BASE_CR, {
            'projet': self.projet_a.id,
            'titre': 'Réunion sans chantier',
            'date_reunion': '2026-04-03',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertIsNone(
            CompteRenduReunion.objects.get(id=resp.data['id']).chantier_id)
