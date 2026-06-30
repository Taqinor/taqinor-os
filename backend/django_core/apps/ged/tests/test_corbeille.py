"""GED26 — Corbeille & restauration (soft-delete réversible).

Couvre :
  * DELETE = mise en corbeille (soft-delete), PAS un effacement réel ;
  * la corbeille est masquée des listes/recherches par défaut ;
  * l'action `corbeille` liste les documents soft-supprimés ;
  * `restaurer-corbeille` sort un document de la corbeille (réversible) ;
  * `mettre-en-corbeille` (action explicite) + idempotence ;
  * un document archivé légalement (GED23) ne peut pas être mis en corbeille → 403 (jamais 500) ;
  * un document sous legal hold actif (GED24) ne peut pas être mis en corbeille → 403 ;
  * `purger` efface définitivement (réel delete) un document EN corbeille, en respectant les gardes légales ;
  * isolation par société (A ne voit/touche pas la corbeille de B) ;
  * traçabilité (`supprime_le`/`supprime_par`) posée côté serveur.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import selectors, services
from apps.ged.models import (
    ArchivageLegalError, Cabinet, Document, Folder, LegalHoldError,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
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


class CorbeilleBase(TestCase):
    LIST = '/api/django/ged/documents/'

    def setUp(self):
        self.co_a = make_company('ged26-a', 'Ged26 A')
        self.co_b = make_company('ged26-b', 'Ged26 B')
        self.admin_a = make_user(self.co_a, 'ged26-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'ged26-admin-b', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Dossier B')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Doc A vivant')


class CorbeilleServiceTests(CorbeilleBase):
    def test_mettre_en_corbeille_sets_server_side_fields(self):
        """mettre_en_corbeille pose supprime_le + supprime_par côté serveur."""
        services.mettre_en_corbeille(self.doc_a, self.admin_a)
        self.doc_a.refresh_from_db()
        self.assertIsNotNone(self.doc_a.supprime_le)
        self.assertEqual(self.doc_a.supprime_par_id, self.admin_a.id)
        self.assertTrue(self.doc_a.est_dans_corbeille)

    def test_corbeille_does_not_hard_delete(self):
        """La mise en corbeille ne supprime PAS la ligne en base."""
        services.mettre_en_corbeille(self.doc_a, self.admin_a)
        self.assertTrue(Document.objects.filter(pk=self.doc_a.pk).exists())

    def test_restaurer_clears_soft_delete(self):
        """restaurer_de_corbeille vide supprime_le/par → document réactivé."""
        services.mettre_en_corbeille(self.doc_a, self.admin_a)
        services.restaurer_de_corbeille(self.doc_a)
        self.doc_a.refresh_from_db()
        self.assertIsNone(self.doc_a.supprime_le)
        self.assertIsNone(self.doc_a.supprime_par_id)
        self.assertFalse(self.doc_a.est_dans_corbeille)

    def test_mettre_en_corbeille_idempotent(self):
        """Remettre en corbeille un doc déjà en corbeille préserve la trace."""
        services.mettre_en_corbeille(self.doc_a, self.admin_a)
        self.doc_a.refresh_from_db()
        premiere = self.doc_a.supprime_le
        # Deuxième appel : no-op (ni date ni auteur réécrasés).
        services.mettre_en_corbeille(self.doc_a, self.admin_b)
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.supprime_le, premiere)
        self.assertEqual(self.doc_a.supprime_par_id, self.admin_a.id)

    def test_restaurer_idempotent_on_active_doc(self):
        """restaurer_de_corbeille sur un doc vivant est un no-op."""
        services.restaurer_de_corbeille(self.doc_a)  # pas en corbeille
        self.doc_a.refresh_from_db()
        self.assertIsNone(self.doc_a.supprime_le)

    def test_archived_doc_cannot_be_trashed(self):
        """GED23 — un document archivé légalement n'est pas mettable en corbeille."""
        services.archiver_legalement(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        with self.assertRaises(ArchivageLegalError):
            services.mettre_en_corbeille(self.doc_a, self.admin_a)
        self.doc_a.refresh_from_db()
        self.assertIsNone(self.doc_a.supprime_le)

    def test_legal_hold_doc_cannot_be_trashed(self):
        """GED24 — un document sous legal hold actif n'est pas mettable en corbeille."""
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        with self.assertRaises(LegalHoldError):
            services.mettre_en_corbeille(self.doc_a, self.admin_a)
        self.doc_a.refresh_from_db()
        self.assertIsNone(self.doc_a.supprime_le)

    def test_purger_requires_trash_first(self):
        """purger_definitivement refuse un document qui n'est pas en corbeille."""
        with self.assertRaises(ValueError):
            services.purger_definitivement(self.doc_a)
        self.assertTrue(Document.objects.filter(pk=self.doc_a.pk).exists())

    def test_purger_hard_deletes_from_trash(self):
        """purger_definitivement efface réellement un document en corbeille."""
        services.mettre_en_corbeille(self.doc_a, self.admin_a)
        services.purger_definitivement(self.doc_a)
        self.assertFalse(Document.objects.filter(pk=self.doc_a.pk).exists())

    def test_purger_respects_legal_hold(self):
        """purger d'un doc en corbeille puis sous hold reste gelé (garde modèle)."""
        services.mettre_en_corbeille(self.doc_a, self.admin_a)
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        with self.assertRaises(LegalHoldError):
            services.purger_definitivement(self.doc_a)
        self.assertTrue(Document.objects.filter(pk=self.doc_a.pk).exists())


class CorbeilleSelectorTests(CorbeilleBase):
    def test_default_list_excludes_trash(self):
        """documents_visible_to_user EXCLUT les documents en corbeille."""
        services.mettre_en_corbeille(self.doc_a, self.admin_a)
        ids = list(
            selectors.documents_visible_to_user(self.admin_a)
            .values_list('id', flat=True))
        self.assertNotIn(self.doc_a.id, ids)

    def test_corbeille_selector_lists_only_trash(self):
        """documents_corbeille ne renvoie QUE les documents soft-supprimés."""
        vivant = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Encore vivant')
        services.mettre_en_corbeille(self.doc_a, self.admin_a)
        ids = list(
            selectors.documents_corbeille(self.admin_a)
            .values_list('id', flat=True))
        self.assertIn(self.doc_a.id, ids)
        self.assertNotIn(vivant.id, ids)

    def test_corbeille_selector_company_scoped(self):
        """La corbeille est bornée à la société (A ne voit pas la corbeille de B)."""
        doc_b = Document.objects.create(
            company=self.co_b, folder=self.folder_b, nom='Doc B')
        services.mettre_en_corbeille(doc_b, self.admin_b)
        ids = list(
            selectors.documents_corbeille(self.admin_a)
            .values_list('id', flat=True))
        self.assertNotIn(doc_b.id, ids)


class CorbeilleApiTests(CorbeilleBase):
    def test_delete_soft_deletes_into_trash(self):
        """DELETE met en corbeille (soft) au lieu d'effacer réellement."""
        api = auth(self.admin_a)
        resp = api.delete(f'{self.LIST}{self.doc_a.id}/')
        self.assertEqual(resp.status_code, 204)
        # Toujours en base, mais en corbeille.
        self.doc_a.refresh_from_db()
        self.assertIsNotNone(self.doc_a.supprime_le)
        self.assertEqual(self.doc_a.supprime_par_id, self.admin_a.id)

    def test_trashed_hidden_from_default_list(self):
        """Un document en corbeille n'apparaît plus dans la liste par défaut."""
        api = auth(self.admin_a)
        api.delete(f'{self.LIST}{self.doc_a.id}/')
        resp = api.get(self.LIST)
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(self.doc_a.id, ids)

    def test_trashed_appears_in_corbeille_endpoint(self):
        """L'action corbeille liste le document soft-supprimé."""
        api = auth(self.admin_a)
        api.delete(f'{self.LIST}{self.doc_a.id}/')
        resp = api.get(f'{self.LIST}corbeille/')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.doc_a.id, ids)

    def test_restaurer_corbeille_returns_doc_to_list(self):
        """restaurer-corbeille rend le document visible dans la liste par défaut."""
        api = auth(self.admin_a)
        api.delete(f'{self.LIST}{self.doc_a.id}/')
        resp = api.post(f'{self.LIST}{self.doc_a.id}/restaurer-corbeille/')
        self.assertEqual(resp.status_code, 200)
        self.doc_a.refresh_from_db()
        self.assertIsNone(self.doc_a.supprime_le)
        liste = api.get(self.LIST)
        ids = [r['id'] for r in rows(liste)]
        self.assertIn(self.doc_a.id, ids)

    def test_mettre_en_corbeille_action(self):
        """L'action explicite mettre-en-corbeille met le document en corbeille."""
        api = auth(self.admin_a)
        resp = api.post(f'{self.LIST}{self.doc_a.id}/mettre-en-corbeille/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.doc_a.refresh_from_db()
        self.assertIsNotNone(self.doc_a.supprime_le)

    def test_archived_doc_delete_is_403_not_500(self):
        """DELETE d'un document archivé légalement → 403 (jamais 500)."""
        services.archiver_legalement(self.doc_a, user=self.admin_a)
        api = auth(self.admin_a)
        resp = api.delete(f'{self.LIST}{self.doc_a.id}/')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.doc_a.refresh_from_db()
        self.assertIsNone(self.doc_a.supprime_le)

    def test_legal_hold_doc_delete_is_403_not_500(self):
        """DELETE d'un document sous legal hold actif → 403 (jamais 500)."""
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        api = auth(self.admin_a)
        resp = api.delete(f'{self.LIST}{self.doc_a.id}/')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.doc_a.refresh_from_db()
        self.assertIsNone(self.doc_a.supprime_le)

    def test_purger_endpoint_hard_deletes(self):
        """L'action purger efface définitivement un document en corbeille."""
        api = auth(self.admin_a)
        api.delete(f'{self.LIST}{self.doc_a.id}/')
        resp = api.post(f'{self.LIST}{self.doc_a.id}/purger/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Document.objects.filter(pk=self.doc_a.pk).exists())

    def test_corbeille_endpoint_company_isolated(self):
        """La corbeille d'une société n'expose jamais celle d'une autre."""
        doc_b = Document.objects.create(
            company=self.co_b, folder=self.folder_b, nom='Doc B corbeille')
        services.mettre_en_corbeille(doc_b, self.admin_b)
        api = auth(self.admin_a)
        resp = api.get(f'{self.LIST}corbeille/')
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(doc_b.id, ids)

    def test_restaurer_other_company_doc_is_404(self):
        """restaurer-corbeille d'un document d'une autre société → 404."""
        doc_b = Document.objects.create(
            company=self.co_b, folder=self.folder_b, nom='Doc B')
        services.mettre_en_corbeille(doc_b, self.admin_b)
        api = auth(self.admin_a)
        resp = api.post(f'{self.LIST}{doc_b.id}/restaurer-corbeille/')
        self.assertEqual(resp.status_code, 404)
