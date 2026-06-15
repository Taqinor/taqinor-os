"""Tests des paramètres métier éditables (Paramètres → Devis / TVA).

Vérifie : les DÉFAUTS reproduisent exactement le comportement historique, et
ÉDITER un réglage change la sortie (échéancier, préfixes, TVA standard).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.echeancier import schedule_for_devis, creer_facture_tranche
from apps.ventes.utils.references import create_with_reference
from apps.ventes.utils.company_settings import doc_prefix, tva_standard

User = get_user_model()


def make_company(slug='set-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': 'Set Co'})[0]


class TestDevisSettings(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='set_user', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Set', telephone='+212600000010')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-SET-0001',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        prod = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-S',
            prix_vente=Decimal('10000'), quantite_stock=5, tva=Decimal('20.00'))
        LigneDevis.objects.create(
            devis=self.devis, produit=prod, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20.00'))  # 10000 HT + 2000 TVA = 12000 TTC

    def test_default_payment_terms_unchanged(self):
        # Défaut résidentiel = 30/60/10 (comportement historique).
        sched = schedule_for_devis(self.devis)
        self.assertEqual(sched, [('acompte', 30), ('materiel', 60), ('solde', 10)])

    def test_edited_payment_terms_change_schedule_and_facture(self):
        profile = CompanyProfile.get(company=self.company)
        profile.payment_terms = {
            'residentiel': {'acompte': 40, 'materiel': 50, 'solde': 10}}
        profile.save(update_fields=['payment_terms'])
        sched = schedule_for_devis(self.devis)
        self.assertEqual(sched[0], ('acompte', 40))
        # La facture d'acompte vaut désormais 40 % de 12000 = 4800 TTC.
        facture = creer_facture_tranche(
            self.devis, self.user, self.company, create_with_reference)
        self.assertEqual(facture.montant_ttc, Decimal('4800.00'))

    def test_default_facture_prefix_is_fac(self):
        self.assertEqual(doc_prefix(self.company, 'facture'), 'FAC')
        facture = creer_facture_tranche(
            self.devis, self.user, self.company, create_with_reference)
        self.assertTrue(facture.reference.startswith('FAC-'))

    def test_edited_prefix_changes_reference(self):
        profile = CompanyProfile.get(company=self.company)
        profile.doc_prefixes = {'facture': 'FACT'}
        profile.save(update_fields=['doc_prefixes'])
        self.assertEqual(doc_prefix(self.company, 'facture'), 'FACT')
        facture = creer_facture_tranche(
            self.devis, self.user, self.company, create_with_reference)
        self.assertTrue(facture.reference.startswith('FACT-'))

    def test_tva_standard_default_is_20(self):
        self.assertEqual(tva_standard(self.company), Decimal('20'))
        # Une ligne sans taux et sans tva produit retombe sur 20 (identique).
        prod = Produit.objects.create(
            company=self.company, nom='Service', sku='SVC-S',
            prix_vente=Decimal('500'), quantite_stock=0, tva=None)
        from apps.ventes.serializers import LigneDevisSerializer
        ser = LigneDevisSerializer(data={
            'devis': self.devis.id, 'produit': prod.id,
            'designation': 'Service', 'quantite': '1', 'prix_unitaire': '500'})
        ser.is_valid(raise_exception=True)
        ligne = ser.save()
        self.assertEqual(ligne.taux_tva, Decimal('20.00'))

    def test_edited_tva_standard_applies_to_new_lines(self):
        profile = CompanyProfile.get(company=self.company)
        profile.tva_standard = Decimal('14.00')
        profile.save(update_fields=['tva_standard'])
        prod = Produit.objects.create(
            company=self.company, nom='Service2', sku='SVC2',
            prix_vente=Decimal('500'), quantite_stock=0, tva=None)
        from apps.ventes.serializers import LigneDevisSerializer
        ser = LigneDevisSerializer(data={
            'devis': self.devis.id, 'produit': prod.id,
            'designation': 'Service2', 'quantite': '1', 'prix_unitaire': '500'})
        ser.is_valid(raise_exception=True)
        ligne = ser.save()
        self.assertEqual(ligne.taux_tva, Decimal('14.00'))
