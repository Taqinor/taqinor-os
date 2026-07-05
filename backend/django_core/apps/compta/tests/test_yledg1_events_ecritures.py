"""Tests YLEDG1 — compta s'abonne à ``facture_emise``/``paiement_enregistre``/
``avoir_cree`` (core.events, M6) et génère l'écriture GL correspondante,
exactement une fois, quand ``COMPTA_AUTO_ECRITURES`` est actif ; toggle OFF
(défaut) → aucune écriture (comportement inchangé). ``ventes`` n'est jamais
importée par ``apps.compta`` : les instances transitent par les arguments du
signal, comme le reste de ce module."""
from decimal import Decimal

from django.test import TestCase, override_settings

from authentication.models import Company
from apps.compta.models import EcritureComptable
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Facture, LigneFacture, Paiement
from core.events import avoir_cree, facture_emise, paiement_enregistre

from apps.compta import receivers  # noqa: F401  (câblage ready())


def make_company(slug='yledg1-co', nom='YLEDG1 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L1',
            email='yledg1@example.com', telephone='+212600000021')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PAN-YLEDG1',
            prix_vente=Decimal('1000'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG1-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Panneau', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))


class TestFactureEmiseGenerateEcriture(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_signal_creates_ecriture_once(self):
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        qs = EcritureComptable.objects.filter(
            company=self.company, source_type='facture',
            source_id=self.facture.id)
        self.assertEqual(qs.count(), 1)
        # Ré-émission (best-effort, ex. re-sauvegarde) : idempotent.
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        self.assertEqual(qs.count(), 1)

    def test_signal_noop_when_toggle_off(self):
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        self.assertEqual(EcritureComptable.objects.count(), 0)


class TestPaiementEnregistreGenerateEcriture(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_signal_creates_ecriture_once(self):
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-01',
            mode=Paiement.Mode.VIREMENT, created_by=None)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)
        qs = EcritureComptable.objects.filter(
            company=self.company, source_type='paiement',
            source_id=paiement.id)
        self.assertEqual(qs.count(), 1)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)
        self.assertEqual(qs.count(), 1)

    def test_signal_noop_when_toggle_off(self):
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-01',
            mode=Paiement.Mode.VIREMENT, created_by=None)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)
        self.assertEqual(EcritureComptable.objects.count(), 0)


class TestAvoirCreeGenerateEcriture(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_signal_creates_ecriture_once(self):
        avoir = Avoir.objects.create(
            company=self.company, reference='AV-YLEDG1-0001',
            facture=self.facture, client=self.cl,
            statut=Avoir.Statut.EMISE, taux_tva=Decimal('20.00'))
        from apps.ventes.models import LigneAvoir
        LigneAvoir.objects.create(
            avoir=avoir, produit=self.produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        avoir_cree.send(sender=Avoir, instance=avoir, company=self.company)
        qs = EcritureComptable.objects.filter(
            company=self.company, source_type='avoir', source_id=avoir.id)
        self.assertEqual(qs.count(), 1)
        avoir_cree.send(sender=Avoir, instance=avoir, company=self.company)
        self.assertEqual(qs.count(), 1)

    def test_signal_noop_when_toggle_off(self):
        avoir = Avoir.objects.create(
            company=self.company, reference='AV-YLEDG1-0002',
            facture=self.facture, client=self.cl,
            statut=Avoir.Statut.EMISE, taux_tva=Decimal('20.00'))
        avoir_cree.send(sender=Avoir, instance=avoir, company=self.company)
        self.assertEqual(EcritureComptable.objects.count(), 0)
