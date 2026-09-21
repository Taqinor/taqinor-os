"""Tests QHSE22 — Document unique requis avant pose (check + gate).

Couvre :
* ``selectors.document_unique_valide`` — vrai ssi ≥ 1 ``EvaluationRisque``
  ``validee`` non vide pour le chantier ; faux sinon (aucune / brouillon /
  validée mais sans lignes), avec le ``motif`` de refus attendu ;
* scoping société : une évaluation validée d'une AUTRE société ne lève jamais
  l'exigence ;
* ``services.exiger_document_unique`` — laisse passer quand un DUERP validé non
  vide existe, lève ``ValidationError`` (message + code = motif) sinon ;
* l'endpoint ``GET …/evaluations-risque/document-unique-statut/?chantier_id=`` —
  statut correct, ``chantier_id`` requis/entier, garde-fou de rôle
  (IsResponsableOrAdmin → 403), scoping société.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import EvaluationRisque, LigneEvaluationRisque
from apps.qhse.selectors import document_unique_valide
from apps.qhse.services import exiger_document_unique

User = get_user_model()

STATUT_URL = (
    '/api/django/qhse/evaluations-risque/document-unique-statut/')


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_eval(company, chantier_id, statut='validee', reference='DUER-X',
              avec_ligne=True):
    ev = EvaluationRisque.objects.create(
        company=company, titre='DUERP', statut=statut, reference=reference,
        chantier_id=chantier_id, date_evaluation=date(2026, 6, 1))
    if avec_ligne:
        LigneEvaluationRisque.objects.create(
            company=company, evaluation=ev, danger='Chute',
            gravite=4, probabilite=3)
    return ev


# ── Sélecteur : document_unique_valide ───────────────────────────────────────

class DocumentUniqueValideTests(TestCase):
    def setUp(self):
        self.company = make_company('co-duer', 'CoDUER')
        self.other = make_company('co-duer-2', 'CoDUER2')

    def test_duer_validee_non_vide_leve_exigence(self):
        ev = make_eval(self.company, chantier_id=42)
        res = document_unique_valide(self.company, 42)
        self.assertTrue(res['valide'])
        self.assertEqual(res['evaluation_id'], ev.id)
        self.assertEqual(res['reference'], 'DUER-X')
        self.assertEqual(res['nb_validees'], 1)
        self.assertEqual(res['nb_validees_avec_lignes'], 1)
        self.assertIsNone(res['motif'])

    def test_aucune_evaluation_refuse(self):
        res = document_unique_valide(self.company, 7)
        self.assertFalse(res['valide'])
        self.assertIsNone(res['evaluation_id'])
        self.assertEqual(res['nb_validees'], 0)
        self.assertEqual(res['motif'], 'aucune_evaluation')

    def test_brouillon_seul_refuse(self):
        make_eval(self.company, chantier_id=9, statut='brouillon',
                  reference='DUER-B')
        res = document_unique_valide(self.company, 9)
        self.assertFalse(res['valide'])
        self.assertEqual(res['nb_validees'], 0)
        self.assertEqual(res['motif'], 'aucune_validee')

    def test_validee_sans_lignes_refuse(self):
        make_eval(self.company, chantier_id=11, statut='validee',
                  reference='DUER-V', avec_ligne=False)
        res = document_unique_valide(self.company, 11)
        self.assertFalse(res['valide'])
        self.assertEqual(res['nb_validees'], 1)
        self.assertEqual(res['nb_validees_avec_lignes'], 0)
        self.assertEqual(res['motif'], 'validee_sans_lignes')

    def test_prend_la_validee_non_vide_la_plus_recente(self):
        make_eval(self.company, chantier_id=5, statut='validee',
                  reference='DUER-1')
        ev2 = make_eval(self.company, chantier_id=5, statut='validee',
                        reference='DUER-2')
        res = document_unique_valide(self.company, 5)
        self.assertTrue(res['valide'])
        self.assertEqual(res['evaluation_id'], ev2.id)
        self.assertEqual(res['nb_validees'], 2)

    def test_scoping_societe(self):
        # DUERP validé non vide d'une AUTRE société : n'aide pas notre chantier.
        make_eval(self.other, chantier_id=99, statut='validee',
                  reference='DUER-AUTRE')
        res = document_unique_valide(self.company, 99)
        self.assertFalse(res['valide'])
        self.assertEqual(res['motif'], 'aucune_evaluation')


# ── Service : exiger_document_unique (gate) ──────────────────────────────────

class ExigerDocumentUniqueTests(TestCase):
    def setUp(self):
        self.company = make_company('co-exiger', 'CoExiger')

    def test_passe_quand_duer_valide(self):
        make_eval(self.company, chantier_id=3)
        statut = exiger_document_unique(self.company, 3)
        self.assertTrue(statut['valide'])

    def test_leve_validation_error_si_manquant(self):
        with self.assertRaises(ValidationError) as ctx:
            exiger_document_unique(self.company, 404)
        self.assertEqual(ctx.exception.code, 'aucune_evaluation')

    def test_leve_validation_error_si_brouillon(self):
        make_eval(self.company, chantier_id=8, statut='brouillon',
                  reference='DUER-BR')
        with self.assertRaises(ValidationError) as ctx:
            exiger_document_unique(self.company, 8)
        self.assertEqual(ctx.exception.code, 'aucune_validee')


# ── Endpoint : document-unique-statut ────────────────────────────────────────

class DocumentUniqueStatutEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('co-ep', 'CoEP')
        self.other = make_company('co-ep-2', 'CoEP2')
        self.user = make_user(self.company, 'ep-resp')
        self.client_api = auth_client(self.user)

    def test_statut_valide(self):
        make_eval(self.company, chantier_id=21)
        resp = self.client_api.get(STATUT_URL, {'chantier_id': 21})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['valide'])
        self.assertEqual(resp.data['chantier_id'], 21)
        self.assertIsNone(resp.data['motif'])

    def test_statut_refuse(self):
        resp = self.client_api.get(STATUT_URL, {'chantier_id': 22})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['valide'])
        self.assertEqual(resp.data['motif'], 'aucune_evaluation')

    def test_chantier_id_requis(self):
        resp = self.client_api.get(STATUT_URL)
        self.assertEqual(resp.status_code, 400)

    def test_chantier_id_non_entier(self):
        resp = self.client_api.get(STATUT_URL, {'chantier_id': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'ep-normal', role='normal')
        resp = auth_client(normal).get(STATUT_URL, {'chantier_id': 21})
        self.assertEqual(resp.status_code, 403)

    def test_scoping_societe_endpoint(self):
        # Une évaluation validée d'une autre société ne lève pas l'exigence.
        make_eval(self.other, chantier_id=30, statut='validee',
                  reference='DUER-O')
        resp = self.client_api.get(STATUT_URL, {'chantier_id': 30})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['valide'])
