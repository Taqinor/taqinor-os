"""XKB5 — Annonces internes ciblées et programmées.

Couverture :
  - publication programmée : le sweep publie une annonce dont
    `date_publication` est atteinte, jamais avant, jamais deux fois.
  - ciblage : TOUS / ROLE / DEPARTEMENT ne notifient QUE les destinataires
    voulus.
  - dashboard : `?active=1` ne renvoie que les annonces publiées non
    expirées ; `epinglee` reste visible jusqu'à expiration.
  - multi-tenant : une annonce d'une société n'est jamais visible/notifiée
    pour une autre.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from .models import Annonce, EventType, Notification

User = get_user_model()


def _make_company(name='AnnonceCo'):
    return Company.objects.create(nom=name)


def _make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


class AnnonceSweepTests(TestCase):
    """Publication programmée via `sweep_daily` / `_sweep_annonces_due`."""

    def setUp(self):
        self.company = _make_company()
        self.user1 = _make_user(self.company, 'u1')
        self.user2 = _make_user(self.company, 'u2')

    def test_annonce_not_due_before_date_publication(self):
        from .sweeps import _sweep_annonces_due
        future = timezone.now() + timedelta(days=1)
        Annonce.objects.create(
            company=self.company, titre='Future', date_publication=future)
        count = _sweep_annonces_due(self.company)
        self.assertEqual(count, 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_annonce_due_is_published_and_notifies_targets(self):
        from .sweeps import _sweep_annonces_due
        past = timezone.now() - timedelta(minutes=5)
        annonce = Annonce.objects.create(
            company=self.company, titre='Annonce due',
            corps='Contenu', date_publication=past)
        count = _sweep_annonces_due(self.company)
        self.assertEqual(count, 1)
        annonce.refresh_from_db()
        self.assertTrue(annonce.publiee)
        self.assertIsNotNone(annonce.date_publication_effective)
        notifs = Notification.objects.filter(
            event_type=EventType.ANNONCE_PUBLISHED)
        self.assertEqual(notifs.count(), 2)  # user1 + user2 (cible=TOUS)

    def test_sweep_idempotent_does_not_reemit_on_rerun(self):
        from .sweeps import _sweep_annonces_due
        past = timezone.now() - timedelta(minutes=5)
        Annonce.objects.create(
            company=self.company, titre='Annonce due', date_publication=past)
        _sweep_annonces_due(self.company)
        first_count = Notification.objects.count()
        second_run = _sweep_annonces_due(self.company)
        self.assertEqual(second_run, 0)
        self.assertEqual(Notification.objects.count(), first_count)

    def test_annonce_without_date_publication_never_auto_published(self):
        """Pas de date = pas de publication automatique (comportement
        additif préservé — création manuelle non-programmée)."""
        from .sweeps import _sweep_annonces_due
        Annonce.objects.create(company=self.company, titre='Sans date')
        count = _sweep_annonces_due(self.company)
        self.assertEqual(count, 0)


class AnnonceTargetingTests(TestCase):
    """Ciblage TOUS / ROLE / DEPARTEMENT — seuls les destinataires voulus
    reçoivent la notification."""

    def setUp(self):
        self.company = _make_company('TargetCo')

    def test_cible_tous_notifies_all_active_users(self):
        from .services import publish_annonce
        u1 = _make_user(self.company, 't1')
        u2 = _make_user(self.company, 't2')
        annonce = Annonce.objects.create(
            company=self.company, titre='Pour tous',
            cible_type=Annonce.Cible.TOUS)
        publish_annonce(annonce)
        self.assertEqual(
            Notification.objects.filter(recipient__in=[u1, u2]).count(), 2)

    def test_cible_role_notifies_only_matching_role(self):
        from .services import publish_annonce
        admin = _make_user(self.company, 'admin_t', role_legacy='admin')
        normal = _make_user(self.company, 'normal_t', role_legacy='normal')
        annonce = Annonce.objects.create(
            company=self.company, titre='Pour admins',
            cible_type=Annonce.Cible.ROLE, cible_role='admin')
        publish_annonce(annonce)
        self.assertEqual(
            Notification.objects.filter(recipient=admin).count(), 1)
        self.assertEqual(
            Notification.objects.filter(recipient=normal).count(), 0)

    def test_cible_role_without_role_set_notifies_no_one(self):
        from .services import publish_annonce
        _make_user(self.company, 'norole_t')
        annonce = Annonce.objects.create(
            company=self.company, titre='Rôle non défini',
            cible_type=Annonce.Cible.ROLE, cible_role='')
        publish_annonce(annonce)
        self.assertEqual(Notification.objects.count(), 0)

    def test_cible_departement_notifies_only_department_members(self):
        from apps.rh.models import Departement, DossierEmploye
        from .services import publish_annonce

        dept_atelier = Departement.objects.create(
            company=self.company, nom='Atelier')
        dept_commercial = Departement.objects.create(
            company=self.company, nom='Commercial')
        atelier_user = _make_user(self.company, 'atelier_u')
        commercial_user = _make_user(self.company, 'commercial_u')
        DossierEmploye.objects.create(
            company=self.company, user=atelier_user, matricule='M1',
            nom='Atelier', prenom='User', departement=dept_atelier)
        DossierEmploye.objects.create(
            company=self.company, user=commercial_user, matricule='M2',
            nom='Commercial', prenom='User', departement=dept_commercial)

        annonce = Annonce.objects.create(
            company=self.company, titre='Pour atelier',
            cible_type=Annonce.Cible.DEPARTEMENT,
            cible_departement_nom='Atelier')
        publish_annonce(annonce)
        self.assertEqual(
            Notification.objects.filter(recipient=atelier_user).count(), 1)
        self.assertEqual(
            Notification.objects.filter(recipient=commercial_user).count(), 0)

    def test_publish_is_noop_when_already_published(self):
        from .services import publish_annonce
        u1 = _make_user(self.company, 'idem_u')
        annonce = Annonce.objects.create(
            company=self.company, titre='Déjà publiée', publiee=True)
        publish_annonce(annonce)
        self.assertEqual(
            Notification.objects.filter(recipient=u1).count(), 0)


class AnnonceApiTests(TestCase):
    """Dashboard `?active=1`, épinglage, scoping multi-tenant."""

    def setUp(self):
        self.company = _make_company('ApiAnnonceCo')
        self.other_company = _make_company('OtherAnnonceCo')
        self.admin = _make_user(self.company, 'api_admin', role_legacy='admin')

    def test_active_filter_excludes_unpublished_and_expired(self):
        from rest_framework.test import APIClient
        past = timezone.now() - timedelta(days=1)
        future = timezone.now() + timedelta(days=1)

        Annonce.objects.create(
            company=self.company, titre='Non publiée', publiee=False)
        Annonce.objects.create(
            company=self.company, titre='Expirée', publiee=True,
            date_expiration=past)
        active = Annonce.objects.create(
            company=self.company, titre='Active', publiee=True,
            date_expiration=future)

        client = APIClient()
        client.force_authenticate(self.admin)
        resp = client.get('/api/django/notifications/annonces/?active=1')
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if 'results' in resp.data else resp.data
        ids = [r['id'] for r in results]
        self.assertEqual(ids, [active.pk])

    def test_annonces_scoped_per_company(self):
        Annonce.objects.create(company=self.company, titre='Mine')
        Annonce.objects.create(company=self.other_company, titre='Not mine')
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(self.admin)
        resp = client.get('/api/django/notifications/annonces/')
        results = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['titre'], 'Mine')

    def test_publier_action_publishes_immediately(self):
        from rest_framework.test import APIClient
        annonce = Annonce.objects.create(
            company=self.company, titre='À publier maintenant')
        client = APIClient()
        client.force_authenticate(self.admin)
        resp = client.post(
            f'/api/django/notifications/annonces/{annonce.pk}/publier/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['publiee'])

    def test_normal_user_cannot_create_annonce(self):
        from rest_framework.test import APIClient
        normal = _make_user(self.company, 'api_normal')
        client = APIClient()
        client.force_authenticate(normal)
        resp = client.post(
            '/api/django/notifications/annonces/',
            {'titre': 'Interdit'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_create_forces_company_and_auteur_server_side(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(self.admin)
        resp = client.post(
            '/api/django/notifications/annonces/',
            {'titre': 'Créée via API', 'company': self.other_company.pk},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        annonce = Annonce.objects.get(pk=resp.data['id'])
        self.assertEqual(annonce.company_id, self.company.pk)
        self.assertEqual(annonce.auteur_id, self.admin.pk)
