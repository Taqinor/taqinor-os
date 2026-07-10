"""ZFAC11 — Arrondi de caisse (cash rounding) sur factures réglées en espèces.

Réglage société ``CompanyProfile.arrondi_caisse`` (défaut 0 = OFF → comportement
actuel strictement inchangé). Quand > 0 ET mode ESPÈCES, l'écran d'encaissement
propose le reste à payer arrondi au pas et l'écart d'arrondi est tracé comme un
abandon « Arrondi espèces » (jamais silencieux). Un règlement virement l'ignore.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zfac11_arrondi_caisse -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Facture
from apps.ventes.views.facture import arrondir_au_pas

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='zfac11-co', nom='ZFAC11 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='zfac11@example.com'):
    return Client.objects.create(
        company=company, nom='Arrondi', prenom='Client',
        email=email, telephone='+212600000011', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ArrondirAuPasHelperTests(TestCase):
    """Le helper pur d'arrondi (aucune I/O)."""

    def test_pas_zero_returns_unchanged(self):
        self.assertEqual(arrondir_au_pas('10000.03', 0), Decimal('10000.03'))

    def test_arrondi_5_centimes(self):
        self.assertEqual(arrondir_au_pas('10000.03', '0.05'), Decimal('10000.05'))
        self.assertEqual(arrondir_au_pas('10000.02', '0.05'), Decimal('10000.00'))

    def test_arrondi_20_centimes(self):
        self.assertEqual(arrondir_au_pas('10000.09', '0.20'), Decimal('10000.00'))
        self.assertEqual(arrondir_au_pas('10000.11', '0.20'), Decimal('10000.20'))

    def test_arrondi_1_mad(self):
        self.assertEqual(arrondir_au_pas('10000.49', '1.00'), Decimal('10000.00'))
        self.assertEqual(arrondir_au_pas('10000.51', '1.00'), Decimal('10001.00'))


class ArrondiCaisseEncaissementTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='zfac11_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)

    def _facture(self, ttc, ref='0101'):
        # HT/TVA cohérents (TVA 20 %) mais seul le TTC pilote le reste à payer.
        ttc = Decimal(ttc)
        ht = (ttc / Decimal('1.2')).quantize(Decimal('0.01'))
        return Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-{ref}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=ht, montant_tva=ttc - ht, montant_ttc=ttc,
            created_by=self.admin,
        )

    # ── Arrondi OFF → strictement inchangé ──────────────────────────────────
    def test_arrondi_off_byte_identical(self):
        """Défaut 0 : un règlement espèces du reste EXACT solde normalement,
        aucun écart tracé, aucun abandon (comportement actuel)."""
        f = self._facture('10000.03')
        r = self.api.post(
            f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
            {'montant': '10000.03',
             'date_paiement': timezone.now().date().isoformat(),
             'mode': 'especes'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.PAYEE)
        self.assertEqual(f.montant_du, Decimal('0'))
        self.assertEqual(f.abandon_motif, '')
        self.assertFalse(f.abandon_auto)

    def test_arrondi_off_partial_cash_leaves_residual(self):
        """Arrondi OFF + règlement espèces partiel : le résiduel reste dû
        (aucun arrondi/abandon)."""
        f = self._facture('10000.03')
        r = self.api.post(
            f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
            {'montant': '10000.00',
             'date_paiement': timezone.now().date().isoformat(),
             'mode': 'especes'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.EMISE)
        self.assertEqual(f.montant_du, Decimal('0.03'))
        self.assertEqual(f.abandon_motif, '')

    # ── Arrondi 0,05 sur un règlement ESPÈCES → propose + trace l'écart ─────
    def test_proposal_endpoint_especes(self):
        profile = CompanyProfile.get(company=self.company)
        profile.arrondi_caisse = Decimal('0.05')
        profile.save(update_fields=['arrondi_caisse'])
        f = self._facture('10000.03')
        r = self.api.get(
            f'/api/django/ventes/factures/{f.id}/arrondi-caisse/'
            '?mode=especes')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['applicable'])
        self.assertEqual(Decimal(r.data['montant_arrondi']), Decimal('10000.00'))
        self.assertEqual(Decimal(r.data['ecart']), Decimal('0.03'))
        self.assertEqual(Decimal(r.data['pas']), Decimal('0.05'))

    def test_cash_payment_rounds_and_traces_ecart(self):
        """Arrondi 0,05 + règlement ESPÈCES du montant arrondi : la facture est
        soldée et l'écart (0,03) est tracé « Arrondi espèces » (jamais
        silencieux)."""
        profile = CompanyProfile.get(company=self.company)
        profile.arrondi_caisse = Decimal('0.05')
        profile.save(update_fields=['arrondi_caisse'])
        f = self._facture('10000.03')
        r = self.api.post(
            f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
            {'montant': '10000.00',
             'date_paiement': timezone.now().date().isoformat(),
             'mode': 'especes'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.PAYEE)
        self.assertEqual(f.montant_du, Decimal('0'))
        self.assertTrue(f.abandon_auto)
        self.assertEqual(f.abandon_motif, 'arrondi_caisse')
        self.assertEqual(f.abandon_montant, Decimal('0.03'))

    def test_cash_rounding_posts_balanced_entry(self):
        """L'écart d'arrondi passe l'écriture d'abandon équilibrée (6585/3421)."""
        profile = CompanyProfile.get(company=self.company)
        profile.arrondi_caisse = Decimal('0.05')
        profile.save(update_fields=['arrondi_caisse'])
        f = self._facture('10000.03')
        self.api.post(
            f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
            {'montant': '10000.00',
             'date_paiement': timezone.now().date().isoformat(),
             'mode': 'especes'}, format='json')
        from apps.compta.models import EcritureComptable, LigneEcriture
        ecriture = EcritureComptable.objects.filter(
            company=self.company).latest('id')
        lignes = LigneEcriture.objects.filter(ecriture=ecriture)
        total_debit = sum((ln.debit for ln in lignes), Decimal('0'))
        total_credit = sum((ln.credit for ln in lignes), Decimal('0'))
        self.assertEqual(total_debit, total_credit)
        self.assertEqual(total_debit, Decimal('0.03'))

    # ── Un règlement VIREMENT ignore l'arrondi ──────────────────────────────
    def test_virement_ignores_rounding(self):
        """Arrondi 0,05 activé MAIS règlement VIREMENT : aucun arrondi, aucun
        écart tracé — le résiduel reste dû (comportement inchangé hors caisse)."""
        profile = CompanyProfile.get(company=self.company)
        profile.arrondi_caisse = Decimal('0.05')
        profile.save(update_fields=['arrondi_caisse'])
        f = self._facture('10000.03')
        r = self.api.post(
            f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
            {'montant': '10000.00',
             'date_paiement': timezone.now().date().isoformat(),
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.EMISE)
        self.assertEqual(f.montant_du, Decimal('0.03'))
        self.assertEqual(f.abandon_motif, '')
        self.assertFalse(f.abandon_auto)

    def test_proposal_endpoint_virement_not_applicable(self):
        profile = CompanyProfile.get(company=self.company)
        profile.arrondi_caisse = Decimal('0.05')
        profile.save(update_fields=['arrondi_caisse'])
        f = self._facture('10000.03')
        r = self.api.get(
            f'/api/django/ventes/factures/{f.id}/arrondi-caisse/'
            '?mode=virement')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['applicable'])
        self.assertEqual(Decimal(r.data['montant_arrondi']), Decimal('10000.03'))
        self.assertEqual(Decimal(r.data['ecart']), Decimal('0'))

    def test_exact_cash_payment_with_rounding_no_ecart(self):
        """Un reste déjà pile au pas (aucun écart) : règlement espèces exact
        solde sans abandon, applicable=false."""
        profile = CompanyProfile.get(company=self.company)
        profile.arrondi_caisse = Decimal('0.05')
        profile.save(update_fields=['arrondi_caisse'])
        f = self._facture('10000.00')
        r = self.api.get(
            f'/api/django/ventes/factures/{f.id}/arrondi-caisse/'
            '?mode=especes')
        self.assertFalse(r.data['applicable'])
        r2 = self.api.post(
            f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
            {'montant': '10000.00',
             'date_paiement': timezone.now().date().isoformat(),
             'mode': 'especes'}, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.PAYEE)
        self.assertEqual(f.abandon_motif, '')
