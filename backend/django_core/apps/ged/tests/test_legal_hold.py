"""GED24 — Rétention légale / legal hold (gel anti-suppression).

Couvre :
  * pose d'un hold actif → suppression BLOQUÉE (modèle + API 403, jamais 500) ;
  * levée du hold → suppression RÉ-AUTORISÉE ;
  * pose/levée IDEMPOTENTES (pas de doublon de hold actif ; levée no-op) ;
  * isolation par société (A ne voit/touche pas les holds de B) ;
  * `company`/`place_par` posés côté serveur (jamais lus du corps) ;
  * indépendance vis-à-vis des politiques de rétention (GED22) ;
  * couche distincte de l'archivage write-once (GED23).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import selectors, services
from apps.ged.models import (
    Cabinet, Document, Folder, LegalHold, LegalHoldError,
    PolitiqueRetention, RETENTION_SUPPRIMER,
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


class LegalHoldBase(TestCase):
    URL = '/api/django/ged/legal-holds/'

    def setUp(self):
        self.co_a = make_company('ged24-a', 'Ged24 A')
        self.co_b = make_company('ged24-b', 'Ged24 B')
        self.admin_a = make_user(self.co_a, 'ged24-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'ged24-admin-b', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat litige')


class LegalHoldServiceTests(LegalHoldBase):
    def test_placer_sets_server_side_fields(self):
        """placer_legal_hold pose company/place_par côté serveur + actif=True."""
        hold = services.placer_legal_hold(
            self.doc_a, user=self.admin_a, motif='Contentieux X')
        self.assertEqual(hold.company_id, self.co_a.id)
        self.assertEqual(hold.place_par_id, self.admin_a.id)
        self.assertTrue(hold.actif)
        self.assertEqual(hold.motif, 'Contentieux X')
        self.assertTrue(self.doc_a.est_sous_legal_hold)

    def test_hold_blocks_model_delete(self):
        """Document.delete() est refusé tant qu'un hold actif le couvre."""
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        with self.assertRaises(LegalHoldError):
            self.doc_a.delete()
        self.assertTrue(Document.objects.filter(pk=self.doc_a.pk).exists())

    def test_lever_reallows_delete(self):
        """Après levée, le document redevient supprimable."""
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        leves = services.lever_legal_hold(self.doc_a, user=self.admin_a)
        self.assertEqual(leves, 1)
        self.doc_a.refresh_from_db()
        self.assertFalse(self.doc_a.est_sous_legal_hold)
        # Plus aucun gel → la suppression passe.
        self.doc_a.delete()
        self.assertFalse(Document.objects.filter(pk=self.doc_a.pk).exists())

    def test_lever_traces_server_side(self):
        """La levée trace date_levee + leve_par et conserve la trace (actif=False)."""
        hold = services.placer_legal_hold(self.doc_a, user=self.admin_a)
        services.lever_legal_hold(self.doc_a, user=self.admin_a)
        hold.refresh_from_db()
        self.assertFalse(hold.actif)
        self.assertIsNotNone(hold.date_levee)
        self.assertEqual(hold.leve_par_id, self.admin_a.id)

    def test_placer_is_idempotent(self):
        """Poser deux fois ne crée pas un second hold actif (idempotent)."""
        h1 = services.placer_legal_hold(self.doc_a, user=self.admin_a)
        h2 = services.placer_legal_hold(self.doc_a, user=self.admin_a)
        self.assertEqual(h1.id, h2.id)
        self.assertEqual(
            LegalHold.objects.filter(document=self.doc_a, actif=True).count(), 1)

    def test_lever_without_hold_is_noop(self):
        """Lever sans hold actif est un no-op (renvoie 0)."""
        self.assertEqual(
            services.lever_legal_hold(self.doc_a, user=self.admin_a), 0)

    def test_re_placer_after_lever_creates_new_hold(self):
        """Reposer après levée crée un NOUVEAU hold (le précédent reste tracé)."""
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        services.lever_legal_hold(self.doc_a, user=self.admin_a)
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        self.assertEqual(
            LegalHold.objects.filter(document=self.doc_a).count(), 2)
        self.assertTrue(self.doc_a.est_sous_legal_hold)

    def test_cross_company_placer_rejected(self):
        """On ne pose pas un hold sur le document d'une autre société."""
        with self.assertRaises(PermissionError):
            services.placer_legal_hold(self.doc_a, user=self.admin_b)

    def test_cross_company_lever_rejected(self):
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        with self.assertRaises(PermissionError):
            services.lever_legal_hold(self.doc_a, user=self.admin_b)

    def test_hold_independent_of_retention_policy(self):
        """Le hold est une couche distincte d'une politique de rétention (GED22).

        Une politique 'supprimer' n'efface jamais passivement ; et même posée,
        elle ne lève pas le gel — le hold reste actif et bloque la suppression."""
        PolitiqueRetention.objects.create(
            company=self.co_a, nom='Purge 30j',
            duree_conservation_jours=30, action_echeance=RETENTION_SUPPRIMER)
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        # Le hold prime : la suppression reste gelée.
        with self.assertRaises(LegalHoldError):
            self.doc_a.delete()
        self.assertTrue(self.doc_a.est_sous_legal_hold)

    def test_assert_not_legal_hold_guard(self):
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        with self.assertRaises(LegalHoldError):
            services.assert_not_legal_hold(self.doc_a)
        services.lever_legal_hold(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        # Levé → la garde passe sans lever.
        services.assert_not_legal_hold(self.doc_a)


class LegalHoldApiTests(LegalHoldBase):
    def test_held_document_delete_returns_403_not_500(self):
        """DELETE d'un document gelé renvoie 403 (jamais 500), doc préservé."""
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        resp = auth(self.admin_a).delete(
            f'/api/django/ged/documents/{self.doc_a.id}/')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertTrue(Document.objects.filter(pk=self.doc_a.pk).exists())

    def test_lever_then_delete_succeeds(self):
        """Après levée via l'action, le DELETE du document passe (204)."""
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        api = auth(self.admin_a)
        r_lever = api.post(
            f'/api/django/ged/documents/{self.doc_a.id}/lever-legal-hold/')
        self.assertEqual(r_lever.status_code, 200, r_lever.data)
        r_del = api.delete(f'/api/django/ged/documents/{self.doc_a.id}/')
        self.assertEqual(r_del.status_code, 204)
        # GED26 — après levée du hold, le DELETE passe et met en corbeille
        # (soft-delete) : la ligne subsiste avec supprime_le posé.
        self.doc_a.refresh_from_db()
        self.assertIsNotNone(self.doc_a.supprime_le)

    def test_placer_action_sets_company_server_side(self):
        """POST documents/<id>/placer-legal-hold/ pose company côté serveur."""
        resp = auth(self.admin_a).post(
            f'/api/django/ged/documents/{self.doc_a.id}/placer-legal-hold/',
            {'motif': 'Litige', 'company': self.co_b.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        hold = LegalHold.objects.get(id=resp.data['id'])
        self.assertEqual(hold.company_id, self.co_a.id)
        self.assertEqual(hold.place_par_id, self.admin_a.id)

    def test_create_viewset_sets_company_server_side(self):
        """POST legal-holds/ crée (company/place_par côté serveur, injection ignorée)."""
        resp = auth(self.admin_a).post(self.URL, {
            'document': self.doc_a.id,
            'company': self.co_b.id,  # injection ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        hold = LegalHold.objects.get(id=resp.data['id'])
        self.assertEqual(hold.company_id, self.co_a.id)

    def test_create_is_idempotent(self):
        api = auth(self.admin_a)
        r1 = api.post(self.URL, {'document': self.doc_a.id}, format='json')
        r2 = api.post(self.URL, {'document': self.doc_a.id}, format='json')
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r1.data['id'], r2.data['id'])
        self.assertEqual(
            LegalHold.objects.filter(document=self.doc_a, actif=True).count(), 1)

    def test_lever_viewset_action(self):
        hold = services.placer_legal_hold(self.doc_a, user=self.admin_a)
        resp = auth(self.admin_a).post(f'{self.URL}{hold.id}/lever/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['leves'], 1)
        hold.refresh_from_db()
        self.assertFalse(hold.actif)

    def test_update_not_allowed_on_hold(self):
        """L'API legal-holds n'expose ni update ni delete (pose puis levée)."""
        hold = services.placer_legal_hold(self.doc_a, user=self.admin_a)
        api = auth(self.admin_a)
        r_patch = api.patch(f'{self.URL}{hold.id}/', {'motif': 'x'},
                            format='json')
        self.assertEqual(r_patch.status_code, 405)
        r_del = api.delete(f'{self.URL}{hold.id}/')
        self.assertEqual(r_del.status_code, 405)

    def test_tenant_isolation_list(self):
        hold = services.placer_legal_hold(self.doc_a, user=self.admin_a)
        doc_b = Document.objects.create(
            company=self.co_b, folder=Folder.objects.create(
                company=self.co_b, cabinet=self.cab_b, nom='Dos B'),
            nom='Doc B')
        hold_b = LegalHold.objects.create(company=self.co_b, document=doc_b)
        resp = auth(self.admin_a).get(self.URL)
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(hold.id, ids)
        self.assertNotIn(hold_b.id, ids)

    def test_create_requires_responsable_role(self):
        """Pose refusée (403) à un compte sans rôle d'écriture."""
        viewer = make_user(self.co_a, 'ged24-viewer', 'normal')
        resp = auth(viewer).post(self.URL, {'document': self.doc_a.id},
                                 format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_read_allowed_to_any_role(self):
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        viewer = make_user(self.co_a, 'ged24-viewer2', 'normal')
        resp = auth(viewer).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_create_rejects_cross_company_document(self):
        """On ne gèle pas le document d'une autre société via l'API (404)."""
        doc_b = Document.objects.create(
            company=self.co_b, folder=Folder.objects.create(
                company=self.co_b, cabinet=self.cab_b, nom='Dos B'),
            nom='Doc B')
        resp = auth(self.admin_a).post(
            self.URL, {'document': doc_b.id}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_selector_active_hold_for_document(self):
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        self.assertIsNotNone(
            selectors.legal_hold_actif_for_document(self.doc_a))
        services.lever_legal_hold(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        self.assertIsNone(
            selectors.legal_hold_actif_for_document(self.doc_a))


class DocumentVersionLegalHoldTests(LegalHoldBase):
    """AUD810 — `DocumentVersion.delete()` ignorait le legal hold (GED24) du
    document parent : une version d'un document sous hold actif restait
    purgeable (destruction de preuve possible), alors que `Document.delete()`
    teste bien les deux gels. `DocumentVersionViewSet` gagne aussi la garde
    de gouvernance (WIR174) : effacer une version est un effacement RÉEL
    (pas de corbeille pour les versions), pas une écriture opérationnelle
    courante."""

    def setUp(self):
        super().setUp()
        self.version_a = services.add_version(
            self.doc_a, file_key='k/v1.pdf', company=self.co_a,
            filename='v1.pdf', uploaded_by=self.admin_a)

    def test_hold_blocks_version_model_delete(self):
        """DocumentVersion.delete() est refusé tant qu'un hold actif couvre
        le document parent — AVANT le fix, ce test aurait rendu 204/succès."""
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        from apps.ged.models import DocumentVersion, LegalHoldError
        with self.assertRaises(LegalHoldError):
            self.version_a.delete()
        self.assertTrue(
            DocumentVersion.objects.filter(pk=self.version_a.pk).exists())

    def test_lever_reallows_version_delete(self):
        """Après levée, la version redevient supprimable."""
        from apps.ged.models import DocumentVersion
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        services.lever_legal_hold(self.doc_a, user=self.admin_a)
        self.doc_a.refresh_from_db()
        self.version_a.delete()
        self.assertFalse(
            DocumentVersion.objects.filter(pk=self.version_a.pk).exists())

    def test_no_hold_version_delete_still_works(self):
        """Sans hold ni archivage, la suppression d'une version reste libre
        (pas de régression sur le comportement courant)."""
        from apps.ged.models import DocumentVersion
        self.version_a.delete()
        self.assertFalse(
            DocumentVersion.objects.filter(pk=self.version_a.pk).exists())

    def test_held_version_api_delete_returns_403_not_500(self):
        """DELETE /ged/versions/<id>/ d'une version d'un document gelé rend
        403 (jamais 500), version préservée — un porteur `ged_gouvernance`
        (admin ici) est le palier attendu pour cette action."""
        from apps.ged.models import DocumentVersion
        services.placer_legal_hold(self.doc_a, user=self.admin_a)
        resp = auth(self.admin_a).delete(
            f'/api/django/ged/versions/{self.version_a.id}/')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertTrue(
            DocumentVersion.objects.filter(pk=self.version_a.pk).exists())

    def test_ged_gerer_sans_gouvernance_403_on_version_destroy(self):
        """AUD810 — `destroy` sur une version exige `ged_gouvernance`, pas
        seulement `ged_gerer` (écriture documentaire courante)."""
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.co_a, nom='aud810-gerer',
            permissions=['ged_voir', 'ged_gerer'])
        gerer_user = User.objects.create_user(
            username='aud810-gerer', password='x',
            company=self.co_a, role=role)
        resp = auth(gerer_user).delete(
            f'/api/django/ged/versions/{self.version_a.id}/')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_ged_gouvernance_can_delete_version(self):
        """Un titulaire `ged_gouvernance` reste autorisé (aucune régression)."""
        from apps.ged.models import DocumentVersion
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.co_a, nom='aud810-gouvernance',
            permissions=['ged_voir', 'ged_gerer', 'ged_gouvernance'])
        gouv_user = User.objects.create_user(
            username='aud810-gouvernance', password='x',
            company=self.co_a, role=role)
        resp = auth(gouv_user).delete(
            f'/api/django/ged/versions/{self.version_a.id}/')
        self.assertEqual(resp.status_code, 204, resp.data)
        self.assertFalse(
            DocumentVersion.objects.filter(pk=self.version_a.pk).exists())
