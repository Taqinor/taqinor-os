"""ERR-QAC-FACTURE-RECALCUL-REMISE — ``ajouter_lignes_frais_refactures`` doit
respecter la chaîne canonique (remise globale) et ne pas écraser une facture
d'échéance figée."""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture
from apps.ventes.services import ajouter_lignes_frais_refactures
from authentication.models import Company


class RecalculFraisRefactures(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QAC Recalcul', slug='qac-recalcul')
        self.client_obj = Client.objects.create(
            company=self.company, nom='C', prenom='X',
            telephone='+212600000099')

    def _facture(self, **kw):
        return Facture.objects.create(
            company=self.company, reference='FAC-QAC-1',
            client=self.client_obj, taux_tva=Decimal('20.00'), **kw)

    def test_remise_globale_honoree(self):
        facture = self._facture(remise_globale=Decimal('10'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='QAC-PV',
            prix_vente=Decimal('1000'), quantite_stock=10)
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        ajouter_lignes_frais_refactures(
            facture=facture, lignes=[{'designation': 'Transport',
                                      'montant_ht': Decimal('100')}])
        facture = Facture.objects.get(pk=facture.pk)
        # (1000 + 100) * 0,90 = 990 HT ; TVA 20 % = 198 ; TTC 1188.
        self.assertEqual(facture.montant_ht, Decimal('990.00'))
        self.assertEqual(facture.montant_ttc, Decimal('1188.00'))
        self.assertEqual(facture.montant_ttc, facture.totaux_affichage['ttc'])

    def test_facture_figee_ajoute_les_frais(self):
        facture = self._facture(
            montant_ht=Decimal('1000.00'), montant_tva=Decimal('200.00'),
            montant_ttc=Decimal('1200.00'))
        ajouter_lignes_frais_refactures(
            facture=facture, lignes=[{'designation': 'Transport',
                                      'montant_ht': Decimal('100')}])
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.montant_ht, Decimal('1100.00'))
        self.assertEqual(facture.montant_tva, Decimal('220.00'))
        self.assertEqual(facture.montant_ttc, Decimal('1320.00'))
