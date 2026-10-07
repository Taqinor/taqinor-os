"""ASTK58 — annuler une réception confirmée NON CONFORME lève la quarantaine
qu'elle avait posée (NTWMS34).

Constat C-ASTK-011 (volet WMS-13, plausible non sondé) : le routage qualité
post-confirmation crée un ``BlocageQualite`` EN_QUARANTAINE rattaché à la
réception ; ``annuler_reception_confirmee`` contre-passait le stock sans
toucher au blocage, laissant une quarantaine fantôme sur une marchandise
sortie.

Run :
    python manage.py test apps.stock.test_astk_annulation_quarantaine -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    BlocageQualite, BonCommandeFournisseur, Categorie, ControleReception,
    Fournisseur, PlanEchantillonnage, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    annuler_reception_confirmee, confirm_reception_fournisseur,
    quantite_disponible_hors_quarantaine,
)
from apps.stock.services_qualite_reception import (
    enregistrer_controle_reception,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


class AnnulationQuarantaineTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk58-co-{n}', nom=f'ASTK58 Co {n}')
        self.admin = User.objects.create_user(
            username=f'astk58-{n}', password='x', role_legacy='admin',
            company=self.company)
        categorie = Categorie.objects.create(
            company=self.company, nom=f'Batteries ASTK58 {n}')
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=categorie,
            taux_echantillon_pct=20)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK58')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie ASTK58', sku=f'ASTK58-{n}',
            categorie=categorie, prix_achat=Decimal('3000'),
            prix_vente=Decimal('4000'), quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK58-{n}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_cmd = bc.lignes.create(
            produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('3000'))
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTK58-{n}',
            bon_commande=bc)
        self.reception.lignes.create(
            ligne_commande=ligne_cmd, produit=self.produit, quantite=10)
        enregistrer_controle_reception(
            reception=self.reception, user=self.admin,
            resultat=ControleReception.Resultat.NON_CONFORME,
            unites_controlees=2, observation='Cellules gonflées')
        confirm_reception_fournisseur(self.reception, self.admin)
        # Pré-condition : la quarantaine est posée.
        self.assertTrue(BlocageQualite.objects.filter(
            reception=self.reception,
            statut=BlocageQualite.Statut.EN_QUARANTAINE).exists())

    def test_annulation_leve_la_quarantaine(self):
        annuler_reception_confirmee(self.reception, self.admin)

        self.assertFalse(BlocageQualite.objects.filter(
            reception=self.reception,
            statut=BlocageQualite.Statut.EN_QUARANTAINE).exists())
        blocage = BlocageQualite.objects.get(reception=self.reception)
        self.assertEqual(blocage.statut, BlocageQualite.Statut.LEVEE)
        self.assertIn('réception annulée', blocage.motif.lower())

    def test_stock_et_disponible_jamais_negatif(self):
        annuler_reception_confirmee(self.reception, self.admin)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)
        self.assertEqual(
            quantite_disponible_hors_quarantaine(self.company, self.produit),
            0)
