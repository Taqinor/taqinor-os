"""Tests YLEDG4 — annuler un document déjà comptabilisé poste son extourne
automatiquement (exactement une fois), jamais de suppression d'écriture
validée (COMPTA11) ; un document jamais comptabilisé n'extourne rien."""
from decimal import Decimal

from django.test import TestCase, override_settings

from authentication.models import Company
from apps.compta.models import EcritureComptable
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture
from core.events import facture_annulee, facture_emise

from apps.compta import receivers  # noqa: F401  (câblage ready())


def make_company(slug='yledg4-co', nom='YLEDG4 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestExtourneFactureAnnulee(TestCase):
    def setUp(self):
        self.company = make_company()
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L4',
            email='yledg4@example.com', telephone='+212600000041')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YLEDG4',
            prix_vente=Decimal('1000'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG4-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_annulation_extourne_ecriture_comptabilisee_once(self):
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        ecriture = EcritureComptable.objects.get(
            company=self.company, source_type='facture',
            source_id=self.facture.id)

        facture_annulee.send(
            sender=Facture, instance=self.facture, company=self.company)
        extourne_qs = EcritureComptable.objects.filter(
            company=self.company, source_type='extourne',
            source_id=ecriture.id)
        self.assertEqual(extourne_qs.count(), 1)
        # L'écriture d'origine n'est JAMAIS supprimée (COMPTA11).
        self.assertTrue(
            EcritureComptable.objects.filter(pk=ecriture.pk).exists())

        # Annuler deux fois (best-effort, ré-émission) n'en poste qu'une.
        facture_annulee.send(
            sender=Facture, instance=self.facture, company=self.company)
        self.assertEqual(extourne_qs.count(), 1)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_annulation_sans_ecriture_source_ne_cree_rien(self):
        # Facture jamais comptabilisée (facture_emise jamais envoyé) :
        # l'annulation n'a rien à extourner.
        facture_annulee.send(
            sender=Facture, instance=self.facture, company=self.company)
        self.assertEqual(EcritureComptable.objects.count(), 0)

    def test_annulation_noop_when_toggle_off(self):
        facture_annulee.send(
            sender=Facture, instance=self.facture, company=self.company)
        self.assertEqual(EcritureComptable.objects.count(), 0)
