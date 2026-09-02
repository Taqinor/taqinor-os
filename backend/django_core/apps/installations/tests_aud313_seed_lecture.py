"""AUD313 — une LECTURE n'amorce jamais les gates bloquants CH2.

Défaut d'origine : `StageModeleViewSet.list()` et l'action `etapes` d'un
chantier appelaient `seed_stages(company)` à chaque GET, par n'importe quel
rôle (`IsAnyRole`). Un technicien ouvrant l'onglet « Jalons » créait donc les
10 `DEFAULT_LIFECYCLE_GATES` (dont 4 `bloquant=True`) pour TOUTE la société,
basculant `stages_configures()` à True — et une transition de statut
routinière se voyait rejetée le lendemain par des gates que personne n'avait
configurés.

Après correctif : l'amorçage n'a qu'UN seul point d'entrée, l'action d'écriture
explicite `POST /etapes-chantier/amorcer/`, réservée au Directeur.

Run :
    python manage.py test apps.installations.tests_aud313_seed_lecture -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Installation, StageModele
from apps.installations.services import (
    DEFAULT_LIFECYCLE_GATES, seed_stages, stages_actifs, stages_configures,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/etapes-chantier'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud313-co-{n}', defaults={'nom': f'AUD313 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_directeur(company):
    from apps.roles.models import Role, DIRECTEUR_PERMISSIONS
    role = Role.objects.create(
        company=company, nom='Directeur', est_systeme=True,
        permissions=list(DIRECTEUR_PERMISSIONS))
    u = User.objects.create_user(
        username=f'aud313-dir-{next(_seq)}', password='x', company=company)
    u.role = role
    u.save(update_fields=['role'])
    return u


def make_technicien(company):
    from apps.roles.models import Role, TECHNICIEN_PERMISSIONS
    role = Role.objects.create(
        company=company, nom='Technicien', est_systeme=True,
        permissions=list(TECHNICIEN_PERMISSIONS))
    u = User.objects.create_user(
        username=f'aud313-tech-{next(_seq)}', password='x', company=company)
    u.role = role
    u.save(update_fields=['role'])
    return u


class LectureNAmorcePasTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.technicien = make_technicien(self.company)
        self.directeur = make_directeur(self.company)

    def test_get_liste_etapes_ne_cree_aucune_ligne(self):
        """ROUGE avant AUD313 : ce GET créait les 10 gates par défaut."""
        api = auth(self.technicien)
        r = api.get(f'{BASE}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            StageModele.objects.filter(company=self.company).count(), 0)
        self.assertFalse(stages_configures(self.company))

    def test_get_etapes_du_chantier_ne_cree_aucune_ligne(self):
        """ROUGE avant AUD313 : l'onglet « Jalons » amorçait la société."""
        inst = Installation.objects.create(
            company=self.company, reference='AUD313-1')
        api = auth(self.technicien)
        r = api.get(f'/api/django/installations/chantiers/{inst.id}/etapes/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['etapes'], [])
        self.assertEqual(
            StageModele.objects.filter(company=self.company).count(), 0)
        self.assertFalse(stages_configures(self.company))

    def test_stages_actifs_ne_seme_plus(self):
        self.assertEqual(stages_actifs(self.company), [])
        self.assertEqual(
            StageModele.objects.filter(company=self.company).count(), 0)

    def test_action_amorcer_directeur_seule_porte_dentree(self):
        api = auth(self.directeur)
        r = api.post(f'{BASE}/amorcer/', {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['crees'], len(DEFAULT_LIFECYCLE_GATES))
        self.assertEqual(
            StageModele.objects.filter(company=self.company).count(),
            len(DEFAULT_LIFECYCLE_GATES))
        self.assertTrue(stages_configures(self.company))
        # Idempotent : un second appel ne recrée rien.
        r2 = api.post(f'{BASE}/amorcer/', {}, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertEqual(r2.data['crees'], 0)
        self.assertEqual(
            StageModele.objects.filter(company=self.company).count(),
            len(DEFAULT_LIFECYCLE_GATES))

    def test_action_amorcer_refusee_a_un_non_directeur(self):
        api = auth(self.technicien)
        r = api.post(f'{BASE}/amorcer/', {}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(
            StageModele.objects.filter(company=self.company).count(), 0)

    def test_amorcage_scope_a_la_societe_du_demandeur(self):
        autre = make_company()
        api = auth(self.directeur)
        api.post(f'{BASE}/amorcer/', {}, format='json')
        self.assertEqual(
            StageModele.objects.filter(company=autre).count(), 0)

    def test_lecture_reste_correcte_une_fois_amorcee(self):
        seed_stages(self.company)
        api = auth(self.technicien)
        r = api.get(f'{BASE}/')
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual(len(rows), len(DEFAULT_LIFECYCLE_GATES))
