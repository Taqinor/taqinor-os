"""Tests des tâches & sous-tâches (PROJ5 — WBS auto-référente).

Couvre : la création d'une tâche puis d'une SOUS-TÂCHE via le FK ``parent``
(arborescence WBS de profondeur arbitraire) ; la récupération de l'arbre via le
sélecteur ``arbre_taches`` et l'action ``projets/<id>/taches/`` ; la société
posée côté serveur (jamais lue du corps) ; le scoping multi-société (isolation +
filtres) ; les garde-fous même-société et même-projet pour ``parent`` et
``phase`` ; le refus d'une tâche parente d'une AUTRE société (400) ; et l'accès
réservé au palier Administrateur/Responsable (rôle ``normal`` → 403).

Le ``statut`` de la tâche est PROPRE à ce module
(a_faire/en_cours/termine/bloque) et ne réutilise aucune clé de ``STAGES.py``
(règle #2).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import PhaseProjet, Projet, Tache

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


class TacheSelectorTreeTests(TestCase):
    """Sélecteur ``arbre_taches`` — arborescence imbriquée, profondeur libre."""

    def setUp(self):
        self.co = make_company('gp-ta-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-TA', nom='Projet tâches')

    def test_arbre_imbrique_profondeur_arbitraire(self):
        racine = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Lot 1',
            code_wbs='1', ordre=1)
        enfant = Tache.objects.create(
            company=self.co, projet=self.projet, parent=racine,
            libelle='Sous 1.1', code_wbs='1.1', ordre=1)
        Tache.objects.create(
            company=self.co, projet=self.projet, parent=enfant,
            libelle='Sous 1.1.1', code_wbs='1.1.1', ordre=1)
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Lot 2',
            code_wbs='2', ordre=2)

        arbre = selectors.arbre_taches(self.projet)
        # Deux racines, ordonnées par ``ordre``.
        self.assertEqual([n['code_wbs'] for n in arbre], ['1', '2'])
        lot1 = arbre[0]
        self.assertEqual(len(lot1['sous_taches']), 1)
        sous = lot1['sous_taches'][0]
        self.assertEqual(sous['code_wbs'], '1.1')
        # Profondeur 3 : la sous-tâche porte elle-même une sous-tâche.
        self.assertEqual(len(sous['sous_taches']), 1)
        self.assertEqual(sous['sous_taches'][0]['code_wbs'], '1.1.1')
        # Lot 2 sans enfant.
        self.assertEqual(arbre[1]['sous_taches'], [])

    def test_arbre_une_seule_requete(self):
        racine = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='R', ordre=1)
        Tache.objects.create(
            company=self.co, projet=self.projet, parent=racine,
            libelle='C', ordre=1)
        with self.assertNumQueries(1):
            selectors.arbre_taches(self.projet)


class TacheApiTests(TestCase):
    BASE = '/api/django/gestion-projet/taches/'

    def setUp(self):
        self.co_a = make_company('gp-ta-a', 'A')
        self.co_b = make_company('gp-ta-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-ta-a')
        self.user_b = make_user(self.co_b, 'gp-ta-b')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-A', nom='Projet A')
        self.projet_b = Projet.objects.create(
            company=self.co_b, code='P-B', nom='Projet B')

    def _payload(self, projet, **over):
        data = {
            'projet': projet.id,
            'code_wbs': '1',
            'libelle': 'Lot principal',
            'ordre': 1,
            'statut': 'en_cours',
            'avancement_pct': 25,
            'charge_estimee': '4.50',
        }
        data.update(over)
        return data

    def test_create_forces_company_server_side(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Tache.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.projet, self.projet_a)
        self.assertIsNone(obj.parent)

    def test_create_ignores_company_in_body(self):
        # ``company`` dans le corps est IGNORÉE : la société reste celle de
        # l'utilisateur (posée côté serveur), jamais lue du corps.
        payload = self._payload(self.projet_a)
        payload['company'] = self.co_b.id
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Tache.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_create_persists_fields(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Tache.objects.get(id=resp.data['id'])
        self.assertEqual(obj.code_wbs, '1')
        self.assertEqual(obj.statut, Tache.Statut.EN_COURS)
        self.assertEqual(obj.avancement_pct, 25)
        self.assertEqual(str(obj.charge_estimee), '4.50')

    def test_create_subtask_with_parent(self):
        parent_resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_a), format='json')
        parent_id = parent_resp.data['id']
        sub = self._payload(
            self.projet_a, parent=parent_id, code_wbs='1.1',
            libelle='Sous-tâche')
        resp = auth(self.user_a).post(self.BASE, sub, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Tache.objects.get(id=resp.data['id'])
        self.assertEqual(obj.parent_id, parent_id)
        # related_name ``sous_taches`` côté parent.
        parent = Tache.objects.get(id=parent_id)
        self.assertEqual(parent.sous_taches.count(), 1)
        self.assertEqual(resp.data['nb_sous_taches'], 0)

    def test_rejects_cross_tenant_projet(self):
        resp = auth(self.user_a).post(
            self.BASE, self._payload(self.projet_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('projet', resp.data)
        self.assertFalse(
            Tache.objects.filter(projet=self.projet_b).exists())

    def test_rejects_cross_tenant_parent(self):
        # Parent d'une AUTRE société → 400 (jamais 500 / fuite cross-tenant).
        autre = Tache.objects.create(
            company=self.co_b, projet=self.projet_b, libelle='Étranger')
        payload = self._payload(self.projet_a, parent=autre.id)
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('parent', resp.data)

    def test_rejects_parent_other_projet(self):
        # Parent d'une autre tâche de la MÊME société mais d'un AUTRE projet.
        autre_projet = Projet.objects.create(
            company=self.co_a, code='P-A2', nom='Projet A2')
        parent = Tache.objects.create(
            company=self.co_a, projet=autre_projet, libelle='Ailleurs')
        payload = self._payload(self.projet_a, parent=parent.id)
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('parent', resp.data)

    def test_rejects_phase_other_projet(self):
        phase = PhaseProjet.objects.create(
            company=self.co_a, projet=self.projet_a, type_phase='pose',
            ordre=1)
        autre_projet = Projet.objects.create(
            company=self.co_a, code='P-A3', nom='Projet A3')
        payload = self._payload(autre_projet, phase=phase.id)
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('phase', resp.data)

    def test_accepts_phase_same_projet(self):
        phase = PhaseProjet.objects.create(
            company=self.co_a, projet=self.projet_a, type_phase='pose',
            ordre=1)
        payload = self._payload(self.projet_a, phase=phase.id)
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Tache.objects.get(id=resp.data['id'])
        self.assertEqual(obj.phase_id, phase.id)

    def test_avancement_over_100_rejected(self):
        payload = self._payload(self.projet_a, avancement_pct=150)
        resp = auth(self.user_a).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('avancement_pct', resp.data)

    def test_list_isolation(self):
        Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='À moi')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_list_filter_by_projet(self):
        Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='T1', ordre=1)
        other = Projet.objects.create(
            company=self.co_a, code='P-A4', nom='Projet A4')
        Tache.objects.create(
            company=self.co_a, projet=other, libelle='T-other', ordre=1)
        resp = auth(self.user_a).get(self.BASE + '?projet=%d' % self.projet_a.id)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertTrue(all(r['projet'] == self.projet_a.id for r in data))

    def test_list_filter_racines(self):
        racine = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='R', ordre=1)
        Tache.objects.create(
            company=self.co_a, projet=self.projet_a, parent=racine,
            libelle='C', ordre=1)
        resp = auth(self.user_a).get(self.BASE + '?racines=1')
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], racine.id)

    def test_list_filter_parent(self):
        racine = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='R', ordre=1)
        child = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, parent=racine,
            libelle='C', ordre=1)
        resp = auth(self.user_a).get(self.BASE + '?parent=%d' % racine.id)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual([r['id'] for r in data], [child.id])

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'gp-ta-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class TacheTreeActionTests(TestCase):
    """Action ``projets/<id>/taches/`` — arbre WBS scopé société."""
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-ta-act-a', 'A')
        self.co_b = make_company('gp-ta-act-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-ta-act-a')
        self.user_b = make_user(self.co_b, 'gp-ta-act-b')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-ACT', nom='Projet action')

    def test_action_returns_nested_tree(self):
        racine = Tache.objects.create(
            company=self.co_a, projet=self.projet, libelle='Lot 1',
            code_wbs='1', ordre=1)
        Tache.objects.create(
            company=self.co_a, projet=self.projet, parent=racine,
            libelle='Sous 1.1', code_wbs='1.1', ordre=1)
        resp = auth(self.user_a).get(f'{self.BASE}{self.projet.id}/taches/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['code_wbs'], '1')
        self.assertEqual(len(resp.data[0]['sous_taches']), 1)

    def test_action_cross_tenant_404(self):
        resp = auth(self.user_b).get(f'{self.BASE}{self.projet.id}/taches/')
        self.assertEqual(resp.status_code, 404)
