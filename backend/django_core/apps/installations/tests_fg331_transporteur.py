"""
FG331 — Transporteurs & tarifs de transport.

Couvre :
  * création : société/`created_by` posés serveur ; nom requis ;
  * affectation d'un transporteur + coût à une livraison (FG329) ;
  * un transporteur d'une autre société rejeté sur la livraison ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg331_transporteur -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    Installation, Livraison, Transporteur,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg331-co-{n}', defaults={'nom': nom or f'FG331 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg331-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company, ref='TR1'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'tr-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        statut=Installation.Statut.RECEPTIONNE,
        type_installation='residentiel',
        puissance_installee_kwc=Decimal('6.5'))


class TestTransporteur(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_create_sets_company_server_side(self):
        resp = self.api.post(f'{BASE}/transporteurs/', {
            'nom': 'Transit Express', 'type_transporteur': 'tiers',
            'tarif_base': '350.00', 'company': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        t = Transporteur.objects.get(id=resp.data['id'])
        self.assertEqual(t.company_id, self.company.id)
        self.assertEqual(t.created_by_id, self.user.id)

    def test_blank_nom_rejected(self):
        resp = self.api.post(f'{BASE}/transporteurs/', {
            'nom': '  ',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_assign_to_livraison(self):
        transporteur = Transporteur.objects.create(
            company=self.company, nom='T1')
        inst = make_installation(self.company)
        liv = Livraison.objects.create(
            company=self.company, installation=inst, reference='LIV-T1')
        resp = self.api.patch(f'{BASE}/livraisons/{liv.id}/', {
            'transporteur': transporteur.id, 'cout_transport': '420.00',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        liv.refresh_from_db()
        self.assertEqual(liv.transporteur_id, transporteur.id)
        self.assertEqual(str(liv.cout_transport), '420.00')

    def test_transporteur_other_company_rejected_on_livraison(self):
        other = make_company()
        t_other = Transporteur.objects.create(company=other, nom='Other')
        inst = make_installation(self.company)
        liv = Livraison.objects.create(
            company=self.company, installation=inst, reference='LIV-T2')
        resp = self.api.patch(f'{BASE}/livraisons/{liv.id}/', {
            'transporteur': t_other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)  # ENF45 a : mise à jour = 409


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/transporteurs/', {'nom': 'X'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        Transporteur.objects.create(company=self.company, nom='Secret')
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/transporteurs/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)

    def test_technicien_livre_ne_lit_pas_tarif_base(self):
        # ALEC6 (D-ALEC-1) — tarif INTERNE masqué sans `prix_achat_voir`.
        from apps.roles.models import Role
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS, TECHNICIEN_PERMISSIONS

        def fin(nom, perms):
            role = Role.objects.create(company=self.company, nom=nom, permissions=list(perms))
            return User.objects.create_user(
                username=f'fg331-{next(_seq)}', password='x', company=self.company, role=role)
        t = Transporteur.objects.create(company=self.company, nom='T', tarif_base=Decimal('350'))
        tech, dirigeant = auth(fin('Tech ALEC6', TECHNICIEN_PERMISSIONS)), auth(fin('Dir ALEC6', DIRECTEUR_PERMISSIONS))
        for url in (f'{BASE}/transporteurs/', f'{BASE}/transporteurs/{t.id}/'):
            rep = tech.get(url)
            self.assertEqual(rep.status_code, 200, rep.content)
            ligne = rep.data['results'][0] if 'results' in rep.data else rep.data
            self.assertNotIn('tarif_base', ligne)
        rep = dirigeant.patch(f'{BASE}/transporteurs/{t.id}/', {'tarif_base': '400.00'}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(Decimal(dirigeant.get(f'{BASE}/transporteurs/{t.id}/').data['tarif_base']), Decimal('400'))


class TestChampsStrictsFuzzR12(TestCase):
    """api-fuzz r12 (CI #956) — `note` entier (POST ou PATCH) → 400, comme le
    schéma le déclare ; une requête valide est inchangée."""

    def setUp(self):
        self.company = make_company()
        self.api = auth(make_user(self.company))

    def test_note_entier_refuse_en_400(self):
        resp = self.api.post(f'{BASE}/transporteurs/', {
            'nom': 'T', 'type_transporteur': 'interne', 'note': 0,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('note', resp.data)
        t = Transporteur.objects.create(company=self.company, nom='T2')
        resp = self.api.patch(f'{BASE}/transporteurs/{t.id}/', {'note': 0}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.patch(f'{BASE}/transporteurs/{t.id}/', {'note': 'ok', 'active': False},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
