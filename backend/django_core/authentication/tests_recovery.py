"""
Tests propriétaire protégé + dernier-propriétaire + commande de récupération
(WS3, 2026-06-13).

Garantit qu'on ne peut jamais se verrouiller dehors : le serveur refuse de
supprimer/rétrograder le dernier propriétaire ou un compte protégé, et la
commande recover_owner (lancée via SSH) rétablit l'accès — sans aucun secret
en dur.

Run :
    docker compose exec django_core python manage.py test \
        authentication.tests_recovery -v 2
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def make_company(slug='rec-co', nom='Rec Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestLastOwnerGuards(TestCase):
    def setUp(self):
        self.company = make_company()
        self.owner = User.objects.create_user(
            username='rec_owner', password='x', role_legacy='admin',
            company=self.company, is_protected=True,
        )
        # Un second admin permet de tester la suppression d'un admin
        # non-dernier.
        self.admin2 = User.objects.create_user(
            username='rec_admin2', password='x', role_legacy='admin',
            company=self.company,
        )

    def test_cannot_delete_protected_owner(self):
        api = auth(self.admin2)
        r = api.delete(f'/api/django/users/{self.owner.id}/')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.owner.id).exists())

    def test_cannot_deactivate_protected_owner(self):
        api = auth(self.admin2)
        r = api.patch(
            f'/api/django/users/{self.owner.id}/',
            {'is_active': False}, format='json',
        )
        self.assertEqual(r.status_code, 403)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_cannot_delete_last_owner(self):
        # Supprime d'abord le 2e admin (autorisé, ce n'est pas le dernier).
        api = auth(self.owner)
        r = api.delete(f'/api/django/users/{self.admin2.id}/')
        self.assertEqual(r.status_code, 204, getattr(r, 'data', None))
        # Désormais owner est le dernier admin → un superuser ne peut pas non
        # plus le supprimer (et il est protégé de toute façon).
        su = User.objects.create_superuser(
            username='rec_su', password='x',
        )
        su.company = self.company
        su.save()
        r = auth(su).delete(f'/api/django/users/{self.owner.id}/')
        self.assertEqual(r.status_code, 403)

    def test_cannot_demote_last_owner_non_protected(self):
        # admin2 n'est pas protégé ; on supprime owner d'abord ? non — owner
        # est protégé. On teste la garde « dernier propriétaire » sur admin2
        # en retirant d'abord le rôle admin d'owner est impossible (protégé).
        # On crée donc une société séparée à un seul admin non protégé.
        solo_co = make_company(slug='solo-co', nom='Solo Co')
        solo = User.objects.create_user(
            username='solo_admin', password='x', role_legacy='admin',
            company=solo_co,
        )
        api = auth(solo)
        r = api.patch(
            f'/api/django/users/{solo.id}/',
            {'is_active': False}, format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_compte_avec_traces_refuse_409_desactivez_le(self):
        """ASUP5 (D-ASUP-2) — un compte qui a laissé des traces ne se supprime
        plus (409 nommé, « désactivez-le »), un compte vierge si (204)."""
        from datetime import date
        from decimal import Decimal

        from django.apps import apps as django_apps
        call_command('init_roles', verbosity=0)
        Role = django_apps.get_model('roles', 'Role')
        Client = django_apps.get_model('crm', 'Client')
        Lead = django_apps.get_model('crm', 'Lead')
        Facture = django_apps.get_model('facturation', 'Facture')
        Paiement = django_apps.get_model('facturation', 'Paiement')

        def compte(username, nom_role):
            return User.objects.create_user(
                username=username, password='x', company=self.company,
                role=Role.objects.get(company=self.company, nom=nom_role))

        directeur = compte('asup5_directeur', 'Directeur')
        technicien = compte('asup5_technicien', 'Technicien')
        vierge = compte('asup5_vierge', 'Commercial')
        client = Client.objects.create(company=self.company, nom='ASUP5', email='asup5@client.test')
        facture = Facture.objects.create(
            company=self.company, reference='FAC-ASUP5-1', client=client, statut=Facture.Statut.EMISE)
        paiement = Paiement.objects.create(
            company=self.company, facture=facture, client=client, montant=Decimal('10'),
            date_paiement=date.today(), mode=Paiement.Mode.VIREMENT, created_by=technicien)
        lead = Lead.objects.create(company=self.company, nom='Lead ASUP5', owner=technicien)

        r = auth(directeur).delete(f'/api/django/users/{technicien.id}/')
        self.assertEqual(r.status_code, 409, getattr(r, 'data', None))
        self.assertIn('auteur de 1 paiement', r.data['detail'])
        self.assertIn('propriétaire de 1 lead', r.data['detail'])
        self.assertIn('désactivez-le', r.data['detail'])
        self.assertTrue(User.objects.filter(pk=technicien.pk, is_active=True).exists())
        paiement.refresh_from_db()
        self.assertEqual(paiement.created_by_id, technicien.pk)
        self.assertEqual(Lead.all_objects.get(pk=lead.pk).owner_id, technicien.pk)

        r = auth(directeur).delete(f'/api/django/users/{vierge.id}/')
        self.assertEqual(r.status_code, 204, getattr(r, 'data', None))
        self.assertFalse(User.objects.filter(pk=vierge.pk).exists())


class TestRecoverOwnerCommand(TestCase):
    def test_resets_existing_owner_password_and_protects(self):
        company = make_company()
        owner = User.objects.create_user(
            username='demo_admin', password='old', role_legacy='normal',
            company=company, is_active=False,
        )
        out = StringIO()
        call_command(
            'recover_owner', '--username', 'demo_admin',
            '--password', 'NewStrongPass!2026', stdout=out,
        )
        owner.refresh_from_db()
        self.assertTrue(owner.is_active)
        self.assertTrue(owner.is_protected)
        self.assertEqual(owner.role_legacy, User.ROLE_ADMIN)
        self.assertTrue(owner.check_password('NewStrongPass!2026'))

    def test_recreates_missing_owner_in_single_company(self):
        company = make_company()
        self.assertFalse(User.objects.filter(username='demo_admin').exists())
        out = StringIO()
        call_command(
            'recover_owner', '--username', 'demo_admin',
            '--password', 'Recreated!2026', stdout=out,
        )
        owner = User.objects.get(username='demo_admin')
        self.assertTrue(owner.is_protected)
        self.assertEqual(owner.company_id, company.id)
        self.assertTrue(owner.check_password('Recreated!2026'))

    def test_generates_password_when_none_given(self):
        make_company()
        User.objects.create_user(
            username='demo_admin', password='old', role_legacy='admin',
            company=Company.objects.first(),
        )
        out = StringIO()
        call_command('recover_owner', stdout=out)
        # Le mot de passe généré est affiché (jamais en dur dans le code).
        self.assertIn('Mot de passe généré', out.getvalue())
