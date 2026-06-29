"""
FG292 — Tâches & sous-tâches de projet avec dépendances (``ProjetTache``).

Couvre :
  * la création d'une tâche et d'une sous-tâche (société posée côté serveur,
    parent/hiérarchie, statut PROPRE à la tâche jamais l'entonnoir commercial) ;
  * la dépendance d'ordonnancement (`predecesseur`) ;
  * le refus des CYCLES (auto-prédécesseur, auto-parent, boucle plus longue) ;
  * le refus d'un lien parent/prédécesseur d'un AUTRE programme ;
  * le scope société (isolation + refus d'un assigné cross-company).

Run :
    python manage.py test apps.installations.tests_program_tache -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Projet, ProjetTache

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    slug = slug or f'tache-co-{n}'
    nom = nom or f'Tache Co {n}'
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'tache-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Ferme', prenom='Client',
        email=f'tache-{company.id}-{n}@example.invalid')


def make_projet(company, reference=None):
    n = next(_seq)
    return Projet.objects.create(
        company=company, reference=reference or f'PRG-T-{n}',
        nom='Ferme 4 forages', client=make_client(company))


# ── Création de tâche / sous-tâche ───────────────────────────────────────────

class TestFG292TacheCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.projet = make_projet(self.company)

    def test_create_sets_company_server_side(self):
        """FG292 — la tâche porte la société du user (jamais lue du corps), le
        statut PROPRE par défaut (à faire), pas l'entonnoir commercial."""
        other = make_company()
        r = self.api.post(f'{BASE}/programme-taches/', {
            'projet': self.projet.id,
            'libelle': 'Étude de site',
            'ordre': 1,
            'company': other.id,  # ignoré côté serveur
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        tache = ProjetTache.objects.get(id=r.data['id'])
        self.assertEqual(tache.company_id, self.company.id)
        self.assertEqual(tache.projet_id, self.projet.id)
        self.assertEqual(tache.statut, ProjetTache.Statut.A_FAIRE)

    def test_create_with_assigne_and_echeance(self):
        """FG292 — assigné + échéance posés ; assigné renvoyé en lecture."""
        r = self.api.post(f'{BASE}/programme-taches/', {
            'projet': self.projet.id,
            'libelle': 'Pose panneaux',
            'assigne': self.user.id,
            'date_echeance': '2026-07-15',
            'statut': 'en_cours',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['assigne'], self.user.id)
        self.assertEqual(r.data['assigne_nom'], self.user.username)
        self.assertEqual(r.data['date_echeance'], '2026-07-15')
        self.assertEqual(r.data['statut'], 'en_cours')

    def test_create_sous_tache(self):
        """FG292 — une sous-tâche pointe vers une tâche parente (hiérarchie)."""
        parent = ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='Pose')
        r = self.api.post(f'{BASE}/programme-taches/', {
            'projet': self.projet.id,
            'parent': parent.id,
            'libelle': 'Pose onduleur',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        sous = ProjetTache.objects.get(id=r.data['id'])
        self.assertEqual(sous.parent_id, parent.id)
        # Le parent compte une sous-tâche.
        parent.refresh_from_db()
        self.assertEqual(parent.sous_taches.count(), 1)

    def test_create_with_predecesseur_dependency(self):
        """FG292 — une tâche déclare un prédécesseur (dépendance d'ordre)."""
        amont = ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='Étude')
        r = self.api.post(f'{BASE}/programme-taches/', {
            'projet': self.projet.id,
            'predecesseur': amont.id,
            'libelle': 'Approvisionnement',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        aval = ProjetTache.objects.get(id=r.data['id'])
        self.assertEqual(aval.predecesseur_id, amont.id)
        self.assertEqual(r.data['predecesseur_libelle'], 'Étude')


# ── Cycles refusés ───────────────────────────────────────────────────────────

class TestFG292CycleGuard(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.projet = make_projet(self.company)

    def test_self_predecesseur_rejected(self):
        """FG292 — une tâche ne peut pas être son propre prédécesseur."""
        t = ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='T')
        r = self.api.patch(f'{BASE}/programme-taches/{t.id}/',
                           {'predecesseur': t.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        t.refresh_from_db()
        self.assertIsNone(t.predecesseur_id)

    def test_self_parent_rejected(self):
        """FG292 — une tâche ne peut pas être sa propre sous-tâche."""
        t = ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='T')
        r = self.api.patch(f'{BASE}/programme-taches/{t.id}/',
                           {'parent': t.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        t.refresh_from_db()
        self.assertIsNone(t.parent_id)

    def test_predecesseur_cycle_rejected(self):
        """FG292 — fermer une boucle A→B→A sur le prédécesseur est refusé et
        rien n'est persisté (rollback)."""
        a = ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='A')
        b = ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='B',
            predecesseur=a)
        # a.predecesseur = b fermerait la boucle a→b→a.
        r = self.api.patch(f'{BASE}/programme-taches/{a.id}/',
                           {'predecesseur': b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        a.refresh_from_db()
        self.assertIsNone(a.predecesseur_id)

    def test_parent_cycle_rejected(self):
        """FG292 — fermer une boucle parent A→B→A est refusée (rollback)."""
        a = ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='A')
        b = ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='B', parent=a)
        r = self.api.patch(f'{BASE}/programme-taches/{a.id}/',
                           {'parent': b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        a.refresh_from_db()
        self.assertIsNone(a.parent_id)

    def test_cross_projet_link_rejected(self):
        """FG292 — parent/prédécesseur doivent appartenir au MÊME programme."""
        autre_projet = make_projet(self.company)
        amont = ProjetTache.objects.create(
            company=self.company, projet=autre_projet, libelle='Hors-prog')
        r = self.api.post(f'{BASE}/programme-taches/', {
            'projet': self.projet.id,
            'predecesseur': amont.id,
            'libelle': 'Aval',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)


# ── Scope société ────────────────────────────────────────────────────────────

class TestFG292Tenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.projet = make_projet(self.company)

    def test_company_isolation(self):
        """FG292 — la société B ne voit pas les tâches de A."""
        ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='Secret A')
        company_b = make_company()
        user_b = make_user(company_b)
        r = auth(user_b).get(f'{BASE}/programme-taches/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_filter_by_projet_and_statut(self):
        """FG292 — la liste se filtre par programme et par statut PROPRE."""
        ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='En cours',
            statut=ProjetTache.Statut.EN_COURS)
        ProjetTache.objects.create(
            company=self.company, projet=self.projet, libelle='À faire',
            statut=ProjetTache.Statut.A_FAIRE)
        r = self.api.get(f'{BASE}/programme-taches/',
                         {'projet': self.projet.id, 'statut': 'en_cours'})
        self.assertEqual(r.status_code, 200)
        libelles = [t['libelle'] for t in r.data['results']]
        self.assertIn('En cours', libelles)
        self.assertNotIn('À faire', libelles)

    def test_cross_company_assigne_rejected(self):
        """FG292 — impossible d'assigner un user d'une autre société."""
        other = make_company()
        user_b = make_user(other)
        r = self.api.post(f'{BASE}/programme-taches/', {
            'projet': self.projet.id,
            'libelle': 'Intrus',
            'assigne': user_b.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_cross_company_projet_rejected(self):
        """FG292 — impossible de créer une tâche sur le programme d'une autre
        société."""
        other = make_company()
        projet_b = make_projet(other)
        r = self.api.post(f'{BASE}/programme-taches/', {
            'projet': projet_b.id,
            'libelle': 'Intrus',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
