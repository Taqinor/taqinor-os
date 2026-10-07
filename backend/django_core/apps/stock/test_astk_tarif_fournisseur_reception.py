"""ASTK90 — la réception n'écrase plus le tarif fournisseur négocié.

Sonde PRIX-1 : une réception au prix d'un PALIER (80) réécrivait le tarif de
base (100 → 80) ; PRIX-1d : une réception à 130 le réécrivait aussi, donc
l'alerte d'écart NTP2P18 voyait toujours 0 % d'écart. Le flux est réel :
``confirm_reception_fournisseur`` et ``POST …/recevoir/`` (APIClient).
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    AchatsParametres, BonCommandeFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, LigneReceptionFournisseur,
    PalierPrixFournisseur, PrixFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    confirm_reception_fournisseur, prix_effectif_fournisseur,
)
from authentication.models import Company, CustomUser as User

_seq = itertools.count(1)


class TarifFournisseurReceptionTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ASTK90 {n}', slug=f'astk90-{n}')
        self.user = User.objects.create_superuser(
            username=f'astk90_admin_{n}', password='x',
            email=f'astk90-{n}@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK90')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK90', sku=f'AST90-{n}',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'))
        self.tarif = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('100.00'))
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=self.tarif, qte_min=50, prix=Decimal('80.00'))
        AchatsParametres.objects.create(
            company=self.company, seuil_deviation_prix_pct=Decimal('10'))

    def _bcf(self, quantite, prix, statut):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BC-AST90-{next(_seq)}',
            fournisseur=self.fournisseur, statut=statut)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal(str(prix)))
        return bc, ligne

    def test_reception_palier_garde_le_tarif_de_base(self):
        bc, ligne = self._bcf(
            50, 80, BonCommandeFournisseur.Statut.ENVOYE)
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-AST90-{next(_seq)}',
            bon_commande=bc)
        LigneReceptionFournisseur.objects.create(
            reception=reception, ligne_commande=ligne, produit=self.produit,
            quantite=50)

        confirm_reception_fournisseur(reception, self.user)

        self.tarif.refresh_from_db()  # persistance : relu en base
        self.assertEqual(self.tarif.prix_achat, Decimal('100.00'))
        self.assertEqual(
            prix_effectif_fournisseur(
                self.produit, self.fournisseur, quantite=1),
            Decimal('100.00'))
        self.assertEqual(
            self.tarif.date_dernier_achat, timezone.now().date())

    def test_alerte_ecart_sur_reception_reelle(self):
        bc, ligne = self._bcf(1, 130, BonCommandeFournisseur.Statut.ENVOYE)

        reponse = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.pk}/recevoir/',
            {'receptions': [{'ligne': ligne.pk, 'quantite': 1}]},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)

        self.tarif.refresh_from_db()
        self.assertEqual(self.tarif.prix_achat, Decimal('100.00'))
        self.assertEqual(
            self.tarif.date_dernier_achat, timezone.now().date())
        hist = self.api.get(
            f'/api/django/stock/produits/{self.produit.pk}/historique-prix/'
            f'?fournisseur={self.fournisseur.pk}')
        self.assertEqual(hist.status_code, 200, hist.content)
        data = hist.json()
        self.assertEqual(Decimal(str(data['prix_catalogue_actuel'])),
                         Decimal('100.00'))
        self.assertEqual(data['historique'][-1]['ecart_vs_catalogue_pct'],
                         30.0)
        self.assertTrue(data['dernier_prix_alerte'])
