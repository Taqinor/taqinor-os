"""Tests QHSE20 — Tableau de bord « ISO 9001 readiness ».

Couvre :

* le sélecteur ``iso9001_readiness`` : score global pondéré + ventilation par
  critère (NCR clôturées, CAPA dans les délais, audits réalisés, procédures
  publiées, couverture ITP, satisfaction client) avec leurs clauses ISO ;
* garde anti-division-par-zéro : société VIDE → tous les critères ``no_data``,
  score global 0, aucun plantage ;
* scoping société : les données d'une autre société n'entrent jamais dans le
  calcul ;
* endpoint ``GET …/iso9001-readiness/`` (lecture seule) ;
* garde-fou de rôle (``IsResponsableOrAdmin`` → 403 pour un rôle normal).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    ActionCorrectivePreventive, Audit, GrilleAudit,
    NonConformite, PlanInspectionChantier, PlanInspectionModele,
    PointControleModele, ProcedureQualite, ReleveControle,
    RetourClientQualite,
)
from apps.qhse.selectors import iso9001_readiness

User = get_user_model()

URL = '/api/django/qhse/iso9001-readiness/'


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def make_ncr(company, statut=NonConformite.Statut.OUVERTE):
    return NonConformite.objects.create(
        company=company, titre='NCR', statut=statut)


def make_capa(company, ncr, statut=ActionCorrectivePreventive.Statut.A_FAIRE,
              echeance=None):
    return ActionCorrectivePreventive.objects.create(
        company=company, non_conformite=ncr, description='CAPA',
        statut=statut, echeance=echeance)


def make_audit(company, statut=Audit.Statut.BROUILLON):
    grille = GrilleAudit.objects.create(company=company, nom='Grille')
    return Audit.objects.create(company=company, grille=grille, statut=statut)


def make_procedure(company, reference, statut, version=1):
    return ProcedureQualite.objects.create(
        company=company, reference=reference, titre='Proc',
        version=version, statut=statut)


def make_releve(company, conforme):
    modele = PlanInspectionModele.objects.create(company=company, nom='ITP')
    point = PointControleModele.objects.create(
        company=company, plan=modele, ordre=0, intitule='Point')
    plan = PlanInspectionChantier.objects.create(
        company=company, modele=modele, chantier_id=1)
    return ReleveControle.objects.create(
        company=company, plan_chantier=plan, point=point, conforme=conforme)


def make_retour(company, note):
    return RetourClientQualite.objects.create(
        company=company, note_satisfaction=note, date_retour=date(2026, 6, 1))


def crit(data, cle):
    return next(c for c in data['criteres'] if c['cle'] == cle)


# ── Sélecteur : société vide (garde anti-division-par-zéro) ─────────────────

class EmptyCompanyTests(TestCase):
    def setUp(self):
        self.company = make_company('iso-empty', 'Empty')

    def test_empty_company_no_crash(self):
        data = iso9001_readiness(self.company)
        self.assertEqual(data['score_global'], 0.0)
        self.assertEqual(data['niveau'], 'initial')
        self.assertEqual(data['nb_criteres'], 6)
        self.assertEqual(data['nb_criteres_sans_donnee'], 6)

    def test_empty_company_all_criteres_no_data(self):
        data = iso9001_readiness(self.company)
        for c in data['criteres']:
            self.assertIsNone(c['score'], c['cle'])
            self.assertTrue(c['no_data'], c['cle'])
            self.assertEqual(c['score_effectif'], 0.0, c['cle'])

    def test_criteres_carry_iso_clauses(self):
        data = iso9001_readiness(self.company)
        clauses = {c['cle']: c['clause_iso'] for c in data['criteres']}
        self.assertEqual(clauses['ncr_cloturees'], '10.2')
        self.assertEqual(clauses['capa_dans_delais'], '10.2')
        self.assertEqual(clauses['audits_realises'], '9.2')
        self.assertEqual(clauses['procedures_publiees'], '7.5')
        self.assertEqual(clauses['couverture_itp'], '8.5/8.6')
        self.assertEqual(clauses['satisfaction_client'], '9.1.2')


# ── Sélecteur : critères chiffrés à partir de données semées ────────────────

class ReadinessScoreTests(TestCase):
    def setUp(self):
        self.company = make_company('iso-score', 'Score')

    def test_ncr_cloturees_pct(self):
        make_ncr(self.company, NonConformite.Statut.CLOTUREE)
        make_ncr(self.company, NonConformite.Statut.CLOTUREE)
        make_ncr(self.company, NonConformite.Statut.OUVERTE)
        data = iso9001_readiness(self.company)
        c = crit(data, 'ncr_cloturees')
        self.assertAlmostEqual(c['score'], 66.67, places=2)
        self.assertFalse(c['no_data'])
        self.assertEqual(c['detail']['total'], 3)
        self.assertEqual(c['detail']['cloturees'], 2)

    def test_capa_dans_delais_inverse_des_retards(self):
        ncr = make_ncr(self.company)
        today = timezone.localdate()
        # 1 en retard (échue + à faire), 1 dans les délais (échéance future).
        make_capa(self.company, ncr,
                  statut=ActionCorrectivePreventive.Statut.A_FAIRE,
                  echeance=today - timedelta(days=5))
        make_capa(self.company, ncr,
                  statut=ActionCorrectivePreventive.Statut.A_FAIRE,
                  echeance=today + timedelta(days=5))
        data = iso9001_readiness(self.company)
        c = crit(data, 'capa_dans_delais')
        self.assertEqual(c['detail']['en_retard'], 1)
        self.assertEqual(c['detail']['dans_delais'], 1)
        self.assertEqual(c['score'], 50.0)

    def test_capa_realisee_jamais_en_retard(self):
        ncr = make_ncr(self.company)
        today = timezone.localdate()
        # Échue mais RÉALISÉE → compte comme dans les délais (non relançable).
        make_capa(self.company, ncr,
                  statut=ActionCorrectivePreventive.Statut.REALISEE,
                  echeance=today - timedelta(days=10))
        data = iso9001_readiness(self.company)
        c = crit(data, 'capa_dans_delais')
        self.assertEqual(c['detail']['en_retard'], 0)
        self.assertEqual(c['score'], 100.0)

    def test_audits_realises_pct(self):
        make_audit(self.company, Audit.Statut.CLOS)
        make_audit(self.company, Audit.Statut.EN_COURS)
        data = iso9001_readiness(self.company)
        c = crit(data, 'audits_realises')
        self.assertEqual(c['score'], 50.0)
        self.assertEqual(c['detail']['clos'], 1)

    def test_procedures_publiees_pct(self):
        make_procedure(
            self.company, 'PRO-1', ProcedureQualite.Statut.EN_VIGUEUR)
        make_procedure(
            self.company, 'PRO-2', ProcedureQualite.Statut.BROUILLON)
        data = iso9001_readiness(self.company)
        c = crit(data, 'procedures_publiees')
        self.assertEqual(c['score'], 50.0)
        self.assertEqual(c['detail']['references'], 2)
        self.assertEqual(c['detail']['en_vigueur'], 1)

    def test_couverture_itp_pct(self):
        make_releve(self.company, conforme=True)
        make_releve(self.company, conforme=False)
        make_releve(self.company, conforme=None)  # pas encore relevé
        data = iso9001_readiness(self.company)
        c = crit(data, 'couverture_itp')
        # 2 relevés renseignés (conforme non nul) sur 3.
        self.assertAlmostEqual(c['score'], 66.67, places=2)
        self.assertEqual(c['detail']['releves'], 3)
        self.assertEqual(c['detail']['renseignes'], 2)

    def test_satisfaction_client_pct(self):
        make_retour(self.company, 5)
        make_retour(self.company, 4)
        data = iso9001_readiness(self.company)
        c = crit(data, 'satisfaction_client')
        # moyenne 4.5 / 5 → 90 %.
        self.assertEqual(c['score'], 90.0)
        self.assertEqual(c['detail']['nb_retours'], 2)

    def test_score_global_pondere_et_niveau(self):
        # Critères pleins à 100 % chacun → score global 100, niveau avancé.
        make_ncr(self.company, NonConformite.Statut.CLOTUREE)
        ncr = NonConformite.objects.first()
        make_capa(self.company, ncr,
                  statut=ActionCorrectivePreventive.Statut.VERIFIEE)
        make_audit(self.company, Audit.Statut.CLOS)
        make_procedure(
            self.company, 'PRO-1', ProcedureQualite.Statut.EN_VIGUEUR)
        make_releve(self.company, conforme=True)
        make_retour(self.company, 5)
        data = iso9001_readiness(self.company)
        self.assertEqual(data['score_global'], 100.0)
        self.assertEqual(data['niveau'], 'avance')
        self.assertEqual(data['nb_criteres_sans_donnee'], 0)


# ── Scoping société ─────────────────────────────────────────────────────────

class ScopingTests(TestCase):
    def test_other_company_data_excluded(self):
        company = make_company('iso-scope', 'Scope')
        other = make_company('iso-scope-other', 'Other')
        make_ncr(company, NonConformite.Statut.CLOTUREE)
        # Bruit de l'autre société : ne doit pas compter.
        make_ncr(other, NonConformite.Statut.OUVERTE)
        make_audit(other, Audit.Statut.CLOS)
        data = iso9001_readiness(company)
        c = crit(data, 'ncr_cloturees')
        self.assertEqual(c['detail']['total'], 1)
        self.assertEqual(c['score'], 100.0)
        # Aucune donnée d'audit côté `company` → critère sans donnée.
        self.assertTrue(crit(data, 'audits_realises')['no_data'])


# ── Endpoint API ────────────────────────────────────────────────────────────

class ReadinessEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('iso-api', 'Api')
        self.user = make_user(self.company, 'iso-api-user')

    def test_endpoint_returns_dashboard(self):
        make_ncr(self.company, NonConformite.Statut.CLOTUREE)
        resp = auth(self.user).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('score_global', resp.data)
        self.assertIn('criteres', resp.data)
        self.assertEqual(resp.data['nb_criteres'], 6)

    def test_endpoint_empty_company_ok(self):
        resp = auth(self.user).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['score_global'], 0.0)

    def test_endpoint_scoped_to_user_company(self):
        other = make_company('iso-api-other', 'Other')
        # Donnée chez l'autre société : invisible pour `self.user`.
        make_audit(other, Audit.Statut.CLOS)
        resp = auth(self.user).get(URL)
        c = next(
            x for x in resp.data['criteres'] if x['cle'] == 'audits_realises')
        self.assertTrue(c['no_data'])

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'iso-normal', role='normal')
        resp = auth(normal).get(URL)
        self.assertEqual(resp.status_code, 403)
