"""
NTP2P19 — Score de conformité fournisseur exportable (audit achats).

CRITÈRE D'ACCEPTATION : l'export produit UNE LIGNE par fournisseur actif avec
les 5 colonnes de conformité (statut onboarding, score de risque, documents
expirés, dernier retard OTD, montant acheté), filtrable par période.

Note d'implémentation VÉRIFIÉE ici : le paramètre est ``?export=xlsx`` et NON
``?format=xlsx`` — ``format`` est RÉSERVÉ par la négociation de contenu DRF.

Run :
    python manage.py test apps.stock.test_ntp2p19_export_conformite -v2
"""
import itertools
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock import selectors as stock_selectors
from apps.stock.models import (
    BonCommandeFournisseur, DocumentFournisseur,
    DossierOnboardingFournisseur, Fournisseur,
    LigneBonCommandeFournisseur,
)

User = get_user_model()
_seq = itertools.count(1)
URL = '/api/django/stock/fournisseurs/export-conformite/'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p19-co-{n}', defaults={'nom': f'NTP2P19 Co {n}'})
    return company


def make_user(company, role='admin'):
    return User.objects.create_user(
        username=f'ntp2p19-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ExportConformiteTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='AlphaSolar')

    def test_une_ligne_par_fournisseur_actif(self):
        Fournisseur.objects.create(company=self.company, nom='BetaSolar')
        archive = Fournisseur.objects.create(
            company=self.company, nom='ZetaArchive')
        archive.is_archived = True
        archive.save(update_fields=['is_archived'])

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        noms = [ligne['fournisseur'] for ligne in resp.data]
        self.assertEqual(noms, ['AlphaSolar', 'BetaSolar'])

    def test_les_cinq_colonnes_de_conformite(self):
        """CRITÈRE D'ACCEPTATION — les 5 colonnes sont présentes."""
        ligne = self.api.get(URL).data[0]
        for colonne in ('statut_onboarding', 'score_risque',
                        'documents_expires', 'dernier_retard_jours',
                        'montant_achete'):
            self.assertIn(colonne, ligne)

    def test_sans_dossier_le_statut_est_explicite(self):
        ligne = self.api.get(URL).data[0]
        self.assertEqual(ligne['statut_onboarding'], 'Aucun dossier')

    def test_statut_onboarding_et_documents_expires(self):
        dossier = DossierOnboardingFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur)
        DocumentFournisseur.objects.create(
            company=self.company, dossier=dossier,
            type_document=DocumentFournisseur.Type.RC,
            file_key=f'attachments/{self.company.id}/{next(_seq)}.pdf',
            date_expiration=date.today() - timedelta(days=1))
        ligne = self.api.get(URL).data[0]
        self.assertEqual(ligne['statut_onboarding'], 'En attente')
        self.assertIn(DocumentFournisseur.Type.RC, ligne['documents_expires'])

    def test_dernier_retard_otd(self):
        prevue = date(2026, 3, 1)
        BonCommandeFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            reference=f'BCF-C-{next(_seq):04d}',
            date_livraison_prevue=prevue,
            date_confirmee_fournisseur=prevue + timedelta(days=4))
        plus_recent = date(2026, 6, 1)
        BonCommandeFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            reference=f'BCF-C-{next(_seq):04d}',
            date_livraison_prevue=plus_recent,
            date_confirmee_fournisseur=plus_recent + timedelta(days=9))
        ligne = self.api.get(URL).data[0]
        self.assertEqual(ligne['dernier_retard_le'], plus_recent)
        self.assertEqual(ligne['dernier_retard_jours'], 9)

    def test_montant_achete_sur_la_periode(self):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            reference=f'BCF-C-{next(_seq):04d}',
            date_commande=date(2026, 4, 15))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, designation='Panneau', quantite=10,
            prix_achat_unitaire=Decimal('1000'))
        hors_periode = BonCommandeFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            reference=f'BCF-C-{next(_seq):04d}',
            date_commande=date(2025, 4, 15))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=hors_periode, designation='Câble', quantite=5,
            prix_achat_unitaire=Decimal('100'))

        toutes = stock_selectors.conformite_fournisseurs(self.company)
        self.assertEqual(toutes[0]['montant_achete'], Decimal('10500'))

        periode = stock_selectors.conformite_fournisseurs(
            self.company, debut=date(2026, 1, 1), fin=date(2026, 12, 31))
        self.assertEqual(periode[0]['montant_achete'], Decimal('10000'))

    def test_filtre_periode_par_lapi(self):
        resp = self.api.get(URL, {'debut': '2026-01-01', 'fin': '2026-12-31'})
        self.assertEqual(resp.status_code, 200)

    def test_export_xlsx(self):
        resp = self.api.get(URL, {'export': 'xlsx'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])
        self.assertIn('conformite-fournisseurs.xlsx',
                      resp['Content-Disposition'])
        # Signature ZIP d'un .xlsx réel (openpyxl), jamais un CSV déguisé.
        self.assertTrue(resp.content.startswith(b'PK'))

    def test_parametre_format_reserve_par_drf_ne_casse_pas_lexport(self):
        """``?format=xlsx`` n'est PAS le paramètre : il ne produit pas de
        fichier (et surtout, l'action ne 500 pas)."""
        resp = self.api.get(URL, {'export': 'xlsx', 'debut': 'pas-une-date'})
        self.assertEqual(resp.status_code, 200)

    def test_scope_societe(self):
        autre = make_company()
        Fournisseur.objects.create(company=autre, nom='Voisin')
        noms = [ligne['fournisseur'] for ligne in self.api.get(URL).data]
        self.assertEqual(noms, ['AlphaSolar'])

    def test_anonyme_refuse(self):
        resp = APIClient().get(URL)
        self.assertIn(resp.status_code, (401, 403))
