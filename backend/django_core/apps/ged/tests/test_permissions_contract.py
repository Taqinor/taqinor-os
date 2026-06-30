"""GED37 — Permissions & garde-prix sur TOUS les endpoints GED.

Contrat vérifié de bout en bout :
  * LECTURE (list) ouverte à tout rôle authentifié (IsAnyRole) ;
  * ÉCRITURE (create/update/delete + actions de mutation) réservée aux
    responsables/admins — un utilisateur « normal » (lecture seule) est REFUSÉ
    (403) sur les endpoints d'écriture ;
  * ENDPOINTS SENSIBLES (journal d'audit GED35) réservés aux responsables/admins
    même en LECTURE ;
  * GARDE-PRIX : aucune réponse GED n'expose un champ de prix d'achat
    (`prix_achat`/`prix`/`cout`/`marge`) — la GED ne porte aucune donnée de prix.
  * Tout est borné à la société (un anonyme est rejeté partout sauf le partage
    public tokenisé, hors scope ici).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged.models import Cabinet, Document, Folder

User = get_user_model()

BASE = '/api/django/ged'

# Champs interdits dans toute réponse GED (garde-prix).
CHAMPS_PRIX_INTERDITS = ('prix_achat', 'prix', 'cout', 'marge', 'price')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class GedPermissionContractTests(TestCase):
    def setUp(self):
        self.co = make_company('ged37', 'Ged37')
        self.admin = make_user(self.co, 'ged37-admin', 'admin')
        self.normal = make_user(self.co, 'ged37-normal', 'normal')
        self.cab = Cabinet.objects.create(company=self.co, nom='Docs')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='F')
        self.doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='Doc')

    # ── Lecture ouverte à tout rôle ──────────────────────────────────────────
    def test_lecture_documents_ouverte_a_tout_role(self):
        for user in (self.admin, self.normal):
            resp = auth(user).get(f'{BASE}/documents/')
            self.assertEqual(resp.status_code, 200, user.username)

    def test_lecture_anonyme_refusee(self):
        resp = APIClient().get(f'{BASE}/documents/')
        self.assertIn(resp.status_code, (401, 403))

    # ── Écriture réservée responsable/admin ──────────────────────────────────
    def test_creation_cabinet_refusee_au_normal(self):
        resp = auth(self.normal).post(
            f'{BASE}/cabinets/', {'nom': 'Interdit'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_creation_cabinet_autorisee_admin(self):
        resp = auth(self.admin).post(
            f'{BASE}/cabinets/', {'nom': 'OK'}, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_action_mutation_refusee_au_normal(self):
        # GED34 — classification (mutation custom_data) : écriture → 403 normal.
        resp = auth(self.normal).post(
            f'{BASE}/documents/{self.doc.id}/classer/')
        self.assertEqual(resp.status_code, 403)

    def test_scan_lot_refuse_au_normal(self):
        resp = auth(self.normal).post(
            f'{BASE}/documents/scan-lot/', {'folder': self.folder.id})
        self.assertEqual(resp.status_code, 403)

    def test_import_masse_refuse_au_normal(self):
        resp = auth(self.normal).post(
            f'{BASE}/documents/import-masse/', {'folder': self.folder.id})
        self.assertEqual(resp.status_code, 403)

    # ── Endpoints sensibles : audit admin-only même en lecture (GED35) ───────
    def test_journal_acces_liste_refusee_au_normal(self):
        resp = auth(self.normal).get(f'{BASE}/journal-acces/')
        self.assertEqual(resp.status_code, 403)

    def test_journal_acces_liste_ok_admin(self):
        resp = auth(self.admin).get(f'{BASE}/journal-acces/')
        self.assertEqual(resp.status_code, 200)

    def test_journal_acces_par_document_refuse_au_normal(self):
        resp = auth(self.normal).get(
            f'{BASE}/documents/{self.doc.id}/journal-acces/')
        self.assertEqual(resp.status_code, 403)

    # ── GED36 — quotas : lecture ouverte, état dispo, écriture admin-only ────
    def test_quota_etat_lisible_par_tout_role(self):
        for user in (self.admin, self.normal):
            resp = auth(user).get(f'{BASE}/quotas-stockage/etat/')
            self.assertEqual(resp.status_code, 200, user.username)
            self.assertIn('usage_octets', resp.data)

    def test_quota_creation_refusee_au_normal(self):
        resp = auth(self.normal).post(
            f'{BASE}/quotas-stockage/', {'quota_octets': 1000}, format='json')
        self.assertEqual(resp.status_code, 403)

    # ── Garde-prix : aucune réponse GED n'expose un champ de prix ────────────
    def test_garde_prix_aucun_champ_prix_dans_documents(self):
        resp = auth(self.admin).get(f'{BASE}/documents/')
        self._assert_no_price(resp.data)

    def test_garde_prix_aucun_champ_prix_dans_detail(self):
        resp = auth(self.admin).get(f'{BASE}/documents/{self.doc.id}/')
        self._assert_no_price(resp.data)

    def _assert_no_price(self, data):
        import json
        blob = json.dumps(data, default=str).lower()
        for champ in CHAMPS_PRIX_INTERDITS:
            self.assertNotIn(
                f'"{champ}"', blob,
                f'Champ de prix « {champ} » exposé dans une réponse GED.')
