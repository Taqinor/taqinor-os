"""Tests YLEDG11 — une facture d'acompte comptabilise 3421/4421 (zéro
produit) au lieu de 3421/71xx ; la facture de solde/complete du même devis
apure le cumul des acomptes déjà comptabilisés (4421 → 3421) en plus de son
propre produit ; une facture complete sans acompte au devis est inchangée
(apurement = 0)."""
from decimal import Decimal

from django.test import TestCase, override_settings

from authentication.models import Company
from apps.compta.models import EcritureComptable, LigneEcriture
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture, LigneFacture
from core.events import facture_emise

from apps.compta import receivers  # noqa: F401  (câblage ready())


def make_company(slug='yledg11-co', nom='YLEDG11 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L11',
            email='yledg11@example.com', telephone='+212600000111')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YLEDG11',
            prix_vente=Decimal('10000'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-YLEDG11-0001',
            client=self.cl, statut=Devis.Statut.ACCEPTE)


class TestFactureAcompteAvance(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_acompte_credite_4421_pas_71xx(self):
        acompte = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG11-A',
            client=self.cl, devis=self.devis, statut=Facture.Statut.EMISE,
            type_facture=Facture.TypeFacture.ACOMPTE,
            pourcentage=Decimal('30'),
            montant_ht=Decimal('3000'), montant_tva=Decimal('600'),
            montant_ttc=Decimal('3600'), taux_tva=Decimal('20.00'))
        facture_emise.send(
            sender=Facture, instance=acompte, company=self.company)

        ecriture = EcritureComptable.objects.get(
            company=self.company, source_type='facture', source_id=acompte.id)
        comptes = {ln.compte.numero for ln in ecriture.lignes.all()}
        self.assertIn('4421', comptes)
        self.assertNotIn('7121', comptes)
        ligne_4421 = ecriture.lignes.get(compte__numero='4421')
        self.assertEqual(ligne_4421.credit, Decimal('3600'))
        ligne_3421 = ecriture.lignes.get(compte__numero='3421')
        self.assertEqual(ligne_3421.debit, Decimal('3600'))


class TestFactureSoldeApureAcompte(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_solde_apure_cumul_acomptes(self):
        acompte = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG11-B1',
            client=self.cl, devis=self.devis, statut=Facture.Statut.EMISE,
            type_facture=Facture.TypeFacture.ACOMPTE,
            montant_ht=Decimal('3000'), montant_tva=Decimal('600'),
            montant_ttc=Decimal('3600'), taux_tva=Decimal('20.00'))
        facture_emise.send(
            sender=Facture, instance=acompte, company=self.company)

        solde = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG11-B2',
            client=self.cl, devis=self.devis, statut=Facture.Statut.EMISE,
            type_facture=Facture.TypeFacture.SOLDE, taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=solde, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20.00'))
        facture_emise.send(
            sender=Facture, instance=solde, company=self.company)

        ecriture_solde = EcritureComptable.objects.get(
            company=self.company, source_type='facture', source_id=solde.id)
        # Produit total constaté en entier sur le solde.
        ligne_ventes = ecriture_solde.lignes.get(compte__numero='7121')
        self.assertEqual(ligne_ventes.credit, Decimal('10000'))
        # Apurement de l'acompte : 4421 débité du cumul (3600).
        ligne_4421 = ecriture_solde.lignes.get(compte__numero='4421')
        self.assertEqual(ligne_4421.debit, Decimal('3600'))

        # Solde du dossier sur 4421 = 0 (crédit acompte − débit apurement).
        total_4421 = LigneEcriture.objects.filter(
            company=self.company, compte__numero='4421')
        solde_4421 = sum(
            ln.debit - ln.credit for ln in total_4421)
        self.assertEqual(solde_4421, Decimal('0'))

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_complete_sans_acompte_inchangee(self):
        complete = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG11-C',
            client=self.cl, devis=self.devis, statut=Facture.Statut.EMISE,
            type_facture=Facture.TypeFacture.COMPLETE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=complete, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20.00'))
        facture_emise.send(
            sender=Facture, instance=complete, company=self.company)

        ecriture = EcritureComptable.objects.get(
            company=self.company, source_type='facture',
            source_id=complete.id)
        comptes = {ln.compte.numero for ln in ecriture.lignes.all()}
        self.assertNotIn('4421', comptes)
        ligne_ventes = ecriture.lignes.get(compte__numero='7121')
        self.assertEqual(ligne_ventes.credit, Decimal('10000'))
