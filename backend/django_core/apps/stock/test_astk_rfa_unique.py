"""ASTK50 (C-ASTK-010) — un accord RFA ne génère qu'UN avoir, même en course.

Constat WMS-5 : l'accord chargé deux fois (instances périmées : double clic,
deux onglets) générait DEUX avoirs (21 et 22) ; `avoir_genere` finissait sur
le 22 et le 21 restait orphelin. La contrainte partielle annoncée par
models_rfa.py n'existait pas (seules `stock_accordrfa_periode_coherente` et
`stock_accordrfa_co_fourn_periode_uniq`). Désormais `generer_avoir_rfa` relit
l'accord sous verrou et la base porte `stock_accordrfa_avoir_genere_uniq`.

Run :
    python manage.py test apps.stock.test_astk_rfa_unique
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company
from apps.stock.models import (
    AccordRFAFournisseur, AvoirFournisseur, BonCommandeFournisseur,
    Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from apps.stock.services_rfa import generer_avoir_rfa

User = get_user_model()

DEBUT = datetime.date(2026, 1, 1)
FIN = datetime.date(2026, 12, 31)


class RfaUniqueTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK50 Co', slug='astk50-co')
        self.user = User.objects.create_user(
            username='astk50-admin', password='x', company=self.company,
            role_legacy='admin')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK50')
        produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK50', sku='PAN-ASTK50',
            prix_achat=Decimal('900'), prix_vente=Decimal('1200'),
            quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK50-1',
            fournisseur=self.fournisseur,
            date_commande=datetime.date(2026, 3, 15))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=produit, quantite=100,
            quantite_recue=100, prix_achat_unitaire=Decimal('1000'))
        self.accord = AccordRFAFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            periode_debut=DEBUT, periode_fin=FIN,
            seuil_ca_achat=Decimal('50000'), taux_pct=Decimal('3'))

    def test_double_generation(self):
        # Deux instances chargées AVANT toute génération (périmées).
        instance_1 = AccordRFAFournisseur.objects.get(pk=self.accord.pk)
        instance_2 = AccordRFAFournisseur.objects.get(pk=self.accord.pk)
        premier = generer_avoir_rfa(instance_1, self.user)
        self.assertIsNone(instance_2.avoir_genere_id)  # encore périmée
        with self.assertRaises(ValueError) as ctx:
            generer_avoir_rfa(instance_2, self.user)
        self.assertIn('déjà été généré', str(ctx.exception))
        self.assertEqual(
            AvoirFournisseur.objects.filter(company=self.company).count(), 1)
        self.accord.refresh_from_db()
        self.assertEqual(self.accord.avoir_genere_id, premier.id)

    def test_contrainte_base_avoir_unique(self):
        avoir = generer_avoir_rfa(self.accord, self.user)
        autre_fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Autre fournisseur ASTK50')
        autre = AccordRFAFournisseur.objects.create(
            company=self.company, fournisseur=autre_fournisseur,
            periode_debut=DEBUT, periode_fin=FIN,
            seuil_ca_achat=Decimal('0'), taux_pct=Decimal('1'))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccordRFAFournisseur.objects.filter(pk=autre.pk).update(
                    avoir_genere=avoir)
        autre.refresh_from_db()
        self.assertIsNone(autre.avoir_genere_id)

    def test_plusieurs_accords_sans_avoir_restent_permis(self):
        # La contrainte est PARTIELLE : des accords sans avoir (NULL)
        # coexistent librement.
        autre_fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Troisième fournisseur ASTK50')
        AccordRFAFournisseur.objects.create(
            company=self.company, fournisseur=autre_fournisseur,
            periode_debut=DEBUT, periode_fin=FIN,
            seuil_ca_achat=Decimal('0'), taux_pct=Decimal('1'))
        self.assertEqual(AccordRFAFournisseur.objects.filter(
            company=self.company, avoir_genere__isnull=True).count(), 2)
