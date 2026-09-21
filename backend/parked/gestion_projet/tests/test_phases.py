"""Tests des phases de projet (PROJ4 — WBS étude/appro/pose/MES/réception).

Couvre : le service ``instancier_phases_standard`` crée les 5 phases dans
l'ordre et reste IDEMPOTENT (un second appel ne duplique rien et préserve les
phases déjà éditées) ; l'action ``instancier-phases`` du projet ; la persistance
des dates / statut / avancement ; la société posée côté serveur (jamais du
corps) ; le scoping multi-société (isolation + filtre ``?projet=``) ; le
garde-fou même-société (lier une phase au projet d'une AUTRE société → 400) ;
et l'accès réservé au palier Administrateur/Responsable (rôle ``normal`` → 403).

Le ``type_phase`` est PROPRE à ce module et ne réutilise aucune clé de
``STAGES.py`` (règle #2).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import PhaseProjet, Projet

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
    return data['results'] if isinstance(data, dict) and 'results' in data else data


EXPECTED_ORDER = ['etude', 'appro', 'pose', 'mes', 'reception']


class InstancierPhasesServiceTests(TestCase):
    """Service ``instancier_phases_standard`` — 5 phases ordonnées, idempotent."""

    def setUp(self):
        self.co = make_company('gp-ph-svc', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-PH', nom='Projet phases')

    def test_creates_five_phases_in_order(self):
        phases = services.instancier_phases_standard(self.projet)
        self.assertEqual(len(phases), 5)
        self.assertEqual([p.type_phase for p in phases], EXPECTED_ORDER)
        # ordre croissant 1..5 conforme à l'ordre de réalisation.
        self.assertEqual([p.ordre for p in phases], [1, 2, 3, 4, 5])
        # société dérivée du projet, statut/avancement par défaut.
        for p in phases:
            self.assertEqual(p.company, self.co)
            self.assertEqual(p.statut, PhaseProjet.Statut.A_VENIR)
            self.assertEqual(p.avancement_pct, 0)

    def test_idempotent_no_duplicates(self):
        services.instancier_phases_standard(self.projet)
        services.instancier_phases_standard(self.projet)
        self.assertEqual(
            PhaseProjet.objects.filter(projet=self.projet).count(), 5)

    def test_idempotent_preserves_edited_phase(self):
        services.instancier_phases_standard(self.projet)
        etude = PhaseProjet.objects.get(
            projet=self.projet, type_phase=PhaseProjet.TypePhase.ETUDE)
        etude.statut = PhaseProjet.Statut.TERMINEE
        etude.avancement_pct = 100
        etude.save(update_fields=['statut', 'avancement_pct'])
        # second appel : ne touche pas la phase déjà éditée.
        services.instancier_phases_standard(self.projet)
        etude.refresh_from_db()
        self.assertEqual(etude.statut, PhaseProjet.Statut.TERMINEE)
        self.assertEqual(etude.avancement_pct, 100)
        self.assertEqual(
            PhaseProjet.objects.filter(projet=self.projet).count(), 5)


class InstancierPhasesActionTests(TestCase):
    """Action ``instancier-phases`` du ProjetViewSet (scopée société)."""
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-ph-act-a', 'A')
        self.co_b = make_company('gp-ph-act-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-ph-act-a')
        self.user_b = make_user(self.co_b, 'gp-ph-act-b')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-ACT', nom='Projet action')

    def test_action_creates_five_phases(self):
        resp = auth(self.user_a).post(
            f'{self.BASE}{self.projet.id}/instancier-phases/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 5)
        self.assertEqual(
            [r['type_phase'] for r in resp.data], EXPECTED_ORDER)

    def test_action_is_idempotent(self):
        api = auth(self.user_a)
        api.post(f'{self.BASE}{self.projet.id}/instancier-phases/')
        api.post(f'{self.BASE}{self.projet.id}/instancier-phases/')
        self.assertEqual(
            PhaseProjet.objects.filter(projet=self.projet).count(), 5)

    def test_action_cross_tenant_404(self):
        resp = auth(self.user_b).post(
            f'{self.BASE}{self.projet.id}/instancier-phases/')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            PhaseProjet.objects.filter(projet=self.projet).count(), 0)

    def test_action_role_normal_refused(self):
        normal = make_user(self.co_a, 'gp-ph-act-normal', role='normal')
        resp = auth(normal).post(
            f'{self.BASE}{self.projet.id}/instancier-phases/')
        self.assertEqual(resp.status_code, 403)


class PhaseProjetApiTests(TestCase):
    BASE = '/api/django/gestion-projet/phases/'

    def setUp(self):
        self.co_a = make_company('gp-ph-a', 'A')
        self.co_b = make_company('gp-ph-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-ph-a')
        self.user_b = make_user(self.co_b, 'gp-ph-b')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-A', nom='Projet A')
        self.projet_b = Projet.objects.create(
            company=self.co_b, code='P-B', nom='Projet B')

    def _payload(self, projet):
        return {
            'projet': projet.id,
            'type_phase': 'pose',
            'libelle': 'Pose modules',
            'ordre': 3,
            'date_debut_prevue': '2026-07-01',
            'date_fin_prevue': '2026-07-10',
            'date_debut_reelle': '2026-07-02',
            'date_fin_reelle': '2026-07-12',
            'statut': 'en_cours',
            'avancement_pct': 40,
        }

    def test_create_forces_company_server_side(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PhaseProjet.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.projet, self.projet_a)

    def test_create_persists_dates_statut_avancement(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PhaseProjet.objects.get(id=resp.data['id'])
        self.assertEqual(str(obj.date_debut_prevue), '2026-07-01')
        self.assertEqual(str(obj.date_fin_prevue), '2026-07-10')
        self.assertEqual(str(obj.date_debut_reelle), '2026-07-02')
        self.assertEqual(str(obj.date_fin_reelle), '2026-07-12')
        self.assertEqual(obj.statut, PhaseProjet.Statut.EN_COURS)
        self.assertEqual(obj.avancement_pct, 40)

    def test_create_rejects_cross_tenant_projet(self):
        # user A tente d'attacher une phase au projet de la société B → 400.
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('projet', resp.data)
        self.assertFalse(
            PhaseProjet.objects.filter(projet=self.projet_b).exists())

    def test_list_isolation(self):
        PhaseProjet.objects.create(
            company=self.co_a, projet=self.projet_a,
            type_phase='etude', libelle='Étude', ordre=1)
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_list_filter_by_projet(self):
        services.instancier_phases_standard(self.projet_a)
        other = Projet.objects.create(
            company=self.co_a, code='P-A2', nom='Projet A2')
        services.instancier_phases_standard(other)
        resp = auth(self.user_a).get(self.BASE + '?projet=%d' % self.projet_a.id)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 5)
        self.assertTrue(
            all(r['projet'] == self.projet_a.id for r in data))

    def test_avancement_over_100_rejected(self):
        payload = self._payload(self.projet_a)
        payload['avancement_pct'] = 150
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('avancement_pct', resp.data)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'gp-ph-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
