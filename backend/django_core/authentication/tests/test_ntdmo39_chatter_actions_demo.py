"""NTDMO39 — entrées `records.Activity` automatiques sur les actions démo
(reset NTDMO7, bascule mode présentation NTDMO10). Réutilise le chatter
générique existant (jamais un journal parallèle)."""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from apps.records.models import Activity
from authentication.models import Company, CustomUser

User = CustomUser


class ModePresentationChatterTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Démo Chatter', slug='co-chatter-39', est_demo=True)
        self.admin = User.objects.create_user(
            'admin-39', password='x', company=self.company, is_staff=True)
        self.ct = ContentType.objects.get_for_model(Company)

    def _client(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        return c

    def test_toggling_on_creates_a_note_activity(self):
        r = self._client().patch(
            f'/api/django/companies/{self.company.id}/',
            {'mode_presentation_actif': True})
        self.assertEqual(r.status_code, 200)
        entries = Activity.objects.filter(
            content_type=self.ct, object_id=self.company.id,
            kind=Activity.Kind.NOTE)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertIn('activé', entry.body)
        self.assertIn('admin-39', entry.body)
        self.assertEqual(entry.created_by, self.admin)
        self.assertEqual(entry.company_id, self.company.id)

    def test_toggling_off_after_on_creates_a_second_note(self):
        self._client().patch(
            f'/api/django/companies/{self.company.id}/',
            {'mode_presentation_actif': True})
        self._client().patch(
            f'/api/django/companies/{self.company.id}/',
            {'mode_presentation_actif': False})
        entries = Activity.objects.filter(
            content_type=self.ct, object_id=self.company.id,
            kind=Activity.Kind.NOTE)
        self.assertEqual(entries.count(), 2)
        self.assertIn('désactivé', entries.latest('id').body)

    def test_no_real_change_creates_no_entry(self):
        # La société démarre à False : PATCH avec False = pas de changement
        # réel, aucune entrée de chatter parasite.
        self._client().patch(
            f'/api/django/companies/{self.company.id}/',
            {'mode_presentation_actif': False})
        self.assertFalse(
            Activity.objects.filter(
                content_type=self.ct, object_id=self.company.id,
                kind=Activity.Kind.NOTE).exists())

    def test_patching_unrelated_field_creates_no_entry(self):
        self._client().patch(
            f'/api/django/companies/{self.company.id}/',
            {'nom': 'Nouveau nom'})
        self.assertFalse(
            Activity.objects.filter(
                content_type=self.ct, object_id=self.company.id,
                kind=Activity.Kind.NOTE).exists())


class ResetDemoChatterTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Démo Reset Chatter', slug='demo-reset-chatter-39',
            est_demo=True)
        self.admin = User.objects.create_user(
            'reset-actor-39', password='x', company=self.company,
            is_staff=True)
        self.ct = ContentType.objects.get_for_model(Company)

    def _client(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        return c

    def test_reset_demo_logs_a_note_on_the_fresh_company_row(self):
        r = self._client().post(
            f'/api/django/companies/{self.company.id}/reset-demo/')
        self.assertEqual(r.status_code, 200)
        fresh = Company.objects.get(slug='demo-reset-chatter-39')
        # Une nouvelle ligne (le reset supprime puis recrée la société) —
        # l'entrée de chatter doit viser CETTE ligne, jamais l'ancienne PK
        # (supprimée par la cascade de `records.Activity.company`).
        self.assertNotEqual(fresh.pk, self.company.pk)
        entries = Activity.objects.filter(
            content_type=self.ct, object_id=fresh.pk,
            kind=Activity.Kind.NOTE)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertIn('Données de démonstration réinitialisées par', entry.body)
        self.assertIn('reset-actor-39', entry.body)

    def test_reset_demo_note_survives_with_no_created_by_fk(self):
        # L'acteur d'origine est supprimé par la purge (voir la note du
        # module) : `created_by` reste None (jamais une FK orpheline), le nom
        # de l'acteur vit dans le texte (`body`) — capturé AVANT la purge.
        self._client().post(
            f'/api/django/companies/{self.company.id}/reset-demo/')
        fresh = Company.objects.get(slug='demo-reset-chatter-39')
        entry = Activity.objects.get(
            content_type=self.ct, object_id=fresh.pk,
            kind=Activity.Kind.NOTE)
        self.assertIsNone(entry.created_by)
