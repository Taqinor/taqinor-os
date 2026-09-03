"""AUD186 — `recover_owner` ne promeut plus, et le registre des sociétés est
cloisonné.

Deux défauts, une même conséquence :

  (a) `recover_owner` recréait le compte PROPRIÉTAIRE d'une société CLIENTE
      avec `is_staff=True` — ce n'est pas un compte interne TAQINOR, et ce
      drapeau lui ouvrait /admin/ (où aucun `get_queryset` n'est cloisonné,
      cf. AUD185) ;
  (b) `CompanyViewSet` servait `Company.objects.all()` sous le seul garde
      `IsAdminUser` (donc `is_staff`), exposant en LECTURE ET EN ÉCRITURE les
      métadonnées de TOUTES les sociétés à tout compte `is_staff`.

Scénario : après une récupération de compte pour la société A, ce propriétaire
— désormais `is_staff` — atteignait l'API des sociétés B, C, D.

Tests ROUGES avant le correctif : (1) le compte recréé portait `is_staff=True` ;
(2) l'admin de A listait et modifiait la société B. Le parcours de récupération
documenté (docs/production.md) reste vérifié de bout en bout : le compte
rétabli garde tous ses droits ERP.

Run :
    python manage.py test \
        authentication.tests.test_aud186_recover_owner_scope_societes -v 2
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RecoverOwnerNePromeutPlusTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Société A AUD186', slug='aud186-societe-a')

    def test_le_proprietaire_recree_nest_pas_is_staff(self):
        call_command(
            'recover_owner', '--username', 'aud186_owner',
            '--company', self.company.slug,
            '--password', 'RecoveredAUD186!2026', stdout=StringIO())

        owner = User.objects.get(username='aud186_owner')
        self.assertFalse(owner.is_staff)

    def test_le_proprietaire_recree_garde_tous_ses_droits_erp(self):
        call_command(
            'recover_owner', '--username', 'aud186_owner',
            '--company', self.company.slug,
            '--password', 'RecoveredAUD186!2026', stdout=StringIO())

        owner = User.objects.get(username='aud186_owner')
        self.assertTrue(owner.is_active)
        self.assertTrue(owner.is_protected)
        self.assertEqual(owner.role_legacy, User.ROLE_ADMIN)
        self.assertEqual(owner.company_id, self.company.id)
        self.assertTrue(owner.check_password('RecoveredAUD186!2026'))
        # Le rôle admin métier — c'est LUI qui porte les droits, jamais
        # `is_staff` : le rôle de la société portant `roles_gerer` est attaché.
        admin_role = Role.objects.filter(
            company=self.company,
            permissions__contains=['roles_gerer']).first()
        if admin_role is not None:
            self.assertEqual(owner.role_id, admin_role.id)

    def test_le_parcours_de_recuperation_reste_fonctionnel_de_bout_en_bout(self):
        """Le compte rétabli se connecte et atteint les écrans d'admin ERP."""
        call_command(
            'recover_owner', '--username', 'aud186_owner',
            '--company', self.company.slug,
            '--password', 'RecoveredAUD186!2026', stdout=StringIO())
        owner = User.objects.get(username='aud186_owner')
        api = auth(owner)

        moi = api.get('/api/django/auth/me/')
        utilisateurs = api.get('/api/django/users/')

        self.assertEqual(moi.status_code, 200, moi.data)
        self.assertEqual(moi.data['username'], 'aud186_owner')
        self.assertEqual(utilisateurs.status_code, 200, utilisateurs.data)

    def test_un_compte_existant_nest_pas_promu(self):
        User.objects.create_user(
            username='aud186_owner', password='old', role_legacy='normal',
            company=self.company, is_active=False)

        call_command(
            'recover_owner', '--username', 'aud186_owner',
            '--password', 'RecoveredAUD186!2026', stdout=StringIO())

        owner = User.objects.get(username='aud186_owner')
        self.assertFalse(owner.is_staff)
        self.assertTrue(owner.is_active)
        self.assertEqual(owner.role_legacy, User.ROLE_ADMIN)


class RegistreDesSocietesCloisonneTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(
            nom='Société A AUD186', slug='aud186-co-a')
        self.co_b = Company.objects.create(
            nom='Société B AUD186', slug='aud186-co-b')
        # Un ADMIN MÉTIER promu `is_staff` — exactement ce que produisait
        # `recover_owner` avant AUD186.
        self.admin_a = User.objects.create_user(
            username='aud186-admin-a', password='x', company=self.co_a,
            role_legacy='admin', is_staff=True)
        self.operateur = User.objects.create_superuser(
            username='aud186-operateur', password='x')
        self.operateur.company = self.co_a
        self.operateur.save()

    def test_la_liste_ne_montre_que_sa_propre_societe(self):
        r = auth(self.admin_a).get('/api/django/companies/')

        self.assertEqual(r.status_code, 200, r.data)
        resultats = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual([c['id'] for c in resultats], [self.co_a.id])

    def test_le_detail_dune_autre_societe_est_refuse(self):
        r = auth(self.admin_a).get(f'/api/django/companies/{self.co_b.id}/')

        self.assertEqual(r.status_code, 403)

    def test_lecriture_sur_une_autre_societe_est_refusee(self):
        r = auth(self.admin_a).patch(
            f'/api/django/companies/{self.co_b.id}/',
            {'nom': 'Détournée'}, format='json')

        self.assertEqual(r.status_code, 403)
        self.co_b.refresh_from_db()
        self.assertEqual(self.co_b.nom, 'Société B AUD186')

    def test_sa_propre_societe_reste_lisible_et_modifiable(self):
        """Non-régression NTDMO27/NTDMO33 : l'admin métier garde SA société."""
        api = auth(self.admin_a)

        detail = api.get(f'/api/django/companies/{self.co_a.id}/')
        patch = api.patch(f'/api/django/companies/{self.co_a.id}/',
                          {'tours_actifs': False}, format='json')

        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(patch.status_code, 200, patch.data)
        self.co_a.refresh_from_db()
        self.assertFalse(self.co_a.tours_actifs)

    def test_creer_ou_supprimer_une_societe_est_reserve_a_loperateur(self):
        api = auth(self.admin_a)

        creation = api.post('/api/django/companies/',
                            {'nom': 'Nouvelle', 'slug': 'aud186-nouvelle'},
                            format='json')
        suppression = api.delete(f'/api/django/companies/{self.co_a.id}/')

        self.assertEqual(creation.status_code, 403)
        self.assertEqual(suppression.status_code, 403)
        self.assertFalse(
            Company.objects.filter(slug='aud186-nouvelle').exists())
        self.assertTrue(Company.objects.filter(pk=self.co_a.pk).exists())

    def test_loperateur_plateforme_garde_le_registre_entier(self):
        api = auth(self.operateur)

        liste = api.get('/api/django/companies/')
        detail = api.get(f'/api/django/companies/{self.co_b.id}/')

        self.assertEqual(liste.status_code, 200, liste.data)
        resultats = (liste.data['results'] if isinstance(liste.data, dict)
                     else liste.data)
        ids = {c['id'] for c in resultats}
        self.assertIn(self.co_a.id, ids)
        self.assertIn(self.co_b.id, ids)
        self.assertEqual(detail.status_code, 200, detail.data)
