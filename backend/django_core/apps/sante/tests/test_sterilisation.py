"""NTSAN23 — stérilisation, traçabilité des instruments et lien QHSE.

Critère d'acceptation : un cycle marqué NON CONFORME crée une `NonConformite`
QHSE LIÉE — testé de bout en bout (API santé → événement `core.events` →
récepteur qhse → NCR en base). Le test importe `qhse.models` uniquement pour
ASSERTER ; le code de production de `sante` ne l'importe jamais (test AST).
"""
import ast
import datetime as dt
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company

from apps.qhse.models import NonConformite
from apps.sante.models import CycleSterilisation, InstrumentSterilise
from apps.sante.services import appliquer_statut_cycle_sterilisation

User = get_user_model()
DATE_CYCLE = timezone.make_aware(dt.datetime(2026, 8, 12, 7, 30))


class SterilisationFixtureMixin:
    def setUp(self):
        super().setUp()
        self.company, _ = Company.objects.get_or_create(
            slug='sante-sterilisation-co',
            defaults={'nom': 'Clinique Stérilisation'})
        self.user = User.objects.create_user(
            username='operateur@sante-sterilisation.ma', password='x',
            company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)


class NTSAN23ModelesTests(SterilisationFixtureMixin, TestCase):
    def test_cycle_conforme_n_ouvre_aucune_ncr(self):
        resp = self.client.post(
            '/api/django/sante/cycles-sterilisation/',
            {'numero_cycle': 'CY-001', 'date_cycle': DATE_CYCLE.isoformat(),
             'autoclave_ref': 'AUTO-1', 'statut': 'conforme'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(
            NonConformite.objects.filter(company=self.company).exists())

    def test_operateur_pose_cote_serveur(self):
        resp = self.client.post(
            '/api/django/sante/cycles-sterilisation/',
            {'numero_cycle': 'CY-002', 'date_cycle': DATE_CYCLE.isoformat()},
            format='json')
        self.assertEqual(resp.status_code, 201)
        cycle = CycleSterilisation.objects.get(pk=resp.data['id'])
        self.assertEqual(cycle.operateur, self.user)
        self.assertEqual(cycle.company, self.company)

    def test_instruments_rattaches_au_cycle(self):
        cycle = CycleSterilisation.objects.create(
            company=self.company, numero_cycle='CY-003',
            date_cycle=DATE_CYCLE)
        resp = self.client.post(
            '/api/django/sante/instruments-sterilises/',
            {'cycle': cycle.id, 'instrument_ref': 'DAV-42',
             'kit_ref': 'KIT-CHIR-1'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(cycle.instruments.count(), 1)
        self.assertEqual(
            InstrumentSterilise.objects.get(pk=resp.data['id']).company,
            self.company)


class NTSAN23LienQhseTests(SterilisationFixtureMixin, TestCase):
    def test_cycle_cree_non_conforme_ouvre_une_ncr_liee(self):
        """Critère NTSAN23, bout en bout : API → événement → NCR liée."""
        resp = self.client.post(
            '/api/django/sante/cycles-sterilisation/',
            {'numero_cycle': 'CY-010', 'date_cycle': DATE_CYCLE.isoformat(),
             'autoclave_ref': 'AUTO-2', 'statut': 'non_conforme'},
            format='json')
        self.assertEqual(resp.status_code, 201)

        ncr = NonConformite.objects.get(company=self.company)
        self.assertEqual(ncr.cycle_sterilisation_id, resp.data['id'])
        self.assertIn('CY-010', ncr.titre)
        self.assertIn('AUTO-2', ncr.description)
        self.assertEqual(ncr.gravite, NonConformite.Gravite.MAJEURE)
        self.assertEqual(ncr.statut, NonConformite.Statut.OUVERTE)
        self.assertEqual(ncr.signale_par, self.user)

    def test_bascule_conforme_vers_non_conforme_ouvre_la_ncr(self):
        cycle = CycleSterilisation.objects.create(
            company=self.company, numero_cycle='CY-011',
            date_cycle=DATE_CYCLE, autoclave_ref='AUTO-3')
        self.assertFalse(NonConformite.objects.exists())

        resp = self.client.patch(
            f'/api/django/sante/cycles-sterilisation/{cycle.id}/',
            {'statut': 'non_conforme'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            NonConformite.objects.filter(
                company=self.company, cycle_sterilisation_id=cycle.id).count(),
            1)

    def test_editer_un_cycle_deja_non_conforme_ne_duplique_pas_la_ncr(self):
        cycle = CycleSterilisation.objects.create(
            company=self.company, numero_cycle='CY-012',
            date_cycle=DATE_CYCLE,
            statut=CycleSterilisation.Statut.NON_CONFORME)
        appliquer_statut_cycle_sterilisation(cycle, user=self.user)
        self.assertEqual(NonConformite.objects.count(), 1)

        resp = self.client.patch(
            f'/api/django/sante/cycles-sterilisation/{cycle.id}/',
            {'autoclave_ref': 'AUTO-4'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(NonConformite.objects.count(), 1)

    def test_repasser_en_conforme_n_emet_rien(self):
        cycle = CycleSterilisation.objects.create(
            company=self.company, numero_cycle='CY-013',
            date_cycle=DATE_CYCLE,
            statut=CycleSterilisation.Statut.NON_CONFORME)
        appliquer_statut_cycle_sterilisation(cycle, user=self.user)

        resp = self.client.patch(
            f'/api/django/sante/cycles-sterilisation/{cycle.id}/',
            {'statut': 'conforme'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(NonConformite.objects.count(), 1)

    def test_ncr_scopee_sur_la_societe_du_cycle(self):
        autre, _ = Company.objects.get_or_create(
            slug='sante-sterilisation-autre',
            defaults={'nom': 'Clinique Stérilisation Autre'})
        cycle_autre = CycleSterilisation.objects.create(
            company=autre, numero_cycle='CY-020', date_cycle=DATE_CYCLE,
            statut=CycleSterilisation.Statut.NON_CONFORME)
        appliquer_statut_cycle_sterilisation(cycle_autre)

        self.assertFalse(
            NonConformite.objects.filter(company=self.company).exists())
        self.assertEqual(
            NonConformite.objects.filter(company=autre).count(), 1)

    def test_evenement_au_catalogue(self):
        """NTPLT12 — tout signal du bus porte une entrée de catalogue."""
        from core.event_catalog import CATALOG

        entree = CATALOG['cycle_sterilisation_non_conforme']
        self.assertEqual(entree['payload'], ['cycle', 'company', 'user'])


class NTSAN23FrontiereCrossAppTests(TestCase):
    def test_sante_n_importe_jamais_qhse_models(self):
        """La NCR est ouverte par l'ABONNÉ qhse, pas par un import de sante.

        Contrôle sur les IMPORTS RÉELS (AST) des modules de production de
        ``apps/sante`` — les modules de TEST importent légitimement
        ``qhse.models`` pour ASSERTER le résultat."""
        racine = Path(__file__).resolve().parent.parent
        for chemin in racine.rglob('*.py'):
            if chemin.name.startswith('test') or 'tests' in chemin.parts:
                continue
            if 'migrations' in chemin.parts:
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                modules = []
                if isinstance(noeud, ast.Import):
                    modules = [alias.name for alias in noeud.names]
                elif isinstance(noeud, ast.ImportFrom):
                    modules = [noeud.module or '']
                for module in modules:
                    self.assertFalse(
                        module.startswith('apps.qhse'),
                        f'{chemin.name} importe {module} : passer par '
                        f'core.events.')
