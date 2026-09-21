"""Tests XRH9 — Guichet de demandes RH self-service (attestations à la demande).

Couvre :
* un employé demande une attestation depuis le portail (``employe``/
  ``company`` posés côté serveur) ;
* le RH la traite (``DemandeRHViewSet.traiter``) → le PDF est généré en
  RÉUTILISANT le renderer paie (``apps.paie.builders``), lié à la demande ;
* l'employé télécharge SON PDF ; un AUTRE employé (même société) → 404 ;
* l'attestation de salaire est refusée (403) à un traitant sans
  ``salaires_voir`` ;
* aucun doublon de code PDF (le wrapper délègue à ``apps.paie.builders``).
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.rh.models import DemandeRH, DossierEmploye
from apps.paie.models import ProfilPaie

User = get_user_model()

PORTAIL = '/api/django/rh/portail/'
DEMANDES_RH = '/api/django/rh/demandes-rh/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_employe_user(company, username, matricule):
    user = User.objects.create_user(
        username=username, password='x', company=company, role_legacy='normal')
    dossier = DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P', user=user)
    return user, dossier


def make_rh_user(company, username, permissions=None):
    """Utilisateur RH — porte un rôle fin avec un droit d'écriture (satisfait
    ``is_responsable``) plus, optionnellement, ``salaires_voir``."""
    perms = ['rh_gerer'] + list(permissions or [])
    role = Role.objects.create(
        company=company, nom=f'role-{username}', permissions=perms)
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


FAKE_PDF = b'%PDF-1.4 fake attestation content'


def _fake_store(file):
    return ({
        'file_key': 'attachments/attestation.pdf',
        'filename': 'attestation.pdf', 'size': len(FAKE_PDF),
        'mime': 'application/pdf',
    }, None)


def _fake_fetch(file_key):
    return FAKE_PDF, None


class DemandeRHFlowTests(TestCase):
    def setUp(self):
        self.co = make_company('xrh9-a', 'A')
        self.emp_user, self.dossier = make_employe_user(
            self.co, 'xrh9-emp', 'EMP001')
        self.other_user, self.other_dossier = make_employe_user(
            self.co, 'xrh9-emp2', 'EMP002')
        self.rh = make_rh_user(self.co, 'xrh9-rh')
        self.rh_salaires = make_rh_user(
            self.co, 'xrh9-rh-sal', permissions=['salaires_voir'])
        ProfilPaie.objects.create(company=self.co, employe=self.dossier)
        ProfilPaie.objects.create(company=self.co, employe=self.other_dossier)

    def test_employe_demande_rh_traite_telecharge(self):
        # 1. L'employé soumet une demande d'attestation de travail.
        resp = auth(self.emp_user).post(
            f'{PORTAIL}demander-attestation/',
            {'type': DemandeRH.TypeAttestation.ATTESTATION_TRAVAIL})
        self.assertEqual(resp.status_code, 201, resp.data)
        demande_id = resp.data['id']
        self.assertEqual(resp.data['statut'], 'soumise')

        # 2. Le RH traite la demande — génère le PDF via le renderer paie.
        with patch('apps.paie.builders._html_to_pdf', return_value=FAKE_PDF), \
                patch('apps.records.storage.store_attachment',
                      side_effect=_fake_store):
            resp = auth(self.rh).post(
                f'{DEMANDES_RH}{demande_id}/traiter/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'traitee')
        self.assertIsNotNone(resp.data['attachment_id'])

        # 3. L'employé télécharge SON PDF.
        with patch('apps.records.storage.fetch_attachment',
                   side_effect=_fake_fetch):
            resp = auth(self.emp_user).get(
                f'{PORTAIL}{demande_id}/mes-demandes-telecharger/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

        # 4. Un AUTRE employé ne peut pas télécharger cette demande → 404.
        resp = auth(self.other_user).get(
            f'{PORTAIL}{demande_id}/mes-demandes-telecharger/')
        self.assertEqual(resp.status_code, 404)

        # 5. La demande apparaît dans mes-demandes du bon employé.
        resp = auth(self.emp_user).get(f'{PORTAIL}mes-demandes/')
        self.assertEqual(len(rows(resp)), 1)
        resp = auth(self.other_user).get(f'{PORTAIL}mes-demandes/')
        self.assertEqual(len(rows(resp)), 0)

    def test_attestation_salaire_refusee_sans_salaires_voir(self):
        resp = auth(self.emp_user).post(
            f'{PORTAIL}demander-attestation/',
            {'type': DemandeRH.TypeAttestation.ATTESTATION_SALAIRE})
        self.assertEqual(resp.status_code, 201, resp.data)
        demande_id = resp.data['id']

        # RH SANS salaires_voir → 403.
        resp = auth(self.rh).post(f'{DEMANDES_RH}{demande_id}/traiter/')
        self.assertEqual(resp.status_code, 403)
        demande = DemandeRH.objects.get(pk=demande_id)
        self.assertEqual(demande.statut, 'soumise')

        # RH AVEC salaires_voir → 200.
        with patch('apps.paie.builders._html_to_pdf', return_value=FAKE_PDF), \
                patch('apps.records.storage.store_attachment',
                      side_effect=_fake_store):
            resp = auth(self.rh_salaires).post(
                f'{DEMANDES_RH}{demande_id}/traiter/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_sans_dossier_lie_400(self):
        orphan = User.objects.create_user(
            username='xrh9-orphan', password='x', company=self.co,
            role_legacy='normal')
        resp = auth(orphan).post(
            f'{PORTAIL}demander-attestation/',
            {'type': DemandeRH.TypeAttestation.ATTESTATION_TRAVAIL})
        self.assertEqual(resp.status_code, 400)

    def test_refuser_demande(self):
        resp = auth(self.emp_user).post(
            f'{PORTAIL}demander-attestation/',
            {'type': DemandeRH.TypeAttestation.ATTESTATION_TRAVAIL})
        demande_id = resp.data['id']
        resp = auth(self.rh).post(
            f'{DEMANDES_RH}{demande_id}/refuser/',
            {'motif_refus': 'Dossier incomplet'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'refusee')
        self.assertEqual(resp.data['motif_refus'], 'Dossier incomplet')

    def test_isolation_societe_admin_endpoint(self):
        co_b = make_company('xrh9-b', 'B')
        rh_b = make_rh_user(co_b, 'xrh9-rh-b')
        resp = auth(self.emp_user).post(
            f'{PORTAIL}demander-attestation/',
            {'type': DemandeRH.TypeAttestation.ATTESTATION_TRAVAIL})
        demande_id = resp.data['id']
        resp = auth(rh_b).post(f'{DEMANDES_RH}{demande_id}/traiter/')
        self.assertEqual(resp.status_code, 404)
