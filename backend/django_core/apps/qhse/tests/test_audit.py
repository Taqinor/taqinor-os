"""Tests QHSE16 — Audit + ReponseCritere + score (→ NCR).

Couvre :

* création d'un ``Audit`` : company forcée côté serveur, grille d'une autre
  société refusée ;
* création d'une ``ReponseCritere`` : company forcée, audit/critère d'une autre
  société refusés, unicité (audit, critère) vérifiée ;
* ``calculer_score_audit`` : % pondéré conforme, exclusion des NA, score None
  quand tout est NA ;
* ``lever_ncr_audit`` : NCR créée pour chaque non-conforme, idempotence,
  réponses conformes/NA non concernées ;
* endpoints API ``calculer-score`` et ``lever-ncr`` ;
* isolation entre sociétés.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    Audit, CritereAudit, GrilleAudit, NonConformite, ReponseCritere,
)
from apps.qhse.services import calculer_score_audit, lever_ncr_audit

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────────

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def make_grille(company, nom='Grille test'):
    return GrilleAudit.objects.create(company=company, nom=nom)


def make_critere(company, grille, intitule='Critère', poids=1):
    return CritereAudit.objects.create(
        company=company, grille=grille, intitule=intitule, poids=poids)


def make_audit(company, grille, user=None):
    return Audit.objects.create(
        company=company, grille=grille, auditeur=user)


def make_reponse(company, audit, critere, resultat='na'):
    return ReponseCritere.objects.create(
        company=company, audit=audit, critere=critere, resultat=resultat)


# ── Tests unitaires : services ───────────────────────────────────────────────

class CalculerScoreTests(TestCase):
    """Tests du service ``calculer_score_audit``."""

    def setUp(self):
        self.co = make_company('qhse16-score', 'Score')
        self.grille = make_grille(self.co)
        self.c1 = make_critere(self.co, self.grille, 'C1', poids=3)
        self.c2 = make_critere(self.co, self.grille, 'C2', poids=2)
        self.c3 = make_critere(self.co, self.grille, 'C3', poids=5)

    def test_score_full_conforme(self):
        audit = make_audit(self.co, self.grille)
        make_reponse(self.co, audit, self.c1, 'conforme')
        make_reponse(self.co, audit, self.c2, 'conforme')
        make_reponse(self.co, audit, self.c3, 'conforme')
        calculer_score_audit(audit)
        audit.refresh_from_db()
        self.assertEqual(audit.score, Decimal('100.00'))

    def test_score_partial(self):
        # c1 (poids 3) conforme, c2 (poids 2) non-conforme, c3 (poids 5) NA
        # score = 3 / (3+2) * 100 = 60.00
        audit = make_audit(self.co, self.grille)
        make_reponse(self.co, audit, self.c1, 'conforme')
        make_reponse(self.co, audit, self.c2, 'non_conforme')
        make_reponse(self.co, audit, self.c3, 'na')
        calculer_score_audit(audit)
        audit.refresh_from_db()
        self.assertEqual(audit.score, Decimal('60.00'))

    def test_score_all_na_gives_none(self):
        audit = make_audit(self.co, self.grille)
        make_reponse(self.co, audit, self.c1, 'na')
        make_reponse(self.co, audit, self.c2, 'na')
        calculer_score_audit(audit)
        audit.refresh_from_db()
        self.assertIsNone(audit.score)

    def test_score_zero(self):
        audit = make_audit(self.co, self.grille)
        make_reponse(self.co, audit, self.c1, 'non_conforme')
        make_reponse(self.co, audit, self.c2, 'non_conforme')
        calculer_score_audit(audit)
        audit.refresh_from_db()
        self.assertEqual(audit.score, Decimal('0.00'))


class LeverNcrAuditTests(TestCase):
    """Tests du service ``lever_ncr_audit``."""

    def setUp(self):
        self.co = make_company('qhse16-ncr', 'NCR')
        self.user = make_user(self.co, 'qhse16-ncr')
        self.grille = make_grille(self.co)
        self.c1 = make_critere(self.co, self.grille, 'C1 NC', poids=1)
        self.c2 = make_critere(self.co, self.grille, 'C2 OK', poids=1)
        self.c3 = make_critere(self.co, self.grille, 'C3 NA', poids=1)

    def test_lever_cree_ncr_pour_non_conforme(self):
        audit = make_audit(self.co, self.grille, self.user)
        make_reponse(self.co, audit, self.c1, 'non_conforme')
        make_reponse(self.co, audit, self.c2, 'conforme')
        make_reponse(self.co, audit, self.c3, 'na')

        result = lever_ncr_audit(audit, signale_par=self.user)

        self.assertEqual(len(result['creees']), 1)
        self.assertEqual(len(result['existantes']), 0)
        # La NCR existe bien en base
        ncr = NonConformite.objects.get(id=result['creees'][0])
        self.assertEqual(ncr.company, self.co)
        self.assertIn('C1 NC', ncr.titre)
        self.assertEqual(ncr.origine, f'Audit — {self.grille.nom}')
        # ncr_id stocké sur la réponse
        rep = ReponseCritere.objects.get(audit=audit, critere=self.c1)
        self.assertEqual(rep.ncr_id, ncr.id)

    def test_lever_idempotent(self):
        audit = make_audit(self.co, self.grille, self.user)
        make_reponse(self.co, audit, self.c1, 'non_conforme')

        r1 = lever_ncr_audit(audit, signale_par=self.user)
        r2 = lever_ncr_audit(audit, signale_par=self.user)

        # Première fois : 1 créée, 0 existante
        self.assertEqual(len(r1['creees']), 1)
        self.assertEqual(len(r1['existantes']), 0)
        # Deuxième fois : 0 créée, 1 existante (idempotent)
        self.assertEqual(len(r2['creees']), 0)
        self.assertEqual(len(r2['existantes']), 1)
        # Toujours une seule NCR en base
        self.assertEqual(NonConformite.objects.filter(company=self.co).count(), 1)

    def test_lever_sans_non_conforme(self):
        audit = make_audit(self.co, self.grille, self.user)
        make_reponse(self.co, audit, self.c1, 'conforme')
        make_reponse(self.co, audit, self.c3, 'na')

        result = lever_ncr_audit(audit)
        self.assertEqual(result['creees'], [])
        self.assertEqual(result['existantes'], [])
        self.assertEqual(NonConformite.objects.filter(company=self.co).count(), 0)


# ── Tests API ─────────────────────────────────────────────────────────────────

class AuditApiTests(TestCase):
    AUDITS = '/api/django/qhse/audits/'
    REPONSES = '/api/django/qhse/reponses-critere/'

    def setUp(self):
        self.co = make_company('qhse16-api', 'Api16')
        self.user = make_user(self.co, 'qhse16-api')
        self.grille = make_grille(self.co, 'G API')
        self.c1 = make_critere(self.co, self.grille, 'EPI', poids=3)
        self.c2 = make_critere(self.co, self.grille, 'Câblage', poids=2)

    def test_create_audit_forces_company(self):
        resp = auth(self.user).post(
            self.AUDITS,
            {'grille': self.grille.id, 'date_audit': '2026-06-28'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        audit = Audit.objects.get(id=resp.data['id'])
        self.assertEqual(audit.company, self.co)

    def test_create_audit_other_company_grille_refused(self):
        other = make_company('qhse16-api-b', 'B16')
        other_grille = make_grille(other, 'Grille B')
        resp = auth(self.user).post(
            self.AUDITS,
            {'grille': other_grille.id},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_reponse_forces_company(self):
        audit = make_audit(self.co, self.grille, self.user)
        resp = auth(self.user).post(
            self.REPONSES,
            {'audit': audit.id, 'critere': self.c1.id, 'resultat': 'conforme'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        rep = ReponseCritere.objects.get(id=resp.data['id'])
        self.assertEqual(rep.company, self.co)

    def test_create_reponse_other_company_audit_refused(self):
        other = make_company('qhse16-api-c', 'C16')
        other_grille = make_grille(other)
        other_audit = make_audit(other, other_grille)
        resp = auth(self.user).post(
            self.REPONSES,
            {'audit': other_audit.id, 'critere': self.c1.id, 'resultat': 'na'},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_calculer_score_endpoint(self):
        audit = make_audit(self.co, self.grille, self.user)
        make_reponse(self.co, audit, self.c1, 'conforme')
        make_reponse(self.co, audit, self.c2, 'non_conforme')

        resp = auth(self.user).post(f'{self.AUDITS}{audit.id}/calculer-score/')
        self.assertEqual(resp.status_code, 200, resp.data)
        # 3/(3+2)*100 = 60.00
        self.assertEqual(resp.data['score'], '60.00')

    def test_lever_ncr_endpoint(self):
        audit = make_audit(self.co, self.grille, self.user)
        make_reponse(self.co, audit, self.c1, 'non_conforme')
        make_reponse(self.co, audit, self.c2, 'conforme')

        resp = auth(self.user).post(f'{self.AUDITS}{audit.id}/lever-ncr/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['creees']), 1)
        self.assertEqual(len(resp.data['existantes']), 0)
        # La NCR est bien scopée à la société
        ncr = NonConformite.objects.get(id=resp.data['creees'][0])
        self.assertEqual(ncr.company, self.co)

    def test_lever_ncr_idempotent_via_api(self):
        audit = make_audit(self.co, self.grille, self.user)
        make_reponse(self.co, audit, self.c1, 'non_conforme')

        auth(self.user).post(f'{self.AUDITS}{audit.id}/lever-ncr/')
        resp2 = auth(self.user).post(f'{self.AUDITS}{audit.id}/lever-ncr/')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.data['creees']), 0)
        self.assertEqual(len(resp2.data['existantes']), 1)

    def test_list_isolation(self):
        other = make_company('qhse16-iso', 'Iso16')
        other_grille = make_grille(other)
        make_audit(other, other_grille)
        resp = auth(self.user).get(self.AUDITS)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 0)

    def test_filter_by_grille(self):
        g2 = make_grille(self.co, 'G2')
        make_audit(self.co, self.grille)
        make_audit(self.co, g2)
        resp = auth(self.user).get(f'{self.AUDITS}?grille={self.grille.id}')
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)

    def test_filter_reponses_by_audit(self):
        a1 = make_audit(self.co, self.grille)
        a2 = make_audit(self.co, self.grille)
        make_reponse(self.co, a1, self.c1, 'conforme')
        make_reponse(self.co, a2, self.c1, 'na')
        resp = auth(self.user).get(f'{self.REPONSES}?audit={a1.id}')
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'qhse16-normal', role='normal')
        resp = auth(normal).get(self.AUDITS)
        self.assertEqual(resp.status_code, 403)
