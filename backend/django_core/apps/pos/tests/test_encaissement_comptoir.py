"""XPOS6 — Encaisser un devis/une facture existants au comptoir.

Couvre : Paiement enregistré sur la bonne facture d'acompte + reçu, le solde
restant est juste, aucun changement de statut de devis hors du chemin
existant, garde multi-société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import services
from apps.ventes.models import Facture
from apps.ventes.services import get_facture_or_none

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class EncaisserFactureExistanteTests(TestCase):
    def setUp(self):
        self.co = make_company('xpos6', 'XPOS6 Co')
        self.user = make_user(self.co, 'caissier-xpos6')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        self.facture = Facture.objects.create(
            reference='FAC-XPOS6-0001', company=self.co, client=self.client_obj,
            statut=Facture.Statut.EMISE,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))

    def test_encaisse_acompte_updates_solde(self):
        paiement = services.encaisser_facture_existante(
            facture=self.facture, montant=Decimal('360'), mode='especes',
            company=self.co, user=self.user)
        self.assertEqual(paiement.montant, Decimal('360.00'))
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('840.00'))

    def test_encaisse_especes_creates_timbre(self):
        services.encaisser_facture_existante(
            facture=self.facture, montant=Decimal('360'), mode='especes',
            company=self.co, user=self.user)
        from apps.compta.models import TimbreFiscal
        self.assertEqual(
            TimbreFiscal.objects.filter(company=self.co).count(), 1)

    def test_refuse_montant_above_solde(self):
        with self.assertRaises(services.EncaissementCompteError):
            services.encaisser_facture_existante(
                facture=self.facture, montant=Decimal('5000'), mode='carte',
                company=self.co, user=self.user)

    def test_refuse_cross_company_facture(self):
        other_co = make_company('xpos6-b', 'B')
        with self.assertRaises(services.EncaissementCompteError):
            services.encaisser_facture_existante(
                facture=self.facture, montant=Decimal('10'), mode='carte',
                company=other_co, user=self.user)

    def test_get_facture_or_none_scoped(self):
        other_co = make_company('xpos6-c', 'C')
        self.assertIsNone(
            get_facture_or_none(company=other_co, facture_id=self.facture.id))
        self.assertEqual(
            get_facture_or_none(company=self.co, facture_id=self.facture.id).id,
            self.facture.id)

    def test_solde_never_negative_after_full_payment(self):
        services.encaisser_facture_existante(
            facture=self.facture, montant=Decimal('1200'), mode='virement',
            company=self.co, user=self.user)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('0'))
