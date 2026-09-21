"""NTLOG14 — DossierExport / PieceDossierExport.

Couvre :
  * création via l'API : ``numero`` (`EXP-`) + société + ``created_by`` posés
    CÔTÉ SERVEUR (jamais ``count()+1``) ; l'injection de ``company``/``numero``
    dans le corps de la requête est ignorée ;
  * ``services.creer_dossier_export_depuis_facture`` : le dossier créé porte
    le ``pays_destinataire`` donné à l'appel et reste lié à la facture ;
  * isolation société : un dossier/pièce d'une autre société n'apparaît
    jamais dans les listes, et créer une pièce sur un dossier étranger est
    refusé ;
  * la checklist de pièces (``pieces``) nested dans la réponse dossier.

Run :
    python manage.py test apps.douane.tests.test_ntlog14_dossier_export -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.douane.models import DossierExport, PieceDossierExport
from apps.douane.services import creer_dossier_export_depuis_facture

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/douane'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntlog14-co-{n}', defaults={'nom': nom or f'NTLOG14 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'ntlog14-{next(_seq)}', password='x',
        role_legacy=role, company=company)


class TestDossierExportCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_create_pose_numero_et_company_cote_serveur(self):
        r = self.api.post(f'{BASE}/dossiers-export/', {
            'incoterm': 'fob', 'pays_destinataire': 'France',
            'port_embarquement': 'Casablanca',
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        dossier = DossierExport.objects.get(pk=r.data['id'])
        self.assertEqual(dossier.company_id, self.company.id)
        self.assertEqual(dossier.created_by_id, self.user.id)
        self.assertTrue(dossier.numero.startswith('EXP-'))

    def test_injection_company_et_numero_ignoree(self):
        autre = make_company()
        r = self.api.post(f'{BASE}/dossiers-export/', {
            'company': autre.id, 'numero': 'FORGE-0001',
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        dossier = DossierExport.objects.get(pk=r.data['id'])
        self.assertEqual(dossier.company_id, self.company.id)
        self.assertNotEqual(dossier.numero, 'FORGE-0001')

    def test_numero_incremental_par_societe(self):
        r1 = self.api.post(f'{BASE}/dossiers-export/', {})
        r2 = self.api.post(f'{BASE}/dossiers-export/', {})
        n1 = DossierExport.objects.get(pk=r1.data['id']).numero
        n2 = DossierExport.objects.get(pk=r2.data['id']).numero
        self.assertNotEqual(n1, n2)
        self.assertTrue(n2.endswith('-0002'), n2)

    def test_filtre_statut(self):
        # `numero` explicite pour chaque dossier — unique_together
        # (company, numero) collision garantie si les deux gardent le défaut
        # vide '' sur la même société.
        d1 = DossierExport.objects.create(
            company=self.company, numero='EXP-TEST-1',
            statut=DossierExport.Statut.A_PREPARER)
        d2 = DossierExport.objects.create(
            company=self.company, numero='EXP-TEST-2',
            statut=DossierExport.Statut.CLOTURE)
        r = self.api.get(f'{BASE}/dossiers-export/?statut=cloture')
        ids = {row['id'] for row in r.data['results']} if 'results' in r.data else {
            row['id'] for row in r.data}
        self.assertIn(d2.id, ids)
        self.assertNotIn(d1.id, ids)


class TestCreerDepuisFacture(TestCase):
    """NTLOG14 — critère d'acceptation : un dossier export se crée depuis une
    Facture et hérite du pays destinataire."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)

    def _make_facture(self):
        from apps.crm.models import Client
        from apps.facturation.models import Facture
        client = Client.objects.create(company=self.company, nom='Client Étranger SARL')
        return Facture.objects.create(
            company=self.company, reference='FAC-TEST-0001', client=client)

    def test_dossier_herite_pays_et_lien_facture(self):
        facture = self._make_facture()
        dossier = creer_dossier_export_depuis_facture(
            company=self.company, facture=facture, pays_destinataire='Sénégal',
            incoterm='cif', created_by=self.user)
        self.assertEqual(dossier.pays_destinataire, 'Sénégal')
        self.assertEqual(dossier.facture_id, facture.id)
        self.assertTrue(dossier.numero.startswith('EXP-'))

    def test_numero_idempotent(self):
        facture = self._make_facture()
        dossier = creer_dossier_export_depuis_facture(
            company=self.company, facture=facture, pays_destinataire='Tunisie')
        numero_avant = dossier.numero
        from apps.douane.services import attribuer_numero_dossier_export
        attribuer_numero_dossier_export(dossier)
        self.assertEqual(dossier.numero, numero_avant)


class TestPieceDossierExport(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.dossier = DossierExport.objects.create(
            company=self.company, numero='EXP-TEST-DOSSIER')

    def test_creer_piece_et_liste_nested_sur_dossier(self):
        r = self.api.post(f'{BASE}/dossiers-export-pieces/', {
            'dossier': self.dossier.id, 'type_piece': 'packing_list',
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        piece = PieceDossierExport.objects.get(pk=r.data['id'])
        self.assertEqual(piece.company_id, self.company.id)
        self.assertEqual(piece.statut_piece, PieceDossierExport.StatutPiece.MANQUANTE)

        detail = self.api.get(f'{BASE}/dossiers-export/{self.dossier.id}/')
        types = [p['type_piece'] for p in detail.data['pieces']]
        self.assertIn('packing_list', types)

    def test_filtre_par_dossier(self):
        autre_dossier = DossierExport.objects.create(
            company=self.company, numero='EXP-TEST-AUTRE')
        PieceDossierExport.objects.create(
            company=self.company, dossier=self.dossier, type_piece='eur1')
        PieceDossierExport.objects.create(
            company=self.company, dossier=autre_dossier, type_piece='eur1')
        r = self.api.get(f'{BASE}/dossiers-export-pieces/?dossier={self.dossier.id}')
        rows = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['dossier'], self.dossier.id)


class TestIsolationSociete(TestCase):
    """Chaque test crée sa propre Company et vérifie l'isolation tenant."""

    def setUp(self):
        self.company_a = make_company()
        self.company_b = make_company()
        self.user_a = make_user(self.company_a)
        self.api_a = auth(self.user_a)

    def test_dossier_autre_societe_invisible(self):
        etranger = DossierExport.objects.create(company=self.company_b)
        r = self.api_a.get(f'{BASE}/dossiers-export/')
        rows = r.data['results'] if 'results' in r.data else r.data
        ids = {row['id'] for row in rows}
        self.assertNotIn(etranger.id, ids)

    def test_creer_piece_sur_dossier_etranger_refuse(self):
        dossier_b = DossierExport.objects.create(company=self.company_b)
        r = self.api_a.post(f'{BASE}/dossiers-export-pieces/', {
            'dossier': dossier_b.id, 'type_piece': 'eur1',
        })
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, r.data)
        self.assertEqual(PieceDossierExport.objects.filter(dossier=dossier_b).count(), 0)

    def test_lier_facture_etrangere_refuse(self):
        from apps.crm.models import Client
        from apps.facturation.models import Facture
        client_b = Client.objects.create(company=self.company_b, nom='Client B')
        facture_b = Facture.objects.create(
            company=self.company_b, reference='FAC-B-0001', client=client_b)
        r = self.api_a.post(f'{BASE}/dossiers-export/', {'facture': facture_b.id})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, r.data)
        self.assertEqual(DossierExport.objects.filter(facture=facture_b).count(), 0)
