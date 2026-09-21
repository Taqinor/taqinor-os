"""Tests QHSE31 — Analyse d'incident (arbre des causes) → CAPA.

Couvre :

* ``AnalyseIncident`` rattachée à un ``Incident`` (scopée société ; ``company``
  et ``analyste`` posés côté serveur ; une seule analyse par incident) ;
* l'arbre des causes (``CauseIncident`` parent/enfant de la MÊME analyse ; un
  parent d'une autre analyse est refusé) ;
* ``generer_capa_depuis_analyse`` / endpoint ``…/generer-capa/`` : crée une
  NCR-pont depuis l'incident à la première génération (mirroir du linkage
  NCR→CAPA existant), la réutilise ensuite, et crée une ``ActionCorrective
  Preventive`` rattachée ;
* l'isolation société (404 hors société) et le palier de rôle (Responsable/Admin
  uniquement).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    ActionCorrectivePreventive, AnalyseIncident, CauseIncident, Incident,
    NonConformite,
)
from apps.qhse.services import generer_capa_depuis_analyse

User = get_user_model()


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


def make_incident(company, titre='Chute de hauteur'):
    return Incident.objects.create(
        company=company, titre=titre, reference='INC-2026-0001')


def make_analyse(company, incident, analyste=None):
    return AnalyseIncident.objects.create(
        company=company, incident=incident, analyste=analyste)


class AnalyseIncidentServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse31-svc', 'Svc')
        self.user = make_user(self.co, 'qhse31-svc')
        self.incident = make_incident(self.co)
        self.analyse = make_analyse(self.co, self.incident, self.user)

    def test_one_analysis_per_incident(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AnalyseIncident.objects.create(
                    company=self.co, incident=self.incident)

    def test_cause_tree_parent_child(self):
        fait = CauseIncident.objects.create(
            company=self.co, analyse=self.analyse,
            type_cause=CauseIncident.TypeCause.FAIT, libelle='Glissade')
        immediate = CauseIncident.objects.create(
            company=self.co, analyse=self.analyse, parent=fait,
            type_cause=CauseIncident.TypeCause.CAUSE_IMMEDIATE,
            libelle='Sol mouillé')
        racine = CauseIncident.objects.create(
            company=self.co, analyse=self.analyse, parent=immediate,
            type_cause=CauseIncident.TypeCause.CAUSE_RACINE,
            libelle='Absence de signalisation')
        self.assertEqual(list(fait.enfants.all()), [immediate])
        self.assertEqual(racine.parent, immediate)
        self.assertEqual(self.analyse.causes.count(), 3)

    def test_generer_capa_creates_bridge_ncr_then_reuses(self):
        CauseIncident.objects.create(
            company=self.co, analyse=self.analyse,
            type_cause=CauseIncident.TypeCause.CAUSE_RACINE,
            libelle='Procédure absente')
        capa1 = generer_capa_depuis_analyse(self.analyse)
        self.analyse.refresh_from_db()
        # NCR-pont créée et rattachée à l'analyse.
        self.assertIsNotNone(self.analyse.non_conformite_id)
        ncr_id = self.analyse.non_conformite_id
        self.assertEqual(capa1.non_conformite_id, ncr_id)
        # Cause racine reportée dans la CAPA.
        self.assertEqual(capa1.cause_racine, 'Procédure absente')
        # Société portée par la CAPA.
        self.assertEqual(capa1.company_id, self.co.id)
        # Deuxième génération : même NCR-pont réutilisée, pas de doublon.
        capa2 = generer_capa_depuis_analyse(self.analyse)
        self.analyse.refresh_from_db()
        self.assertEqual(self.analyse.non_conformite_id, ncr_id)
        self.assertEqual(capa2.non_conformite_id, ncr_id)
        self.assertEqual(
            NonConformite.objects.filter(company=self.co).count(), 1)
        self.assertEqual(
            ActionCorrectivePreventive.objects.filter(
                non_conformite_id=ncr_id).count(), 2)


class AnalyseIncidentApiTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse31-api', 'Api')
        self.user = make_user(self.co, 'qhse31-api')
        self.incident = make_incident(self.co)

    def test_create_sets_company_and_analyste_server_side(self):
        resp = auth(self.user).post(
            '/api/django/qhse/analyses-incident/',
            {'incident': self.incident.id, 'methode': 'arbre_des_causes',
             'description': 'Déroulé', 'company': 999, 'analyste': 999},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        analyse = AnalyseIncident.objects.get(id=resp.data['id'])
        self.assertEqual(analyse.company_id, self.co.id)
        self.assertEqual(analyse.analyste_id, self.user.id)

    def test_cause_parent_must_share_analyse(self):
        a1 = make_analyse(self.co, self.incident, self.user)
        incident2 = Incident.objects.create(
            company=self.co, titre='Autre', reference='INC-2026-0002')
        a2 = make_analyse(self.co, incident2, self.user)
        parent_other = CauseIncident.objects.create(
            company=self.co, analyse=a2,
            type_cause=CauseIncident.TypeCause.FAIT, libelle='X')
        resp = auth(self.user).post(
            '/api/django/qhse/causes-incident/',
            {'analyse': a1.id, 'parent': parent_other.id,
             'type_cause': 'cause_immediate', 'libelle': 'Y'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_generer_capa_endpoint(self):
        analyse = make_analyse(self.co, self.incident, self.user)
        resp = auth(self.user).post(
            f'/api/django/qhse/analyses-incident/{analyse.id}/generer-capa/',
            {'description': 'Mettre en place une procédure'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['description'],
                         'Mettre en place une procédure')
        analyse.refresh_from_db()
        self.assertIsNotNone(analyse.non_conformite_id)

    def test_company_isolation(self):
        other = make_company('qhse31-other', 'Other')
        other_user = make_user(other, 'qhse31-other')
        analyse = make_analyse(self.co, self.incident, self.user)
        # L'utilisateur d'une autre société ne voit pas l'analyse (404).
        resp = auth(other_user).get(
            f'/api/django/qhse/analyses-incident/{analyse.id}/')
        self.assertEqual(resp.status_code, 404)
        # Et ne peut pas générer de CAPA dessus (404, hors société).
        gen = auth(other_user).post(
            f'/api/django/qhse/analyses-incident/{analyse.id}/generer-capa/',
            {}, format='json')
        self.assertEqual(gen.status_code, 404)

    def test_role_normal_refuse(self):
        analyse = make_analyse(self.co, self.incident, self.user)
        normal = make_user(self.co, 'qhse31-normal', role='normal')
        resp = auth(normal).get(
            f'/api/django/qhse/analyses-incident/{analyse.id}/')
        self.assertEqual(resp.status_code, 403)
