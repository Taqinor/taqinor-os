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

    # ── ALEC18 — droit du module, PII et portée des documents produits ──────
    def _role_livre(self, nom, username):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        role = Role.objects.create(
            company=self.co, nom=f'{nom} {username}',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)[nom]))
        return User.objects.create_user(
            username=username, password='x', company=self.co, role=role)

    def test_roles_livres_module_pii_et_portee(self):
        c1 = self._role_livre('Commercial', 'alec18-c1')
        c2 = self._role_livre('Commercial', 'alec18-c2')
        terrain = self._role_livre('Commercial terrain', 'alec18-terrain')
        rh = self._role_livre('Admin RH', 'alec18-rh')
        directeur = self._role_livre('Directeur', 'alec18-dir')
        facture = Document.objects.create(
            company=self.co, folder=self.folder, nom='FAC-C1.pdf',
            created_by=c1, custom_data={'routage_reference': 'FAC-C1'})
        upload = Document.objects.create(
            company=self.co, folder=self.folder, nom='CIN.pdf',
            custom_data={'source_type': 'portail.piece', 'source_id': 1})

        def ids(user):
            resp = auth(user).get(f'{BASE}/documents/')
            self.assertEqual(resp.status_code, 200, user.username)
            data = resp.data
            rows = data['results'] if isinstance(data, dict) else data
            return {row['id'] for row in rows}

        for path in ('documents/', f'documents/{self.doc.pk}/', 'versions/'):
            with self.subTest(path=path):
                self.assertEqual(
                    auth(terrain).get(f'{BASE}/{path}').status_code, 403)
        self.assertEqual(ids(rh), {self.doc.pk})
        self.assertEqual(ids(c2), {self.doc.pk})
        self.assertEqual(ids(c1), {self.doc.pk, facture.pk})
        self.assertEqual(
            ids(directeur), {self.doc.pk, facture.pk, upload.pk})
        for doc in (facture, upload):
            self.assertEqual(auth(c2).get(
                f'{BASE}/documents/{doc.pk}/').status_code, 404)

    # ── ALEC42/ALEC43 — demandes de signature et leurs destinataires ────────
    def _demande_deux_signataires(self):
        from django.utils import timezone
        from apps.ged.models import DemandeSignatureDocument, SignataireDemande
        demande = DemandeSignatureDocument.objects.create(
            company=self.co, document=self.doc, signataire_nom='Sara',
            signataire_email='sara@client.ma', adresse_ip='10.0.0.7',
            user_agent='Navigateur S')
        SignataireDemande.objects.create(
            company=self.co, demande=demande, nom='Sara', ordre=1,
            email='sara@client.ma', telephone='0600000001',
            statut='signe',
            date_action=timezone.now(), adresse_ip='10.0.0.7',
            user_agent='Navigateur S')
        SignataireDemande.objects.create(
            company=self.co, demande=demande, nom='Omar', ordre=2,
            email='omar@client.ma', telephone='0600000002')
        return demande

    def test_signatures_reservees_au_module(self):
        terrain = self._role_livre('Commercial terrain', 'alec42-terrain')
        commercial = self._role_livre('Commercial', 'alec42-c')
        directeur = self._role_livre('Directeur', 'alec42-dir')
        demande = self._demande_deux_signataires()
        routes = (
            'demandes-signature/', f'demandes-signature/{demande.pk}/',
            f'demandes-signature/{demande.pk}/pdf-signe/',
            f'signataires-demande/?demande={demande.pk}')
        for path in routes:
            with self.subTest(path=path):
                self.assertEqual(
                    auth(terrain).get(f'{BASE}/{path}').status_code, 403)
                for user in (commercial, directeur):
                    self.assertNotEqual(
                        auth(user).get(f'{BASE}/{path}').status_code, 403)
        for user in (commercial, directeur):
            resp = auth(user).get(f'{BASE}/demandes-signature/')
            self.assertEqual(resp.status_code, 200, user.username)
            rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
            self.assertEqual([r['id'] for r in rows], [demande.pk])
            self.assertEqual(auth(user).get(
                f'{BASE}/demandes-signature/{demande.pk}/').status_code, 200)

    def test_coordonnees_signataires_sans_client_pii(self):
        from apps.ged.models import SignataireDemande
        rh = self._role_livre('Admin RH', 'alec43-rh')
        commercial = self._role_livre('Commercial', 'alec43-c')
        directeur = self._role_livre('Directeur', 'alec43-dir')
        demande = self._demande_deux_signataires()
        coord = ('email', 'telephone', 'adresse_ip', 'user_agent')
        coord_demande = ('signataire_email', 'adresse_ip', 'user_agent')

        def lire(user):
            detail = auth(user).get(f'{BASE}/demandes-signature/{demande.pk}/')
            dests = auth(user).get(f'{BASE}/signataires-demande/?demande={demande.pk}')
            self.assertEqual((detail.status_code, dests.status_code), (200, 200))
            rows = dests.data['results'] if isinstance(dests.data, dict) else dests.data
            return detail.data, list(rows) + list(detail.data['signataires'])

        detail, dests = lire(rh)
        self.assertEqual(len(dests), 4)
        for d in dests:
            self.assertTrue(d['nom'] and d['statut'])
            self.assertEqual({c: d[c] for c in coord}, dict.fromkeys(coord))
        self.assertEqual(
            {c: detail[c] for c in coord_demande}, dict.fromkeys(coord_demande))
        for user in (commercial, directeur):
            detail, dests = lire(user)
            self.assertEqual(detail['signataire_email'], 'sara@client.ma')
            self.assertEqual(detail['adresse_ip'], '10.0.0.7')
            sara = [d for d in dests if d['nom'] == 'Sara']
            self.assertTrue(sara and all(
                d['email'] == 'sara@client.ma' and d['telephone'] == '0600000001'
                and d['adresse_ip'] == '10.0.0.7' for d in sara))
        # Rendu seulement : la base garde les coordonnées.
        self.assertEqual(SignataireDemande.objects.filter(
            demande=demande, email__endswith='@client.ma').count(), 2)
