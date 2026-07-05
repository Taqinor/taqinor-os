"""ZSTK11 — Réglage société : méthode de réservation du stock (Odoo
"Reservation methods": à la confirmation / manuelle).

`StockReservation` (N14) était semée par un chemin fixe à la création du
chantier. Couvre :

  * en mode `confirmation` (défaut), le stock se réserve COMME AUJOURD'HUI à
    la création du chantier (non-régression byte-identique) ;
  * en mode `manuelle`, la création NE sème PAS la réservation
    automatiquement ;
  * en mode `manuelle`, le bouton « Réserver le stock » explicite
    (`reserver-stock`) sème la réservation (même service, aucune logique
    dupliquée) ;
  * scoping société du réglage.

Run :
    python manage.py test \
        apps.installations.tests_zstk11_methode_reservation_stock -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit
from apps.installations.models import StockReservation
from apps.installations.services import create_installation_from_devis
from apps.parametres.models import CompanyProfile

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'zstk11-co-{n}', defaults={'nom': f'ZSTK11 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'zstk11-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=f'Panneau ZSTK11-{n}',
        prix_achat=Decimal('70'), prix_vente=Decimal('100'),
        quantite_stock=100)


def make_devis_avec_ligne(company, produit, qte=4):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='ZSTK11',
        email=f'zstk11-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-ZSTK11-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation=produit.nom,
        quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
    return devis


class TestMethodeReservationConfirmation(TestCase):
    """Défaut 'confirmation' — non-régression byte-identique."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.produit = make_produit(self.company)

    def test_creation_chantier_seme_reservation_par_defaut(self):
        devis = make_devis_avec_ligne(self.company, self.produit)
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        self.assertTrue(
            StockReservation.objects.filter(installation=inst).exists())


class TestMethodeReservationManuelle(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        profil = CompanyProfile.get(self.company)
        profil.methode_reservation_stock = (
            CompanyProfile.MethodeReservationStock.MANUELLE)
        profil.save(update_fields=['methode_reservation_stock'])

    def test_creation_chantier_ne_seme_pas_automatiquement(self):
        devis = make_devis_avec_ligne(self.company, self.produit)
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        self.assertFalse(
            StockReservation.objects.filter(installation=inst).exists())

    def test_bouton_reserver_stock_seme_la_reservation(self):
        devis = make_devis_avec_ligne(self.company, self.produit)
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        self.assertFalse(
            StockReservation.objects.filter(installation=inst).exists())

        r = self.api.post(
            f'{BASE}/chantiers/{inst.id}/reserver-stock/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['reservations_actives'], 1)
        self.assertTrue(
            StockReservation.objects.filter(installation=inst).exists())


class TestScopingSociete(TestCase):
    def test_reglage_scope_par_societe(self):
        company_a = make_company()
        company_b = make_company()
        profil_a = CompanyProfile.get(company_a)
        profil_a.methode_reservation_stock = (
            CompanyProfile.MethodeReservationStock.MANUELLE)
        profil_a.save(update_fields=['methode_reservation_stock'])

        user_b = make_user(company_b)
        produit_b = make_produit(company_b)
        devis_b = make_devis_avec_ligne(company_b, produit_b)
        inst_b, _ = create_installation_from_devis(devis_b, user_b, company_b)
        # Société B n'a jamais touché au réglage -> comportement historique.
        self.assertTrue(
            StockReservation.objects.filter(installation=inst_b).exists())
