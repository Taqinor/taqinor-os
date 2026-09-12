"""
NTP2P30 — Wizard de clôture de fin de mois achats.

CRITÈRE D'ACCEPTATION : le wizard affiche les 3 listes du mois en cours en
un seul écran avec compteurs (``stock.selectors.checklist_cloture_achats``,
purement agrégateur en lecture, aucune nouvelle donnée, aucune mutation).

Run :
    python manage.py test \
        apps.stock.test_ntp2p30_checklist_cloture_achats -v2
"""
import itertools
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeAchat, DemandeAchatLigne
from apps.stock import selectors as stock_selectors
from apps.stock.models import (
    BonCommandeFournisseur, DocumentFournisseur, DossierOnboardingFournisseur,
    FactureFournisseur, Fournisseur,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/stock'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p30-co-{n}', defaults={'nom': f'NTP2P30 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p30-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ChecklistClotureAchatsTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTP2P30')

    def test_vide_sans_donnees(self):
        result = stock_selectors.checklist_cloture_achats(
            self.company, date(2026, 9, 1))
        self.assertEqual(result['nb_factures_en_exception'], 0)
        self.assertEqual(result['nb_demandes_en_attente_anciennes'], 0)
        self.assertEqual(result['nb_documents_expires'], 0)

    def test_facture_en_exception_du_mois_comptee(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTP2P30',
            fournisseur=self.fournisseur)
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-NTP2P30-1',
            fournisseur=self.fournisseur, bon_commande=bc,
            date_facture=date(2026, 9, 15),
            statut_controle=FactureFournisseur.StatutControle.EXCEPTION,
            montant_ttc=Decimal('1000'))
        # Une facture RÉSOLUE n'est jamais comptée (factures_en_exception).
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-NTP2P30-2',
            fournisseur=self.fournisseur, bon_commande=bc,
            date_facture=date(2026, 9, 20),
            statut_controle=FactureFournisseur.StatutControle.RESOLUE,
            montant_ttc=Decimal('500'))
        # Une exception d'un AUTRE mois n'est pas comptée.
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-NTP2P30-3',
            fournisseur=self.fournisseur, bon_commande=bc,
            date_facture=date(2026, 8, 15),
            statut_controle=FactureFournisseur.StatutControle.EXCEPTION,
            montant_ttc=Decimal('700'))

        result = stock_selectors.checklist_cloture_achats(
            self.company, date(2026, 9, 1))
        self.assertEqual(result['nb_factures_en_exception'], 1)
        self.assertEqual(
            result['factures_en_exception'][0]['reference'], 'FF-NTP2P30-1')

    def test_demande_ancienne_comptee(self):
        da = DemandeAchat.objects.create(
            company=self.company, reference='DA-NTP2P30-1',
            objet='Réquisition ancienne', created_by=self.user,
            statut=DemandeAchat.Statut.SOUMISE)
        DemandeAchatLigne.objects.create(
            demande=da, designation='Article', quantite=1, prix_estime=500)
        vieux = timezone.now() - timedelta(days=20)
        DemandeAchat.objects.filter(pk=da.pk).update(updated_at=vieux)

        # Une demande RÉCENTE n'est pas comptée (seuil par défaut 15 jours).
        da_recente = DemandeAchat.objects.create(
            company=self.company, reference='DA-NTP2P30-2',
            objet='Réquisition récente', created_by=self.user,
            statut=DemandeAchat.Statut.SOUMISE)
        DemandeAchatLigne.objects.create(
            demande=da_recente, designation='Article', quantite=1,
            prix_estime=500)

        result = stock_selectors.checklist_cloture_achats(self.company)
        self.assertEqual(result['nb_demandes_en_attente_anciennes'], 1)
        self.assertEqual(
            result['demandes_en_attente_anciennes'][0]['reference'],
            'DA-NTP2P30-1')

    def test_document_expire_compte(self):
        dossier = DossierOnboardingFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur)
        DocumentFournisseur.objects.create(
            company=self.company, dossier=dossier,
            type_document=DocumentFournisseur.Type.RC,
            file_key='x', date_expiration=timezone.localdate() - timedelta(days=5))
        DocumentFournisseur.objects.create(
            company=self.company, dossier=dossier,
            type_document=DocumentFournisseur.Type.RIB_CERTIFIE,
            file_key='y', date_expiration=timezone.localdate() + timedelta(days=60))

        result = stock_selectors.checklist_cloture_achats(self.company)
        self.assertEqual(result['nb_documents_expires'], 1)

    def test_endpoint_api_renvoie_les_trois_compteurs(self):
        resp = self.api.get(f'{BASE}/achats-parametres/checklist-cloture/')
        self.assertEqual(resp.status_code, 200)
        for key in ('nb_factures_en_exception',
                    'nb_demandes_en_attente_anciennes',
                    'nb_documents_expires'):
            self.assertIn(key, resp.json())

    def test_seuil_jours_configurable_a_l_appel(self):
        da = DemandeAchat.objects.create(
            company=self.company, reference='DA-NTP2P30-3',
            objet='Réquisition 5 jours', created_by=self.user,
            statut=DemandeAchat.Statut.SOUMISE)
        DemandeAchatLigne.objects.create(
            demande=da, designation='Article', quantite=1, prix_estime=500)
        DemandeAchat.objects.filter(pk=da.pk).update(
            updated_at=timezone.now() - timedelta(days=6))

        # Seuil par défaut (15 j) : pas encore ancienne.
        result_defaut = stock_selectors.checklist_cloture_achats(self.company)
        self.assertEqual(result_defaut['nb_demandes_en_attente_anciennes'], 0)

        # Seuil resserré à 5 j : maintenant comptée.
        result_serre = stock_selectors.checklist_cloture_achats(
            self.company, seuil_jours=5)
        self.assertEqual(result_serre['nb_demandes_en_attente_anciennes'], 1)
