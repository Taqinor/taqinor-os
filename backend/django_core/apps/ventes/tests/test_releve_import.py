"""Tests FG42 — import relevé bancaire (dry-run + commit)."""
import csv
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def make_company(slug='ri-co', nom='RI Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _make_csv(rows, headers=None):
    """Crée un CSV minimal en mémoire."""
    if headers is None:
        headers = ['date', 'reference', 'montant', 'mode']
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers, delimiter=';')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode('utf-8')


class TestReleveImport(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ri_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='RI', prenom='Client',
            email='ri@example.com', telephone='+212600000080')

    def _facture(self, ref=None, ttc=Decimal('12000'), statut='emise'):
        n = _nxt()
        ref = ref or f'FAC-{MONTH}-RI{n:04d}'
        f = Facture.objects.create(
            company=self.company, reference=ref,
            client=self.client_obj, statut=statut,
            taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'),
            montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc,
        )
        return f

    DRY_URL = '/api/django/ventes/paiements/import-releve/dry-run/'
    COMMIT_URL = '/api/django/ventes/paiements/import-releve/commit/'

    # ── Validation ────────────────────────────────────────────────────────────

    def test_no_file_returns_400(self):
        r = self.api.post(self.DRY_URL)
        self.assertEqual(r.status_code, 400)

    # ── Dry-run ───────────────────────────────────────────────────────────────

    def test_dry_run_match_by_reference(self):
        """Dry-run : ligne avec référence exacte → statut a_importer."""
        fac = self._facture(ref=f'FAC-{MONTH}-RI0099', ttc=Decimal('15000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20',
            'reference': fac.reference,
            'montant': '15000',
            'mode': 'virement',
        }])
        r = self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)},
            format='multipart')
        r.accepted_renderer = None
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['matched'], 1)
        self.assertEqual(r.data['preview'][0]['statut'], 'a_importer')
        self.assertEqual(r.data['preview'][0]['facture_reference'], fac.reference)

    def test_dry_run_no_match(self):
        """Dry-run : ligne sans facture correspondante → statut non_trouve."""
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': 'FAC-INCONNU', 'montant': '5000',
        }])
        r = self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['matched'], 0)
        self.assertEqual(r.data['preview'][0]['statut'], 'non_trouve')

    def test_dry_run_invalid_montant(self):
        """Ligne sans montant valide → statut montant_invalide."""
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': 'X', 'montant': 'abc',
        }])
        r = self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['preview'][0]['statut'], 'montant_invalide')

    def test_dry_run_exposes_columns(self):
        """Dry-run renvoie le mapping colonnes reconnues + non reconnues."""
        csv_bytes = _make_csv([{'date': '2026-06-20', 'reference': 'X',
                                 'montant': '100', 'unknown_col': 'x'}],
                              headers=['date', 'reference', 'montant', 'unknown_col'])
        r = self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('date', r.data['columns'].values())
        self.assertIn('unknown_col', r.data['unmapped'])

    def test_dry_run_no_write(self):
        """Dry-run ne crée aucun Paiement."""
        fac = self._facture(ttc=Decimal('10000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference, 'montant': '10000',
        }])
        before = Paiement.objects.filter(company=self.company).count()
        self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)}, format='multipart')
        after = Paiement.objects.filter(company=self.company).count()
        self.assertEqual(before, after)

    # ── Commit ────────────────────────────────────────────────────────────────

    def test_commit_creates_paiement(self):
        """Commit : ligne matchée → Paiement créé, facture passée payée."""
        fac = self._facture(ttc=Decimal('9000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference,
            'montant': '9000', 'mode': 'virement',
        }])
        r = self.api.post(
            self.COMMIT_URL, {'file': io.BytesIO(csv_bytes)},
            format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['created'], 1)
        self.assertEqual(r.data['skipped'], 0)
        fac.refresh_from_db()
        self.assertEqual(fac.statut, 'payee')
        p = Paiement.objects.filter(company=self.company, facture=fac).first()
        self.assertIsNotNone(p)
        self.assertEqual(p.montant, Decimal('9000'))

    def test_commit_surpaiement_skipped(self):
        """Un montant supérieur au reste dû est refusé (garde sur-paiement)."""
        fac = self._facture(ttc=Decimal('5000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference,
            'montant': '6000', 'mode': 'virement',
        }])
        r = self.api.post(
            self.COMMIT_URL, {'file': io.BytesIO(csv_bytes)},
            format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['skipped'], 1)
        self.assertEqual(Paiement.objects.filter(facture=fac).count(), 0)

    def test_commit_already_paid_skipped(self):
        """Une facture déjà payée est ignorée (statut deja_regle)."""
        fac = self._facture(ttc=Decimal('8000'), statut='payee')
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference,
            'montant': '8000',
        }])
        r = self.api.post(
            self.COMMIT_URL, {'file': io.BytesIO(csv_bytes)},
            format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['skipped'], 1)
        self.assertEqual(Paiement.objects.filter(facture=fac).count(), 0)

    def test_commit_match_by_montant_when_no_ref(self):
        """Sans référence, le match peut se faire par montant."""
        fac = self._facture(ttc=Decimal('7777'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': '',
            'montant': '7777',
        }])
        r = self.api.post(
            self.COMMIT_URL, {'file': io.BytesIO(csv_bytes)},
            format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['created'], 1)

    def test_commit_no_match_skipped(self):
        """Ligne sans facture correspondante → skipped."""
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': 'FAC-INCONNU', 'montant': '1234',
        }])
        r = self.api.post(
            self.COMMIT_URL, {'file': io.BytesIO(csv_bytes)},
            format='multipart')
        self.assertIn(r.status_code, (200, 201))
        self.assertEqual(r.data['skipped'], 1)

    def test_commit_company_scoped(self):
        """Les factures d'une autre société ne sont jamais matchées."""
        other_co, _ = Company.objects.get_or_create(
            slug='other-ri-co', defaults={'nom': 'Other RI Co'})
        other_client = Client.objects.create(
            company=other_co, nom='Other', email='other@ri.com',
            telephone='+212600000081')
        other_fac = Facture.objects.create(
            company=other_co, reference=f'FAC-{MONTH}-ORI001',
            client=other_client, statut='emise',
            taux_tva=Decimal('20'),
            montant_ht=Decimal('5000'), montant_tva=Decimal('1000'),
            montant_ttc=Decimal('6000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': other_fac.reference, 'montant': '6000',
        }])
        r = self.api.post(
            self.COMMIT_URL, {'file': io.BytesIO(csv_bytes)},
            format='multipart')
        self.assertIn(r.status_code, (200, 201))
        self.assertEqual(r.data['created'], 0)
        self.assertEqual(Paiement.objects.filter(facture=other_fac).count(), 0)
