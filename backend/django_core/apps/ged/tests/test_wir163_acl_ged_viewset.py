"""WIR163 — API + écran de gestion pour `ged.AclGed` (AclGedViewSet).

Couvre :
  * lecture (`list`) ouverte à tout rôle authentifié ; écriture (`create`/
    `update`/`destroy`) réservée responsable/admin (même patron que
    `RegleAclMetadonneeViewSet`/`kb.KbArticleAclViewSet`) ;
  * `company`/`created_by` posés côté serveur (jamais lus du corps) ;
  * validations propres (400, jamais une 500 de CheckConstraint) : cible
    exactement-une (folder XOR document), principal au moins-un
    (utilisateur/role), cible obligatoirement de la société de l'appelant ;
  * filtres `?folder=`/`?document=`/`?niveau=` ;
  * DONE (critère du plan) — poser une entrée `AclGed` DEPUIS L'API a un
    effet IMMÉDIAT vérifié sur `selectors.documents_visible_to_user` pour un
    AUTRE utilisateur de test (aucun cache, aucune bascule additionnelle).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import selectors
from apps.ged.models import AclGed, Cabinet, Document, Folder

User = get_user_model()

BASE = '/api/django/ged/acls/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Wir163Base(TestCase):
    def setUp(self):
        self.co_a = make_company('wir163-a', 'WIR163 A')
        self.co_b = make_company('wir163-b', 'WIR163 B')
        self.admin_a = make_user(self.co_a, 'wir163-admin-a', 'admin')
        self.responsable_a = make_user(self.co_a, 'wir163-resp-a', 'responsable')
        self.normal_a = make_user(self.co_a, 'wir163-normal-a', 'normal')
        self.autre_normal_a = make_user(
            self.co_a, 'wir163-autre-normal-a', 'normal')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Confidentiel')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat-042.pdf')

        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Admin B')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Autre société')
        self.doc_b = Document.objects.create(
            company=self.co_b, folder=self.folder_b, nom='autre.pdf')


class PermissionsTests(Wir163Base):
    def test_lecture_ouverte_a_tout_role(self):
        AclGed.objects.create(
            company=self.co_a, document=self.doc_a, utilisateur=self.admin_a,
            niveau='gestion')
        resp = auth(self.normal_a).get(BASE)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_creation_refusee_a_un_role_normal(self):
        resp = auth(self.normal_a).post(BASE, {
            'document': self.doc_a.id, 'utilisateur': self.normal_a.id,
            'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_creation_autorisee_responsable_et_admin(self):
        for user in (self.responsable_a, self.admin_a):
            resp = auth(user).post(BASE, {
                'document': self.doc_a.id, 'utilisateur': self.normal_a.id,
                'niveau': 'lecture',
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)

    def test_company_et_created_by_poses_cote_serveur(self):
        resp = auth(self.admin_a).post(BASE, {
            'document': self.doc_a.id, 'utilisateur': self.normal_a.id,
            'niveau': 'lecture', 'company': 999999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        entry = AclGed.objects.get(id=resp.data['id'])
        self.assertEqual(entry.company_id, self.co_a.id)
        self.assertEqual(entry.created_by_id, self.admin_a.id)


class ValidationTests(Wir163Base):
    def test_ni_dossier_ni_document_refuse(self):
        resp = auth(self.admin_a).post(BASE, {
            'utilisateur': self.normal_a.id, 'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_dossier_et_document_a_la_fois_refuse(self):
        resp = auth(self.admin_a).post(BASE, {
            'folder': self.folder_a.id, 'document': self.doc_a.id,
            'utilisateur': self.normal_a.id, 'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_sans_principal_refuse(self):
        resp = auth(self.admin_a).post(BASE, {
            'document': self.doc_a.id, 'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_cible_hors_societe_refusee(self):
        resp = auth(self.admin_a).post(BASE, {
            'document': self.doc_b.id, 'utilisateur': self.normal_a.id,
            'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(
            AclGed.objects.filter(document=self.doc_b).exists())


class FiltersTests(Wir163Base):
    def test_filtre_document_et_niveau(self):
        AclGed.objects.create(
            company=self.co_a, document=self.doc_a, utilisateur=self.admin_a,
            niveau='gestion')
        AclGed.objects.create(
            company=self.co_a, folder=self.folder_a, role=None,
            utilisateur=self.normal_a, niveau='lecture')
        resp = auth(self.admin_a).get(BASE, {'document': self.doc_a.id})
        self.assertEqual(resp.data['count'], 1, resp.data)
        resp = auth(self.admin_a).get(BASE, {'niveau': 'lecture'})
        self.assertEqual(resp.data['count'], 1, resp.data)

    def test_isolation_societe(self):
        AclGed.objects.create(
            company=self.co_b, document=self.doc_b,
            utilisateur=make_user(self.co_b, 'wir163-user-b'),
            niveau='lecture')
        resp = auth(self.admin_a).get(BASE)
        self.assertEqual(resp.data['count'], 0, resp.data)


class IsolationMultiSocieteTests(Wir163Base):
    """RÉGRESSION (SCA4) — `AclGedViewSet` est basé sur
    `core.viewsets.CompanyScopedModelViewSet` : un utilisateur de la société A
    ne LIT ni n'ÉCRIT jamais une entrée ACL de la société B, et ne peut pas
    s'attribuer une entrée à la société B en passant `company` dans le corps.

    Une entrée ACL gouverne QUI voit quel document : une fuite ici laisserait
    une société lire — ou pire, réécrire — les droits d'accès d'une autre.
    """

    def setUp(self):
        super().setUp()
        self.admin_b = make_user(self.co_b, 'wir163-admin-b', 'admin')
        self.acl_a = AclGed.objects.create(
            company=self.co_a, document=self.doc_a,
            utilisateur=self.normal_a, niveau='lecture')
        self.acl_b = AclGed.objects.create(
            company=self.co_b, document=self.doc_b,
            utilisateur=self.admin_b, niveau='gestion')

    def test_viewset_herite_du_socle_scope_societe(self):
        from core.viewsets import CompanyScopedModelViewSet

        from apps.ged.views import AclGedViewSet
        self.assertTrue(
            issubclass(AclGedViewSet, CompanyScopedModelViewSet),
            'AclGedViewSet doit hériter de CompanyScopedModelViewSet (SCA4).')

    def test_list_ne_renvoie_que_les_entrees_de_sa_societe(self):
        resp = auth(self.admin_a).get(BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {ligne['id'] for ligne in resp.data['results']}
        self.assertEqual(ids, {self.acl_a.id}, resp.data)

    def test_retrieve_entree_autre_societe_404(self):
        resp = auth(self.admin_a).get(f'{BASE}{self.acl_b.id}/')
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_update_et_delete_entree_autre_societe_404(self):
        resp = auth(self.admin_a).patch(
            f'{BASE}{self.acl_b.id}/', {'niveau': 'lecture'}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
        resp = auth(self.admin_a).delete(f'{BASE}{self.acl_b.id}/')
        self.assertEqual(resp.status_code, 404, resp.data)
        self.acl_b.refresh_from_db()
        self.assertEqual(self.acl_b.company_id, self.co_b.id)
        self.assertEqual(self.acl_b.niveau, 'gestion')

    def test_company_du_corps_ne_peut_pas_attribuer_l_entree_a_la_societe_b(self):
        resp = auth(self.admin_a).post(BASE, {
            'folder': self.folder_a.id, 'utilisateur': self.normal_a.id,
            'niveau': 'gestion', 'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        entry = AclGed.objects.get(id=resp.data['id'])
        self.assertEqual(entry.company_id, self.co_a.id)
        # …et la société B ne voit RIEN de neuf apparaître chez elle.
        resp = auth(self.admin_b).get(BASE)
        ids = {ligne['id'] for ligne in resp.data['results']}
        self.assertEqual(ids, {self.acl_b.id}, resp.data)


class EffetImmediatSurVisibiliteTests(Wir163Base):
    """DONE — poser une entrée AclGed depuis l'API a un effet immédiat sur
    `documents_visible_to_user` pour un AUTRE utilisateur de test."""

    def test_restreindre_puis_accorder_change_immediatement_la_visibilite(self):
        # Un second document NON gouverné (aucune ACL) reste toujours visible,
        # quoi qu'il arrive — seul le document ciblé est affecté.
        doc_libre = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='libre.pdf')

        # Avant toute ACL : GED19 backward-compat — tout est visible.
        visibles = set(selectors.documents_visible_to_user(
            self.autre_normal_a).values_list('pk', flat=True))
        self.assertIn(self.doc_a.pk, visibles)
        self.assertIn(doc_libre.pk, visibles)

        # L'admin restreint doc_a au SEUL normal_a (via l'API de gestion).
        resp = auth(self.admin_a).post(BASE, {
            'document': self.doc_a.id, 'utilisateur': self.normal_a.id,
            'niveau': 'lecture', 'herite': False,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        # Effet IMMÉDIAT pour autre_normal_a (jamais invité) : doc_a disparaît,
        # doc_libre (non gouverné) reste visible sans le moindre changement.
        visibles = set(selectors.documents_visible_to_user(
            self.autre_normal_a).values_list('pk', flat=True))
        self.assertNotIn(self.doc_a.pk, visibles)
        self.assertIn(doc_libre.pk, visibles)
        # normal_a, lui, voit toujours doc_a (l'entrée le cible explicitement).
        visibles_normal_a = set(selectors.documents_visible_to_user(
            self.normal_a).values_list('pk', flat=True))
        self.assertIn(self.doc_a.pk, visibles_normal_a)

        # L'admin accorde ENSUITE la lecture à autre_normal_a (toujours via
        # l'API) : effet immédiat, sans aucune autre bascule.
        resp = auth(self.admin_a).post(BASE, {
            'document': self.doc_a.id, 'utilisateur': self.autre_normal_a.id,
            'niveau': 'lecture', 'herite': False,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        visibles = set(selectors.documents_visible_to_user(
            self.autre_normal_a).values_list('pk', flat=True))
        self.assertIn(self.doc_a.pk, visibles)

        # Révocation (DELETE) via l'API : retire à nouveau l'accès explicite —
        # sans admin_a/superuser, autre_normal_a redevient exclu de doc_a
        # (la restriction posée par la 1ère entrée tient toujours).
        entry_id = resp.data['id']
        resp = auth(self.admin_a).delete(f'{BASE}{entry_id}/')
        self.assertEqual(resp.status_code, 204, resp.data)
        visibles = set(selectors.documents_visible_to_user(
            self.autre_normal_a).values_list('pk', flat=True))
        self.assertNotIn(self.doc_a.pk, visibles)
