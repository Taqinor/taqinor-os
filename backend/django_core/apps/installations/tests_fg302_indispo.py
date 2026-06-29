"""
FG302 — Calendrier de disponibilité des ressources terrain.

``IndisponibiliteRessource`` (congé/formation/arrêt/autre) marque un TECHNICIEN
(utilisateur) OU une CAMIONNETTE (``stock.EmplacementStock``) comme indisponible
sur une fenêtre [date_debut, date_fin] inclusive. Le plan de charge (FG299), la
détection de conflits (FG300) et le nivellement (FG301) peuvent EXCLURE une
ressource absente via le sélecteur ``ressource_indisponible``.

Couvre :
  * création d'une indisponibilité ciblant un technicien, puis une camionnette ;
  * la requête de chevauchement (``ressource_indisponible``) ;
  * la garde « exactement une / au moins une cible » (ni zéro, ni les deux) ;
  * la garde d'ordre des dates (fin ≥ début) ;
  * le scope société (ni lecture ni exclusion d'une autre société) ;
  * la barrière de rôle (écriture responsable/admin uniquement).

Run :
    python manage.py test apps.installations.tests_fg302_indispo -v2
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import IndisponibiliteRessource
from apps.installations.selectors import ressource_indisponible
from apps.stock.models import EmplacementStock

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg302-co-{n}', defaults={'nom': nom or f'FG302 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg302-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_camionnette(company, nom=None):
    return EmplacementStock.objects.create(
        company=company, nom=nom or f'Camion {next(_seq)}')


LUNDI = datetime.date(2026, 6, 1)
MERCREDI = datetime.date(2026, 6, 3)
VENDREDI = datetime.date(2026, 6, 5)
SEMAINE_FIN = datetime.date(2026, 6, 7)


# ── Création via l'API ────────────────────────────────────────────────────────

class TestIndispoCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.tech = make_user(self.company)
        self.camion = make_camionnette(self.company)

    def test_create_indispo_technicien(self):
        """FG302 — créer une indisponibilité ciblant un technicien."""
        r = self.api.post(f'{BASE}/indisponibilites-ressource/', {
            'technicien': self.tech.id,
            'type_indispo': 'conge',
            'date_debut': '2026-06-01', 'date_fin': '2026-06-05',
            'motif': 'Congés annuels',
        })
        self.assertEqual(r.status_code, 201, r.data)
        indispo = IndisponibiliteRessource.objects.get(id=r.data['id'])
        # Société + créateur posés côté serveur, jamais du corps.
        self.assertEqual(indispo.company_id, self.company.id)
        self.assertEqual(indispo.created_by_id, self.user.id)
        self.assertEqual(indispo.technicien_id, self.tech.id)
        self.assertIsNone(indispo.camionnette_id)

    def test_create_indispo_camionnette(self):
        """FG302 — créer une indisponibilité ciblant une camionnette."""
        r = self.api.post(f'{BASE}/indisponibilites-ressource/', {
            'camionnette': self.camion.id,
            'type_indispo': 'arret',
            'date_debut': '2026-06-03', 'date_fin': '2026-06-03',
        })
        self.assertEqual(r.status_code, 201, r.data)
        indispo = IndisponibiliteRessource.objects.get(id=r.data['id'])
        self.assertEqual(indispo.camionnette_id, self.camion.id)
        self.assertIsNone(indispo.technicien_id)

    def test_company_forced_server_side(self):
        """FG302 — la société du corps de requête est ignorée (forcée serveur)."""
        autre = make_company()
        r = self.api.post(f'{BASE}/indisponibilites-ressource/', {
            'company': autre.id,  # tentative d'injection
            'technicien': self.tech.id,
            'type_indispo': 'formation',
            'date_debut': '2026-06-01', 'date_fin': '2026-06-01',
        })
        self.assertEqual(r.status_code, 201, r.data)
        indispo = IndisponibiliteRessource.objects.get(id=r.data['id'])
        self.assertEqual(indispo.company_id, self.company.id)


# ── Gardes de validation ──────────────────────────────────────────────────────

class TestIndispoGuards(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.tech = make_user(self.company)
        self.camion = make_camionnette(self.company)

    def test_no_target_rejected(self):
        """FG302 — aucune cible (ni technicien ni camionnette) → 400."""
        r = self.api.post(f'{BASE}/indisponibilites-ressource/', {
            'type_indispo': 'conge',
            'date_debut': '2026-06-01', 'date_fin': '2026-06-05',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_both_targets_rejected(self):
        """FG302 — deux cibles à la fois (technicien ET camionnette) → 400."""
        r = self.api.post(f'{BASE}/indisponibilites-ressource/', {
            'technicien': self.tech.id,
            'camionnette': self.camion.id,
            'type_indispo': 'conge',
            'date_debut': '2026-06-01', 'date_fin': '2026-06-05',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_inverted_dates_rejected(self):
        """FG302 — date de fin antérieure à la date de début → 400."""
        r = self.api.post(f'{BASE}/indisponibilites-ressource/', {
            'technicien': self.tech.id,
            'type_indispo': 'conge',
            'date_debut': '2026-06-05', 'date_fin': '2026-06-01',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_model_clean_no_target(self):
        """FG302 — la garde modèle ``clean`` refuse l'absence de cible."""
        indispo = IndisponibiliteRessource(
            company=self.company, type_indispo='conge',
            date_debut=LUNDI, date_fin=VENDREDI)
        with self.assertRaises(DjangoValidationError):
            indispo.clean()

    def test_model_clean_both_targets(self):
        """FG302 — la garde modèle ``clean`` refuse deux cibles à la fois."""
        indispo = IndisponibiliteRessource(
            company=self.company, technicien=self.tech, camionnette=self.camion,
            type_indispo='conge', date_debut=LUNDI, date_fin=VENDREDI)
        with self.assertRaises(DjangoValidationError):
            indispo.clean()

    def test_model_clean_inverted_dates(self):
        """FG302 — la garde modèle ``clean`` refuse fin < début."""
        indispo = IndisponibiliteRessource(
            company=self.company, technicien=self.tech,
            type_indispo='conge', date_debut=VENDREDI, date_fin=LUNDI)
        with self.assertRaises(DjangoValidationError):
            indispo.clean()


