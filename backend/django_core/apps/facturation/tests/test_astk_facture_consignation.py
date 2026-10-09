"""ASTK197 (C-ASTK-047) — `creer_facture_consignation` : facture BROUILLON
d'une consommation de dépôt de consignation, au prix de vente catalogue HT,
TVA du produit, numérotée par references.py, idempotente par
`reference_origine`. Fonction réelle (via la façade `apps.ventes.services`),
aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_astk_facture_consignation"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class FactureConsignationTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='Co ASTK197', slug='co-astk197')
        self.autre = Company.objects.create(
            nom='Autre ASTK197', slug='autre-astk197')
        self.user = User.objects.create_user(
            username='resp-astk197', password='x', company=self.company,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Consigne', prenom='Client',
            email='astk197@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK197', sku='SKU-ASTK197',
            prix_vente=Decimal('1000.00'), prix_achat=Decimal('600.00'),
            tva=Decimal('10.00'), quantite_stock=5)

    def _creer(self, ref='CONSIGNATION-1', client=None, company=None):
        from apps.ventes.services import creer_facture_consignation
        return creer_facture_consignation(
            company=company or self.company,
            client=client or self.client_obj, user=self.user,
            lignes=[{'produit': self.produit, 'quantite': 2}],
            reference_origine=ref)

    def test_brouillon_au_prix_de_vente(self):
        from apps.ventes.models import Facture
        facture = self._creer()
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertEqual(facture.client_id, self.client_obj.id)
        self.assertTrue(facture.reference.startswith('FAC-'))
        lignes = list(facture.lignes.all())
        self.assertEqual(len(lignes), 1)
        ligne = lignes[0]
        self.assertEqual(ligne.produit_id, self.produit.id)
        self.assertEqual(ligne.quantite, Decimal('2'))
        self.assertEqual(ligne.prix_unitaire, Decimal('1000.00'))
        self.assertEqual(ligne.taux_tva, Decimal('10.00'))
        self.assertEqual(Decimal(str(facture.total_ht)), Decimal('2000.00'))
        self.assertEqual(Decimal(str(facture.total_ttc)), Decimal('2200.00'))

    def test_idempotente(self):
        from apps.ventes.models import Facture
        f1 = self._creer('CONSIGNATION-7')
        f2 = self._creer('CONSIGNATION-7')
        self.assertEqual(f1.pk, f2.pk)
        self.assertEqual(Facture.objects.filter(
            company=self.company, client=self.client_obj).count(), 1)
        f3 = self._creer('CONSIGNATION-8')
        self.assertNotEqual(f3.pk, f1.pk)
        self.assertNotEqual(f3.reference, f1.reference)

    def test_jamais_prix_achat(self):
        facture = self._creer()
        prix = [ligne.prix_unitaire for ligne in facture.lignes.all()]
        self.assertNotIn(Decimal('600.00'), prix)
        self.assertEqual(prix, [Decimal('1000.00')])

    def test_autre_societe_refusee(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        client_b = Client.objects.create(
            company=self.autre, nom='B', prenom='Client',
            email='astk197-b@example.invalid')
        with self.assertRaises(ValueError):
            self._creer(client=client_b)
        with self.assertRaises(ValueError):
            # produit de A facturé pour la société B
            self._creer(client=client_b, company=self.autre)
        self.assertFalse(Facture.objects.exists())
