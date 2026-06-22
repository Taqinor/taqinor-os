"""Tests des jalons de projet (PROJ7 — milestones + ``facturation_pct``).

Couvre : la création d'un jalon (avec ``facturation_pct``, ``date_reelle``,
rattachement optionnel phase/tâche) ; la société posée côté serveur (jamais lue
du corps) ; le refus d'un ``facturation_pct`` hors [0, 100] (>100 ET <0, 400) ;
le scoping multi-société (isolation + filtre ``?projet=``, ``?facturation=``) ;
le garde-fou même-société (lier un jalon au projet d'une AUTRE société → 400) ;
le garde-fou phase/tâche d'un AUTRE projet (400) ; le sélecteur
``jalons_for_projet`` ORDONNÉ par date prévue ; l'action ``projets/<id>/jalons/``
scopée société ; et l'accès réservé au palier Administrateur/Responsable
(rôle ``normal`` → 403).

Le ``statut`` est PROPRE à ce module (a_venir/atteint/manque) et ne réutilise
aucune clé de ``STAGES.py`` (règle #2).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    Jalon,
    PhaseProjet,
    Projet,
    Tache,
)

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class JalonSelectorTests(TestCase):
    """Sélecteur ``jalons_for_projet`` — scopé société, ORDONNÉ par date."""

    def setUp(self):
        self.co = make_company('gp-jal-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-JAL', nom='Projet jalon')

    def test_orders_by_date_prevue(self):
        # Insérés dans le DÉSORDRE — le sélecteur doit les rendre par date.
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='C',
            date_prevue='2026-09-01')
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='A',
            date_prevue='2026-07-01')
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='B',
            date_prevue='2026-08-01')
        jalons = list(selectors.jalons_for_projet(self.projet))
        self.assertEqual([j.libelle for j in jalons], ['A', 'B', 'C'])

    def test_scoped_to_projet_company(self):
        autre_co = make_company('gp-jal-sel-2', 'S2')
        autre_projet = Projet.objects.create(
            company=autre_co, code='P-JAL2', nom='Projet 2')
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Mien',
            date_prevue='2026-07-01')
        Jalon.objects.create(
            company=autre_co, projet=autre_projet, libelle='Autre',
            date_prevue='2026-07-01')
        jalons = list(selectors.jalons_for_projet(self.projet))
        self.assertEqual([j.libelle for j in jalons], ['Mien'])


class JalonApiTests(TestCase):
    BASE = '/api/django/gestion-projet/jalons/'

    def setUp(self):
        self.co_a = make_company('gp-jal-a', 'A')
        self.co_b = make_company('gp-jal-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-jal-a')
        self.user_b = make_user(self.co_b, 'gp-jal-b')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-A', nom='Projet A')
        self.projet_b = Projet.objects.create(
            company=self.co_b, code='P-B', nom='Projet B')

    def _payload(self, projet, **over):
        data = {
            'projet': projet.id,
            'libelle': 'Acompte signature',
            'description': 'Versement à la signature',
            'date_prevue': '2026-07-01',
            'date_reelle': '2026-07-03',
            'statut': 'atteint',
            'facturation_pct': '30.00',
        }
        data.update(over)
        return data

    def test_create_forces_company_server_side(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Jalon.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.projet, self.projet_a)

    def test_create_ignores_company_from_body(self):
        # La société du corps doit être ignorée (posée côté serveur).
        payload = self._payload(self.projet_a)
        payload['company'] = self.co_b.id
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Jalon.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_create_persists_facturation_and_dates(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Jalon.objects.get(id=resp.data['id'])
        self.assertEqual(obj.facturation_pct, Decimal('30.00'))
        self.assertEqual(str(obj.date_prevue), '2026-07-01')
        self.assertEqual(str(obj.date_reelle), '2026-07-03')
        self.assertEqual(obj.statut, Jalon.Statut.ATTEINT)

    def test_create_with_phase_and_tache(self):
        phase = PhaseProjet.objects.create(
            company=self.co_a, projet=self.projet_a,
            type_phase='pose', libelle='Pose', ordre=3)
        tache = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='Câblage')
        payload = self._payload(self.projet_a, phase=phase.id, tache=tache.id)
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Jalon.objects.get(id=resp.data['id'])
        self.assertEqual(obj.phase, phase)
        self.assertEqual(obj.tache, tache)

    def test_default_facturation_pct_zero(self):
        payload = self._payload(self.projet_a)
        payload.pop('facturation_pct')
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Jalon.objects.get(id=resp.data['id'])
        self.assertEqual(obj.facturation_pct, Decimal('0'))

    def test_facturation_pct_over_100_rejected(self):
        payload = self._payload(self.projet_a, facturation_pct='150')
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('facturation_pct', resp.data)
        self.assertFalse(Jalon.objects.exists())

    def test_facturation_pct_negative_rejected(self):
        payload = self._payload(self.projet_a, facturation_pct='-5')
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('facturation_pct', resp.data)
        self.assertFalse(Jalon.objects.exists())

    def test_facturation_pct_100_accepted(self):
        payload = self._payload(self.projet_a, facturation_pct='100')
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_create_rejects_cross_tenant_projet(self):
        # user A tente d'attacher un jalon au projet de la société B → 400.
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('projet', resp.data)
        self.assertFalse(
            Jalon.objects.filter(projet=self.projet_b).exists())

    def test_create_rejects_phase_of_other_projet(self):
        autre_projet = Projet.objects.create(
            company=self.co_a, code='P-A2', nom='Projet A2')
        phase = PhaseProjet.objects.create(
            company=self.co_a, projet=autre_projet,
            type_phase='pose', libelle='Pose', ordre=3)
        payload = self._payload(self.projet_a, phase=phase.id)
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('phase', resp.data)

    def test_create_rejects_tache_of_other_projet(self):
        autre_projet = Projet.objects.create(
            company=self.co_a, code='P-A3', nom='Projet A3')
        tache = Tache.objects.create(
            company=self.co_a, projet=autre_projet, libelle='Ailleurs')
        payload = self._payload(self.projet_a, tache=tache.id)
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('tache', resp.data)

    def test_list_isolation(self):
        Jalon.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='A',
            date_prevue='2026-07-01')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_list_filter_by_projet(self):
        other = Projet.objects.create(
            company=self.co_a, code='P-A4', nom='Projet A4')
        Jalon.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='Mien',
            date_prevue='2026-07-01')
        Jalon.objects.create(
            company=self.co_a, projet=other, libelle='Autre',
            date_prevue='2026-07-01')
        resp = auth(self.user_a).get(self.BASE + '?projet=%d' % self.projet_a.id)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['libelle'], 'Mien')

    def test_list_filter_by_facturation(self):
        Jalon.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='Repère',
            date_prevue='2026-07-01', facturation_pct=Decimal('0'))
        Jalon.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='Acompte',
            date_prevue='2026-08-01', facturation_pct=Decimal('40'))
        resp = auth(self.user_a).get(self.BASE + '?facturation=1')
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['libelle'], 'Acompte')

    def test_role_normal_refused(self):
        normal = make_user(self.co_a, 'gp-jal-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class JalonProjetActionTests(TestCase):
    """Action ``projets/<id>/jalons/`` — échéancier scopé société, ordonné."""
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-jal-act-a', 'A')
        self.co_b = make_company('gp-jal-act-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-jal-act-a')
        self.user_b = make_user(self.co_b, 'gp-jal-act-b')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-ACT', nom='Projet action')

    def test_action_returns_jalons_ordered(self):
        Jalon.objects.create(
            company=self.co_a, projet=self.projet, libelle='B',
            date_prevue='2026-08-01')
        Jalon.objects.create(
            company=self.co_a, projet=self.projet, libelle='A',
            date_prevue='2026-07-01')
        resp = auth(self.user_a).get(f'{self.BASE}{self.projet.id}/jalons/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([r['libelle'] for r in resp.data], ['A', 'B'])

    def test_action_cross_tenant_404(self):
        resp = auth(self.user_b).get(f'{self.BASE}{self.projet.id}/jalons/')
        self.assertEqual(resp.status_code, 404)
