"""Tests COMPTA2/3/9/10/11 — mapping document→compte, comptes auxiliaires
tiers, numérotation séquentielle de pièces, pièces justificatives et extourne.

Couvre :
* COMPTA2 : seed idempotent des mappings + résolution ``compte_pour_clef``.
* COMPTA3 : comptes auxiliaires clients/fournisseurs dérivés via les selectors
  crm/stock (jamais un import de leurs modèles), codes séquentiels, isolation.
* COMPTA9 : ``creer_ecriture_numerotee`` attribue une référence via references.py
  (plus-haut+1, jamais count()+1) et reste séquentielle.
* COMPTA10 : pièce justificative rattachée à une écriture, société posée serveur.
* COMPTA11 : extourne = écriture inverse équilibrée, idempotente, sans jamais
  supprimer l'écriture d'origine.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    CompteAuxiliaire, EcritureComptable, Journal, LigneEcriture,
    MappingCompte, PieceJustificative,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


# ── COMPTA2 — Mapping document → compte ────────────────────────────────────

class MappingCompteTests(TestCase):
    def setUp(self):
        self.co = make_company('map-a', 'Map A')
        services.seed_plan_comptable(self.co)

    def test_seed_mappings_idempotent(self):
        services.seed_mappings_defaut(self.co)
        n1 = MappingCompte.objects.filter(company=self.co).count()
        services.seed_mappings_defaut(self.co)
        n2 = MappingCompte.objects.filter(company=self.co).count()
        self.assertEqual(n1, n2)
        self.assertGreater(n1, 0)

    def test_seed_ne_touche_pas_un_mapping_existant(self):
        services.seed_mappings_defaut(self.co)
        m = MappingCompte.objects.get(
            company=self.co, type_clef='paiement', clef='especes')
        autre = services.get_compte(self.co, '5141')
        m.compte = autre
        m.save(update_fields=['compte'])
        services.seed_mappings_defaut(self.co)
        m.refresh_from_db()
        self.assertEqual(m.compte_id, autre.id)  # non écrasé par le seed

    def test_compte_pour_clef_resout_et_defaut(self):
        services.seed_mappings_defaut(self.co)
        c = services.compte_pour_clef(self.co, 'tva', '20')
        self.assertIsNotNone(c)
        self.assertEqual(c.numero, '4455')
        # Casse tolérée.
        self.assertIsNotNone(
            services.compte_pour_clef(self.co, 'paiement', 'ESPECES'))
        # Clef inconnue → défaut.
        sentinel = object()
        self.assertIs(
            services.compte_pour_clef(self.co, 'tva', '99', defaut=sentinel),
            sentinel)

    def test_api_seed_action(self):
        api = auth(make_user(self.co, 'map-user'))
        resp = api.post('/api/django/compta/mappings-compte/seed/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            MappingCompte.objects.filter(company=self.co).exists())


# ── COMPTA3 — Comptes auxiliaires tiers ────────────────────────────────────

class CompteAuxiliaireTests(TestCase):
    def setUp(self):
        self.co = make_company('aux-a', 'Aux A')
        self.autre = make_company('aux-b', 'Aux B')
        services.seed_plan_comptable(self.co)

    def _make_client(self, company, nom):
        from apps.crm.models import Client
        return Client.objects.create(company=company, nom=nom)

    def _make_fournisseur(self, company, nom):
        from apps.stock.models import Fournisseur
        return Fournisseur.objects.create(company=company, nom=nom)

    def test_auxiliaire_client_cree_et_idempotent(self):
        client = self._make_client(self.co, 'Client Un')
        aux1 = services.assurer_compte_auxiliaire_client(self.co, client.id)
        self.assertIsNotNone(aux1)
        self.assertEqual(aux1.type_tiers, CompteAuxiliaire.TypeTiers.CLIENT)
        self.assertEqual(aux1.compte_collectif.numero, '3421')
        self.assertTrue(aux1.code.startswith('C'))
        # Idempotent : deuxième appel = même auxiliaire.
        aux2 = services.assurer_compte_auxiliaire_client(self.co, client.id)
        self.assertEqual(aux1.id, aux2.id)
        self.assertEqual(
            CompteAuxiliaire.objects.filter(company=self.co).count(), 1)

    def test_auxiliaire_fournisseur_via_selector(self):
        f = self._make_fournisseur(self.co, 'Fourn Un')
        aux = services.assurer_compte_auxiliaire_fournisseur(self.co, f.id)
        self.assertIsNotNone(aux)
        self.assertEqual(aux.type_tiers, CompteAuxiliaire.TypeTiers.FOURNISSEUR)
        self.assertEqual(aux.compte_collectif.numero, '4411')
        self.assertTrue(aux.code.startswith('F'))

    def test_codes_sequentiels(self):
        c1 = self._make_client(self.co, 'C1')
        c2 = self._make_client(self.co, 'C2')
        a1 = services.assurer_compte_auxiliaire_client(self.co, c1.id)
        a2 = services.assurer_compte_auxiliaire_client(self.co, c2.id)
        self.assertNotEqual(a1.code, a2.code)
        self.assertEqual(a1.code, 'C0001')
        self.assertEqual(a2.code, 'C0002')

    def test_tiers_autre_societe_refuse(self):
        # Un client de l'autre société n'est pas résolu (isolation).
        client_autre = self._make_client(self.autre, 'Etranger')
        aux = services.assurer_compte_auxiliaire_client(
            self.co, client_autre.id)
        self.assertIsNone(aux)

    def test_api_assurer_action(self):
        client = self._make_client(self.co, 'API Client')
        api = auth(make_user(self.co, 'aux-user'))
        resp = api.post(
            '/api/django/compta/comptes-auxiliaires/assurer/',
            {'type_tiers': 'client', 'tiers_id': client.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['type_tiers'], 'client')

    def test_api_liste_paginee_isolation(self):
        c1 = self._make_client(self.co, 'C1')
        services.assurer_compte_auxiliaire_client(self.co, c1.id)
        api = auth(make_user(self.co, 'aux-list'))
        resp = api.get('/api/django/compta/comptes-auxiliaires/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)


# ── COMPTA9 — Numérotation séquentielle des pièces ─────────────────────────

class NumerotationPieceTests(TestCase):
    def setUp(self):
        self.co = make_company('num-a', 'Num A')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = Journal.objects.get(company=self.co, code='OD')
        self.c1 = services.get_compte(self.co, '3421')
        self.c2 = services.get_compte(self.co, '7121')

    def _lignes(self):
        return [
            {'compte': self.c1, 'debit': Decimal('100'), 'credit': Decimal('0')},
            {'compte': self.c2, 'debit': Decimal('0'), 'credit': Decimal('100')},
        ]

    def test_reference_attribuee_et_sequentielle(self):
        e1 = services.creer_ecriture_numerotee(
            self.co, self.journal, date(2026, 7, 1), 'Pièce 1', self._lignes())
        e2 = services.creer_ecriture_numerotee(
            self.co, self.journal, date(2026, 7, 1), 'Pièce 2', self._lignes())
        self.assertTrue(e1.reference)
        self.assertTrue(e2.reference)
        self.assertNotEqual(e1.reference, e2.reference)
        # Séquence croissante (plus-haut+1, jamais count()+1).
        self.assertTrue(e1.reference.endswith('0001'))
        self.assertTrue(e2.reference.endswith('0002'))
        self.assertTrue(e1.est_equilibree)


# ── COMPTA10 — Pièces justificatives ───────────────────────────────────────

class PieceJustificativeTests(TestCase):
    def setUp(self):
        self.co = make_company('pj-a', 'PJ A')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        journal = Journal.objects.get(company=self.co, code='OD')
        c1 = services.get_compte(self.co, '3421')
        c2 = services.get_compte(self.co, '7121')
        self.ecriture = services.creer_ecriture(
            self.co, journal, date(2026, 7, 1), 'Écriture pièce', [
                {'compte': c1, 'debit': Decimal('50'), 'credit': Decimal('0')},
                {'compte': c2, 'debit': Decimal('0'), 'credit': Decimal('50')},
            ])

    def test_api_ajout_piece_pose_company_et_user(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        user = make_user(self.co, 'pj-user')
        api = auth(user)
        f = SimpleUploadedFile('recu.txt', b'contenu', content_type='text/plain')
        resp = api.post(
            '/api/django/compta/pieces-justificatives/',
            {'ecriture': self.ecriture.id, 'libelle': 'Reçu', 'fichier': f},
            format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        piece = PieceJustificative.objects.get(id=resp.data['id'])
        self.assertEqual(piece.company_id, self.co.id)
        self.assertEqual(piece.ajoute_par_id, user.id)
        self.assertEqual(piece.ecriture_id, self.ecriture.id)

    def test_api_liste_filtre_par_ecriture(self):
        PieceJustificative.objects.create(
            company=self.co, ecriture=self.ecriture, libelle='P1',
            fichier='compta/pieces/x.txt')
        api = auth(make_user(self.co, 'pj-list'))
        resp = api.get(
            f'/api/django/compta/pieces-justificatives/?ecriture={self.ecriture.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)


# ── COMPTA11 — Extourne / contre-passation ─────────────────────────────────

class ExtourneTests(TestCase):
    def setUp(self):
        self.co = make_company('ext-a', 'Ext A')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = Journal.objects.get(company=self.co, code='VTE')
        self.clients = services.get_compte(self.co, '3421')
        self.ventes = services.get_compte(self.co, '7121')
        self.ecriture = services.creer_ecriture(
            self.co, self.journal, date(2026, 7, 1), 'Vente à extourner', [
                {'compte': self.clients, 'debit': Decimal('120'),
                 'credit': Decimal('0'), 'tiers_type': 'client', 'tiers_id': 7},
                {'compte': self.ventes, 'debit': Decimal('0'),
                 'credit': Decimal('120')},
            ], statut=EcritureComptable.Statut.VALIDEE)

    def test_extourne_inverse_et_equilibree(self):
        ext = services.extourner_ecriture(self.ecriture)
        self.assertIsNotNone(ext)
        self.assertTrue(ext.est_equilibree)
        self.assertEqual(ext.source_type, 'extourne')
        self.assertEqual(ext.source_id, self.ecriture.id)
        # Les débits/crédits sont permutés.
        lig_client = ext.lignes.get(compte=self.clients)
        self.assertEqual(lig_client.credit, Decimal('120'))
        self.assertEqual(lig_client.debit, Decimal('0'))
        # Le tiers est conservé.
        self.assertEqual(lig_client.tiers_id, 7)
        # L'écriture d'origine existe TOUJOURS (jamais supprimée).
        self.assertTrue(
            EcritureComptable.objects.filter(id=self.ecriture.id).exists())

    def test_extourne_idempotente(self):
        e1 = services.extourner_ecriture(self.ecriture)
        e2 = services.extourner_ecriture(self.ecriture)
        self.assertEqual(e1.id, e2.id)
        # Une seule écriture d'extourne pour l'origine.
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='extourne',
                source_id=self.ecriture.id).count(), 1)

    def test_api_extourner_action(self):
        api = auth(make_user(self.co, 'ext-user'))
        resp = api.post(
            f'/api/django/compta/ecritures/{self.ecriture.id}/extourner/',
            {'date_extourne': '2026-07-05'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['source_type'], 'extourne')
        self.assertEqual(
            LigneEcriture.objects.filter(
                ecriture_id=resp.data['id']).count(), 2)
