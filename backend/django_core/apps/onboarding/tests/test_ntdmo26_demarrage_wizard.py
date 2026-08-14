"""NTDMO26 — assistant first-run « Configurez votre société en 5 minutes »
(société RÉELLE, jamais démo). Deux surfaces :

* le catalogue gagne 2 items (``assistant_demarrage``, ``premier_produit``,
  seedés par migration, idempotents comme le reste du catalogue) ;
* ``resume_pour_utilisateur`` calcule ``assistant_demarrage_auto`` (vrai
  seulement société réelle < 30 j avec l'item encore à faire) — consommé par
  ``PremiersPasWidget.jsx`` pour naviguer automatiquement vers
  ``/onboarding/demarrage``.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.onboarding.models import OnboardingChecklistItem
from apps.onboarding.selectors import resume_pour_utilisateur
from apps.onboarding.services import marquer_item_complete, seed_default_items
from apps.roles.models import Role

User = get_user_model()


class Ntdmo26CatalogueTest(TestCase):
    def test_catalogue_gains_two_items(self):
        self.assertTrue(OnboardingChecklistItem.objects.filter(
            key='assistant_demarrage', company__isnull=True).exists())
        self.assertTrue(OnboardingChecklistItem.objects.filter(
            key='premier_produit', company__isnull=True).exists())

    def test_seed_is_idempotent(self):
        n = OnboardingChecklistItem.objects.count()
        seed_default_items()
        seed_default_items()
        self.assertEqual(OnboardingChecklistItem.objects.count(), n)

    def test_existing_six_items_untouched(self):
        # Additive-only : les 6 clés du round précédent restent présentes.
        for key in ('configurer_societe', 'import_clients', 'premier_devis',
                    'premier_paiement', 'inviter_coequipier', 'premier_chantier'):
            self.assertTrue(
                OnboardingChecklistItem.objects.filter(key=key).exists(), key)


class Ntdmo26AutoTriggerTest(TestCase):
    def _admin(self, company):
        role = Role.objects.create(company=company, nom='Administrateur')
        return User.objects.create_user(
            f'admin-{company.pk}', password='x', company=company, role=role)

    def test_true_for_fresh_real_company_with_item_todo(self):
        company = Company.objects.create(nom='Frais', slug='co-frais-26')
        user = self._admin(company)
        resume = resume_pour_utilisateur(company, user)
        self.assertTrue(resume['assistant_demarrage_auto'])

    def test_false_for_demo_company(self):
        company = Company.objects.create(
            nom='Demo', slug='co-demo-26', est_demo=True)
        user = self._admin(company)
        resume = resume_pour_utilisateur(company, user)
        self.assertFalse(resume['assistant_demarrage_auto'])

    def test_false_for_old_company(self):
        company = Company.objects.create(nom='Vieille', slug='co-vieille-26')
        # `date_creation` est `auto_now_add` — on la recule directement en base.
        Company.objects.filter(pk=company.pk).update(
            date_creation=timezone.now() - timedelta(days=90))
        company.refresh_from_db()
        user = self._admin(company)
        resume = resume_pour_utilisateur(company, user)
        self.assertFalse(resume['assistant_demarrage_auto'])

    def test_false_once_item_marked_done(self):
        company = Company.objects.create(nom='Fait', slug='co-fait-26')
        user = self._admin(company)
        marquer_item_complete(company, user, 'assistant_demarrage')
        resume = resume_pour_utilisateur(company, user)
        self.assertFalse(resume['assistant_demarrage_auto'])

    def test_false_once_wizard_skipped(self):
        from apps.onboarding.services import ignorer_item
        company = Company.objects.create(nom='Passe', slug='co-passe-26')
        user = self._admin(company)
        item = OnboardingChecklistItem.objects.get(key='assistant_demarrage')
        ignorer_item(company, user, item.id)
        resume = resume_pour_utilisateur(company, user)
        self.assertFalse(resume['assistant_demarrage_auto'])
        # « Passer » ne réapparaît plus JAMAIS automatiquement : l'item quitte
        # la liste ``items`` (comportement générique NTDMO13 déjà couvert par
        # test_progress_endpoint.py, revérifié ici pour ce cas précis).
        keys = {it['key'] for it in resume['items']}
        self.assertNotIn('assistant_demarrage', keys)


class Ntdmo26EndpointReuseTest(TestCase):
    """Le wizard NE POSE AUCUN nouvel endpoint : « Passer » et chaque étape
    complétée réutilisent ignorer/marquer-fait (WIR59/NTDMO13), déjà exposés."""

    def setUp(self):
        self.company = Company.objects.create(nom='Ep', slug='co-ep-26')
        self.role = Role.objects.create(company=self.company, nom='Administrateur')
        self.user = User.objects.create_user(
            'u-ep', password='x', company=self.company, role=self.role)

    def _client(self):
        c = APIClient()
        c.force_authenticate(self.user)
        return c

    def test_passer_ignores_item_via_existing_endpoint(self):
        item = OnboardingChecklistItem.objects.get(key='assistant_demarrage')
        c = self._client()
        r = c.post(f'/api/django/onboarding/progress/{item.id}/ignorer/')
        self.assertEqual(r.status_code, 200)
        keys = {it['key'] for it in r.data['items']}
        self.assertNotIn('assistant_demarrage', keys)
        self.assertFalse(r.data['assistant_demarrage_auto'])

    def test_completing_produit_step_shows_in_progress(self):
        item = OnboardingChecklistItem.objects.get(key='premier_produit')
        c = self._client()
        r = c.post(f'/api/django/onboarding/progress/{item.id}/marquer-fait/')
        self.assertEqual(r.status_code, 200)
        done = [it for it in r.data['items'] if it['key'] == 'premier_produit']
        self.assertTrue(done and done[0]['fait'])
