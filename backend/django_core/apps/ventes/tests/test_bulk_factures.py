"""Tests FG43 — opérations en masse sur les factures (bulk endpoint)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, RelanceLog

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def make_company(slug='bulk-co', nom='Bulk Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestFactureBulk(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='bulk_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bulk', prenom='Client',
            email='bulk@example.com', telephone='+212600000050')

    def _facture(self, statut=Facture.Statut.BROUILLON, with_ligne=True):
        n = _nxt()
        f = Facture.objects.create(
            company=self.company,
            reference=f'FAC-{MONTH}-B{n:04d}',
            client=self.client_obj,
            statut=statut,
            taux_tva=Decimal('20'),
        )
        if with_ligne:
            produit = Produit.objects.create(
                company=self.company, nom=f'Prod {n}', sku=f'SKU-B{n}',
                prix_vente=Decimal('1000'), prix_achat=Decimal('800'),
                quantite_stock=100)
            LigneFacture.objects.create(
                facture=f, produit=produit, designation='Test',
                quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        return f

    def _url(self):
        return '/api/django/ventes/factures/bulk/'

    # ── Validation ────────────────────────────────────────────────────────────

    def test_invalid_action_rejected(self):
        f = self._facture()
        r = self.api.post(self._url(), {'action': 'supprimer', 'ids': [f.id]},
                          format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('invalide', r.data['detail'])

    def test_empty_ids_rejected(self):
        r = self.api.post(self._url(), {'action': 'emettre', 'ids': []},
                          format='json')
        self.assertEqual(r.status_code, 400)

    def test_missing_ids_rejected(self):
        r = self.api.post(self._url(), {'action': 'emettre'}, format='json')
        self.assertEqual(r.status_code, 400)

    # ── Emettre ───────────────────────────────────────────────────────────────

    def test_bulk_emettre_brouillon(self):
        f1 = self._facture(statut=Facture.Statut.BROUILLON)
        f2 = self._facture(statut=Facture.Statut.BROUILLON)
        r = self.api.post(
            self._url(), {'action': 'emettre', 'ids': [f1.id, f2.id]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        f1.refresh_from_db()
        f2.refresh_from_db()
        self.assertEqual(f1.statut, 'emise')
        self.assertEqual(f2.statut, 'emise')
        self.assertTrue(r.data[f1.id]['ok'])
        self.assertTrue(r.data[f2.id]['ok'])

    def test_bulk_emettre_non_brouillon_skipped(self):
        """Une facture déjà émise retourne ok=False mais n'interrompt pas le batch."""
        f_emise = self._facture(statut=Facture.Statut.EMISE)
        f_new = self._facture(statut=Facture.Statut.BROUILLON)
        r = self.api.post(
            self._url(), {'action': 'emettre', 'ids': [f_emise.id, f_new.id]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data[f_emise.id]['ok'])
        self.assertTrue(r.data[f_new.id]['ok'])
        f_new.refresh_from_db()
        self.assertEqual(f_new.statut, 'emise')

    # ── Relancer ──────────────────────────────────────────────────────────────

    def test_bulk_relancer_emises(self):
        f1 = self._facture(statut=Facture.Statut.EMISE)
        f2 = self._facture(statut=Facture.Statut.EN_RETARD)
        r = self.api.post(
            self._url(), {'action': 'relancer', 'ids': [f1.id, f2.id]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data[f1.id]['ok'])
        self.assertTrue(r.data[f2.id]['ok'])
        self.assertEqual(RelanceLog.objects.filter(company=self.company).count(), 2)

    def test_bulk_relancer_brouillon_skipped(self):
        """Une facture brouillon ne peut pas être relancée."""
        f = self._facture(statut=Facture.Statut.BROUILLON)
        r = self.api.post(
            self._url(), {'action': 'relancer', 'ids': [f.id]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data[f.id]['ok'])
        self.assertEqual(RelanceLog.objects.filter(company=self.company).count(), 0)

    # ── Company scoping ───────────────────────────────────────────────────────

    def test_bulk_cross_company_invisible(self):
        """Les factures d'une autre société sont traitées comme introuvables."""
        other_co, _ = Company.objects.get_or_create(
            slug='other-bulk-co', defaults={'nom': 'Other Bulk Co'})
        other_client = Client.objects.create(
            company=other_co, nom='Other', email='other@ex.com',
            telephone='+212600000051')
        other_f = Facture.objects.create(
            company=other_co, reference=f'FAC-{MONTH}-X0001',
            client=other_client, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20'))
        r = self.api.post(
            self._url(), {'action': 'emettre', 'ids': [other_f.id]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data[other_f.id]['ok'])
        other_f.refresh_from_db()
        self.assertEqual(other_f.statut, 'brouillon')  # inchangé

    # ── generer-pdf ───────────────────────────────────────────────────────────

    def test_bulk_generer_pdf_returns_result_per_id(self):
        """generer-pdf traite chaque id et renvoie un résultat par clé (ok ou erreur).

        En test sans broker Redis, la tâche Celery lève une exception réseau :
        le batch la capture et renvoie ok=False + detail. Ce qui importe est que
        le batch renvoie 200 et un dict avec la clé de la facture demandée —
        pas d'erreur 500.
        """
        f = self._facture(statut=Facture.Statut.EMISE)
        r = self.api.post(
            self._url(), {'action': 'generer-pdf', 'ids': [f.id]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # La clé de la facture doit exister dans la réponse.
        self.assertIn(f.id, r.data)
