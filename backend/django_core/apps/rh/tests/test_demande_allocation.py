"""Tests ZRH13 — demande d'allocation de congés self-service.

Couvre : demande via le portail, validation (crédite le solde disponible),
refus (aucun effet), un employé ne demande que pour lui-même, isolation
tenant, gate admin sur la liste/validation.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DemandeAllocation, DossierEmploye, SoldeConge, TypeAbsence

User = get_user_model()

PORTAIL = '/api/django/rh/portail/'
ALLOC = '/api/django/rh/demandes-allocation/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DemandeAllocationTests(TestCase):
    def setUp(self):
        self.co_a = make_company('da-a', 'A')
        self.co_b = make_company('da-b', 'B')
        self.user_a = make_user(self.co_a, 'da-user-a')
        self.responsable = make_user(
            self.co_a, 'da-resp', role='responsable')
        self.user_b = make_user(self.co_b, 'da-user-b')
        self.dossier = DossierEmploye.objects.create(
            company=self.co_a, matricule='DA1', nom='N', prenom='P',
            user=self.user_a)
        self.type_absence = TypeAbsence.objects.create(
            company=self.co_a, code='RTT', libelle='RTT')

    def test_demande_via_portail(self):
        resp = auth(self.user_a).post(f'{PORTAIL}mes-allocations/', {
            'type_absence': self.type_absence.id, 'jours': '2',
            'motif': 'RTT accumulés',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['employe'], self.dossier.id)
        self.assertEqual(resp.data['statut'], 'soumise')

    def test_validation_credite_solde(self):
        demande = DemandeAllocation.objects.create(
            company=self.co_a, employe=self.dossier,
            type_absence=self.type_absence, jours=Decimal('3'))
        annee = timezone.now().year
        resp = auth(self.responsable).post(f'{ALLOC}{demande.id}/valider/')
        self.assertEqual(resp.status_code, 200, resp.data)
        solde = SoldeConge.objects.get(
            company=self.co_a, employe=self.dossier, annee=annee)
        self.assertEqual(solde.acquis, Decimal('3'))
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeAllocation.Statut.VALIDEE)

    def test_refus_aucun_effet(self):
        demande = DemandeAllocation.objects.create(
            company=self.co_a, employe=self.dossier,
            type_absence=self.type_absence, jours=Decimal('2'))
        resp = auth(self.responsable).post(f'{ALLOC}{demande.id}/refuser/')
        self.assertEqual(resp.status_code, 200, resp.data)
        annee = timezone.now().year
        self.assertFalse(
            SoldeConge.objects.filter(
                company=self.co_a, employe=self.dossier,
                annee=annee).exists())
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeAllocation.Statut.REFUSEE)

    def test_employe_demande_que_pour_lui(self):
        autre_dossier = DossierEmploye.objects.create(
            company=self.co_a, matricule='DA2', nom='Autre', prenom='X')
        resp = auth(self.user_a).post(f'{PORTAIL}mes-allocations/', {
            'employe': autre_dossier.id,
            'type_absence': self.type_absence.id, 'jours': '1',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        # ``employe`` forcé côté serveur au dossier du compte appelant.
        self.assertEqual(resp.data['employe'], self.dossier.id)

    def test_isolation_tenant(self):
        resp = auth(self.user_b).get(ALLOC)
        rows_data = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertEqual(len(rows_data), 0)

    def test_liste_gate_admin(self):
        resp = auth(self.user_a).get(ALLOC)
        self.assertEqual(resp.status_code, 403)

    def test_double_validation_erreur(self):
        demande = DemandeAllocation.objects.create(
            company=self.co_a, employe=self.dossier,
            type_absence=self.type_absence, jours=Decimal('1'),
            statut=DemandeAllocation.Statut.VALIDEE)
        resp = auth(self.responsable).post(f'{ALLOC}{demande.id}/valider/')
        self.assertEqual(resp.status_code, 400)
