"""
NTP2P7 — Onboarding fournisseur avec documents légaux.

CRITÈRE D'ACCEPTATION : avec le flag société activé, un fournisseur au dossier
incomplet ne peut PAS recevoir de nouveau BCF (400 explicite).

Couvre aussi : le no-op total quand le flag est OFF (défaut — le
``Fournisseur.statut`` reste ``actif`` et rien ne change), les 5 pièces
requises, la progression (NTP2P29), le refus de valider un dossier incomplet,
l'effet d'une pièce EXPIRÉE, et le scope société.

Run :
    python manage.py test apps.stock.test_ntp2p7_onboarding_fournisseur -v2
"""
import itertools
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock import selectors as stock_selectors
from apps.stock.models import (
    AchatsParametres, DocumentFournisseur, DossierOnboardingFournisseur,
    Fournisseur,
)

User = get_user_model()
_seq = itertools.count(1)
STOCK = '/api/django/stock'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p7-co-{n}', defaults={'nom': f'NTP2P7 Co {n}'})
    return company


def make_user(company, role='admin'):
    return User.objects.create_user(
        username=f'ntp2p7-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_dossier(company, fournisseur):
    return DossierOnboardingFournisseur.objects.create(
        company=company, fournisseur=fournisseur)


def poser_piece(company, dossier, type_document, *, expiration=None,
                avec_fichier=True):
    return DocumentFournisseur.objects.create(
        company=company, dossier=dossier, type_document=type_document,
        file_key=f'attachments/{company.id}/{next(_seq)}.pdf'
        if avec_fichier else '',
        filename='piece.pdf', mime='application/pdf', taille=1024,
        date_expiration=expiration)


def dossier_complet(company, dossier, *, expiration=None):
    for type_document in DocumentFournisseur.TYPES_REQUIS:
        poser_piece(company, dossier, type_document, expiration=expiration)


class OnboardingInactifTests(TestCase):
    """Non-régression : sans le flag, rien ne change."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='SolarImport')

    def test_flag_off_par_defaut(self):
        params = AchatsParametres.for_company(self.company)
        self.assertFalse(params.onboarding_fournisseur_obligatoire)
        self.assertFalse(
            stock_selectors.onboarding_fournisseur_obligatoire(self.company))

    def test_fournisseur_statut_reste_actif(self):
        """Le statut historique n'est jamais dégradé par l'onboarding."""
        make_dossier(self.company, self.fournisseur)
        self.fournisseur.refresh_from_db()
        self.assertEqual(self.fournisseur.statut, Fournisseur.Statut.ACTIF)

    def test_bcf_autorise_sans_dossier_quand_flag_off(self):
        autorise, motif = stock_selectors.fournisseur_peut_recevoir_bcf(
            self.company, self.fournisseur.pk)
        self.assertTrue(autorise)
        self.assertEqual(motif, '')

    def test_creation_bcf_passe_sans_dossier(self):
        resp = self.api.post(f'{STOCK}/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.pk,
            'date_commande': str(timezone.localdate()),
        }, format='json')
        self.assertEqual(resp.status_code, 201)


class OnboardingObligatoireTests(TestCase):
    """CRITÈRE D'ACCEPTATION — le flag activé bloque les dossiers incomplets."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='SolarImport')
        params = AchatsParametres.for_company(self.company)
        params.onboarding_fournisseur_obligatoire = True
        params.save(update_fields=['onboarding_fournisseur_obligatoire'])

    def test_sans_dossier_le_bcf_est_refuse(self):
        resp = self.api.post(f'{STOCK}/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.pk,
            'date_commande': str(timezone.localdate()),
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Onboarding', resp.data['detail'])

    def test_dossier_incomplet_le_bcf_est_refuse(self):
        dossier = make_dossier(self.company, self.fournisseur)
        poser_piece(self.company, dossier, DocumentFournisseur.Type.RC)
        resp = self.api.post(f'{STOCK}/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.pk,
            'date_commande': str(timezone.localdate()),
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Onboarding', resp.data['detail'])

    def test_dossier_valide_le_bcf_passe(self):
        dossier = make_dossier(self.company, self.fournisseur)
        dossier_complet(self.company, dossier)
        resp = self.api.post(
            f'{STOCK}/dossiers-onboarding-fournisseur/{dossier.pk}/'
            'valider-dossier/', {'valider': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'],
                         DossierOnboardingFournisseur.Statut.VALIDE)

        resp = self.api.post(f'{STOCK}/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.pk,
            'date_commande': str(timezone.localdate()),
        }, format='json')
        self.assertEqual(resp.status_code, 201)


class ProgressionEtValidationTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='SolarImport')
        self.dossier = make_dossier(self.company, self.fournisseur)

    def test_progression_deux_pieces_sur_cinq(self):
        """NTP2P29 — 2 pièces reçues sur 5 requises = 40%."""
        poser_piece(self.company, self.dossier, DocumentFournisseur.Type.RC)
        poser_piece(self.company, self.dossier,
                    DocumentFournisseur.Type.ATTESTATION_CNSS)
        detail = stock_selectors.progression_onboarding(self.dossier)
        self.assertEqual(len(detail['requis']), 5)
        self.assertEqual(len(detail['recus']), 2)
        self.assertEqual(detail['progression_pct'], 40)
        self.assertFalse(detail['complet'])

    def test_endpoint_progression(self):
        poser_piece(self.company, self.dossier, DocumentFournisseur.Type.RC)
        resp = self.api.get(
            f'{STOCK}/dossiers-onboarding-fournisseur/{self.dossier.pk}/'
            'progression/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['progression_pct'], 20)

    def test_piece_expiree_ne_compte_pas(self):
        hier = date.today() - timedelta(days=1)
        dossier_complet(self.company, self.dossier)
        piece = self.dossier.documents.first()
        piece.date_expiration = hier
        piece.save(update_fields=['date_expiration'])
        detail = stock_selectors.progression_onboarding(self.dossier)
        self.assertFalse(detail['complet'])
        self.assertIn(piece.type_document, detail['expires'])

    def test_piece_sans_fichier_ne_compte_pas(self):
        for type_document in DocumentFournisseur.TYPES_REQUIS:
            poser_piece(self.company, self.dossier, type_document,
                        avec_fichier=False)
        detail = stock_selectors.progression_onboarding(self.dossier)
        self.assertEqual(detail['progression_pct'], 0)

    def test_valider_un_dossier_incomplet_refuse(self):
        poser_piece(self.company, self.dossier, DocumentFournisseur.Type.RC)
        resp = self.api.post(
            f'{STOCK}/dossiers-onboarding-fournisseur/{self.dossier.pk}/'
            'valider-dossier/', {'valider': True}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.dossier.refresh_from_db()
        self.assertNotEqual(self.dossier.statut,
                            DossierOnboardingFournisseur.Statut.VALIDE)

    def test_rejeter_un_dossier(self):
        resp = self.api.post(
            f'{STOCK}/dossiers-onboarding-fournisseur/{self.dossier.pk}/'
            'valider-dossier/',
            {'valider': False, 'motif_rejet': 'RC illisible'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'],
                         DossierOnboardingFournisseur.Statut.REJETE)
        self.assertEqual(resp.data['motif_rejet'], 'RC illisible')

    def test_statut_non_ecrivable_directement(self):
        resp = self.api.patch(
            f'{STOCK}/dossiers-onboarding-fournisseur/{self.dossier.pk}/',
            {'statut': DossierOnboardingFournisseur.Statut.VALIDE},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut,
                         DossierOnboardingFournisseur.Statut.EN_ATTENTE)

    def test_file_key_jamais_serialise(self):
        piece = poser_piece(self.company, self.dossier,
                            DocumentFournisseur.Type.RC)
        resp = self.api.get(f'{STOCK}/documents-fournisseur/{piece.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('file_key', resp.data)

    def test_endpoint_onboarding_sur_le_fournisseur(self):
        resp = self.api.get(
            f'{STOCK}/fournisseurs/{self.fournisseur.pk}/onboarding/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['dossier'])
        self.assertFalse(resp.data['obligatoire'])

    def test_endpoint_onboarding_sans_dossier_nest_pas_404(self):
        autre = Fournisseur.objects.create(
            company=self.company, nom='SansDossier')
        resp = self.api.get(f'{STOCK}/fournisseurs/{autre.pk}/onboarding/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['dossier'])
        self.assertEqual(resp.data['progression']['progression_pct'], 0)

    def test_scope_societe(self):
        autre = make_company()
        autre_fournisseur = Fournisseur.objects.create(
            company=autre, nom='Voisin')
        make_dossier(autre, autre_fournisseur)
        resp = self.api.get(f'{STOCK}/dossiers-onboarding-fournisseur/')
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], self.dossier.pk)

    def test_fournisseur_dune_autre_societe_rejete(self):
        autre = make_company()
        autre_fournisseur = Fournisseur.objects.create(
            company=autre, nom='Voisin')
        resp = self.api.post(f'{STOCK}/dossiers-onboarding-fournisseur/',
                             {'fournisseur': autre_fournisseur.pk},
                             format='json')
        self.assertEqual(resp.status_code, 400)

    def test_company_du_corps_ignoree(self):
        autre_societe = make_company()
        nouveau = Fournisseur.objects.create(
            company=self.company, nom='Nouveau')
        resp = self.api.post(
            f'{STOCK}/dossiers-onboarding-fournisseur/',
            {'fournisseur': nouveau.pk, 'company': autre_societe.pk},
            format='json')
        self.assertEqual(resp.status_code, 201)
        dossier = DossierOnboardingFournisseur.objects.get(pk=resp.data['id'])
        self.assertEqual(dossier.company_id, self.company.id)
