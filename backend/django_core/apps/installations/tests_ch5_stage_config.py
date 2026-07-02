"""
CH5 — Configuration des étapes/gates de chantier (Paramètres, Directeur-only).

Couvre :
  * le Directeur configure le flux d'étapes de SA société (ajout / retrait /
    réordonnancement / bloquant-consultatif / exigences) ;
  * un NON-Directeur (Responsable, Technicien) ne peut pas écrire (403) mais
    peut lire ;
  * une étape système protégée ne se supprime pas (409) — elle se désactive ;
  * scope multi-société (une société ne configure jamais les étapes d'une autre)
    + amorçage à la première consultation.

Run :
    python manage.py test apps.installations.tests_ch5_stage_config -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import StageModele

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/etapes-chantier'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ch5-co-{n}', defaults={'nom': f'CH5 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_directeur(company):
    """Compte Directeur : rôle système « Directeur » (porte le signal
    `journal_activite_voir`)."""
    from apps.roles.models import Role, DIRECTEUR_PERMISSIONS
    role = Role.objects.create(
        company=company, nom='Directeur', est_systeme=True,
        permissions=list(DIRECTEUR_PERMISSIONS))
    u = User.objects.create_user(
        username=f'ch5-dir-{next(_seq)}', password='x', company=company)
    u.role = role
    u.save(update_fields=['role'])
    return u


def make_responsable(company):
    """Compte NON-Directeur : rôle Technicien responsable (écrit ses chantiers
    mais ne configure pas les gates)."""
    from apps.roles.models import Role, TECHNICIEN_RESP_PERMISSIONS
    role = Role.objects.create(
        company=company, nom='Technicien responsable', est_systeme=True,
        permissions=list(TECHNICIEN_RESP_PERMISSIONS))
    u = User.objects.create_user(
        username=f'ch5-resp-{next(_seq)}', password='x', company=company)
    u.role = role
    u.save(update_fields=['role'])
    return u


class StageConfigRoleGateTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.directeur = make_directeur(self.company)
        self.responsable = make_responsable(self.company)

    def test_lecture_amorce_le_cycle(self):
        api = auth(self.responsable)
        r = api.get(f'{BASE}/')
        self.assertEqual(r.status_code, 200)
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual(len(rows), 10)  # cycle PV international amorcé

    def test_directeur_ajoute_une_etape(self):
        api = auth(self.directeur)
        api.get(f'{BASE}/')  # amorce
        r = api.post(f'{BASE}/', {
            'cle': 'controle_qualite', 'libelle': 'Contrôle qualité',
            'ordre': 5, 'bloquant': True, 'exige_photos': True,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(StageModele.objects.filter(
            company=self.company, cle='controle_qualite').exists())

    def test_directeur_reordonne_et_bascule_bloquant(self):
        api = auth(self.directeur)
        api.get(f'{BASE}/')
        stage = StageModele.objects.get(
            company=self.company, cle='autorisations')
        r = api.patch(f'{BASE}/{stage.id}/',
                      {'ordre': 99, 'bloquant': False}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        stage.refresh_from_db()
        self.assertEqual(stage.ordre, 99)
        self.assertFalse(stage.bloquant)

    def test_non_directeur_ne_peut_pas_ecrire(self):
        api = auth(self.responsable)
        api.get(f'{BASE}/')
        stage = StageModele.objects.filter(company=self.company).first()
        r = api.patch(f'{BASE}/{stage.id}/', {'ordre': 42}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        r2 = api.post(f'{BASE}/', {
            'cle': 'x', 'libelle': 'X', 'ordre': 1}, format='json')
        self.assertEqual(r2.status_code, 403)

    def test_etape_protegee_ne_se_supprime_pas(self):
        api = auth(self.directeur)
        api.get(f'{BASE}/')
        stage = StageModele.objects.get(
            company=self.company, cle='mise_en_service')
        self.assertTrue(stage.protege)
        r = api.delete(f'{BASE}/{stage.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        # Elle se DÉSACTIVE en revanche.
        r2 = api.patch(f'{BASE}/{stage.id}/', {'actif': False}, format='json')
        self.assertEqual(r2.status_code, 200)
        stage.refresh_from_db()
        self.assertFalse(stage.actif)

    def test_etape_personnalisee_supprimable(self):
        api = auth(self.directeur)
        api.get(f'{BASE}/')
        stage = StageModele.objects.create(
            company=self.company, cle='perso', libelle='Perso', ordre=20)
        r = api.delete(f'{BASE}/{stage.id}/')
        self.assertEqual(r.status_code, 204)


class StageConfigScopeTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.autre = make_company()
        self.directeur = make_directeur(self.company)

    def test_scope_par_societe(self):
        api = auth(self.directeur)
        api.get(f'{BASE}/')  # amorce la société du directeur
        # Une étape d'une AUTRE société est invisible/inaccessible.
        from apps.installations.services import seed_stages
        seed_stages(self.autre)
        autre_stage = StageModele.objects.filter(company=self.autre).first()
        r = api.get(f'{BASE}/{autre_stage.id}/')
        self.assertEqual(r.status_code, 404)
        r2 = api.patch(f'{BASE}/{autre_stage.id}/',
                       {'ordre': 1}, format='json')
        self.assertEqual(r2.status_code, 404)