# ── Sélecteur de chevauchement ────────────────────────────────────────────────

class TestRessourceIndisponibleSelector(TestCase):
    def setUp(self):
        self.company = make_company()
        self.tech = make_user(self.company)
        self.camion = make_camionnette(self.company)

    def _indispo(self, debut, fin, technicien=None, camionnette=None):
        return IndisponibiliteRessource.objects.create(
            company=self.company, technicien=technicien,
            camionnette=camionnette, type_indispo='conge',
            date_debut=debut, date_fin=fin)

    def test_overlap_detected_for_user_instance(self):
        """FG302 — un technicien en congé chevauchant la fenêtre est
        indisponible (instance utilisateur passée)."""
        self._indispo(LUNDI, VENDREDI, technicien=self.tech)
        self.assertTrue(
            ressource_indisponible(self.company, self.tech, MERCREDI, MERCREDI))

    def test_overlap_detected_for_user_id(self):
        """FG302 — un id entier est interprété comme un technicien (cas
        FG299/300/301)."""
        self._indispo(LUNDI, VENDREDI, technicien=self.tech)
        self.assertTrue(
            ressource_indisponible(self.company, self.tech.id, LUNDI, LUNDI))

    def test_overlap_detected_for_camionnette(self):
        """FG302 — une camionnette en arrêt chevauchant la fenêtre est
        indisponible (instance EmplacementStock passée)."""
        self._indispo(LUNDI, VENDREDI, camionnette=self.camion)
        self.assertTrue(
            ressource_indisponible(
                self.company, self.camion, MERCREDI, SEMAINE_FIN))

    def test_no_overlap_outside_window(self):
        """FG302 — un congé hors fenêtre ne rend pas la ressource
        indisponible."""
        self._indispo(LUNDI, MERCREDI, technicien=self.tech)
        # Fenêtre après la fin du congé.
        self.assertFalse(
            ressource_indisponible(
                self.company, self.tech, VENDREDI, SEMAINE_FIN))

    def test_inverted_window_returns_false(self):
        """FG302 — une fenêtre inversée ne contraint rien (False, jamais une
        exception)."""
        self._indispo(LUNDI, VENDREDI, technicien=self.tech)
        self.assertFalse(
            ressource_indisponible(self.company, self.tech, VENDREDI, LUNDI))

    def test_none_resource_returns_false(self):
        """FG302 — une ressource None ne contraint rien."""
        self.assertFalse(
            ressource_indisponible(self.company, None, LUNDI, VENDREDI))


# ── Scope société ─────────────────────────────────────────────────────────────

class TestIndispoTenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.tech = make_user(self.company)

    def test_list_company_isolation(self):
        """FG302 — la société B ne voit pas les indisponibilités de A."""
        IndisponibiliteRessource.objects.create(
            company=self.company, technicien=self.tech, type_indispo='conge',
            date_debut=LUNDI, date_fin=VENDREDI)
        company_b = make_company()
        user_b = make_user(company_b)
        r = auth(user_b).get(f'{BASE}/indisponibilites-ressource/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_selector_company_isolation(self):
        """FG302 — le sélecteur ne voit pas l'indisponibilité d'une autre
        société."""
        company_b = make_company()
        tech_b = make_user(company_b)
        IndisponibiliteRessource.objects.create(
            company=company_b, technicien=tech_b, type_indispo='conge',
            date_debut=LUNDI, date_fin=VENDREDI)
        # Société A interroge l'absence du technicien de B : invisible.
        self.assertFalse(
            ressource_indisponible(self.company, tech_b, LUNDI, VENDREDI))
        # Et B la voit bien.
        self.assertTrue(
            ressource_indisponible(company_b, tech_b, LUNDI, VENDREDI))

    def test_cross_company_target_rejected(self):
        """FG302 — viser un technicien d'une autre société est refusé (tenant)."""
        company_b = make_company()
        tech_b = make_user(company_b)
        r = self.api.post(f'{BASE}/indisponibilites-ressource/', {
            'technicien': tech_b.id,
            'type_indispo': 'conge',
            'date_debut': '2026-06-01', 'date_fin': '2026-06-05',
        })
        self.assertEqual(r.status_code, 400, r.data)


# ── Barrière de rôle ──────────────────────────────────────────────────────────

class TestIndispoRoleGate(TestCase):
    def setUp(self):
        self.company = make_company()
        self.tech = make_user(self.company)
        # Rôle hérité « normal » : ni responsable ni admin → lecture seule.
        self.lecteur = make_user(self.company, role='normal')

    def test_read_allowed_any_role(self):
        """FG302 — un rôle simple peut LIRE la liste."""
        r = auth(self.lecteur).get(f'{BASE}/indisponibilites-ressource/')
        self.assertEqual(r.status_code, 200, r.data)

    def test_write_forbidden_for_non_manager(self):
        """FG302 — un rôle simple ne peut PAS créer (écriture
        responsable/admin)."""
        r = auth(self.lecteur).post(f'{BASE}/indisponibilites-ressource/', {
            'technicien': self.tech.id,
            'type_indispo': 'conge',
            'date_debut': '2026-06-01', 'date_fin': '2026-06-05',
        })
        self.assertEqual(r.status_code, 403, r.data)
