"""ACHT14 (C-ACHT-013) — le registre des séries entrepôt d'une réception
confirmée est plafonné à la quantité RÉELLEMENT entrée par ligne, et une
série « retournée » qui revient par une nouvelle réception repasse « en
stock » (référence de la nouvelle réception).

Rejoue CACH-8 : BCF de 2, réception saisie 5 avec 5 séries → 5 « en stock »
pour 2 appliqués ; séries d'une réception annulée restées « retourné » après
leur re-réception.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_series_reception"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.installations.models import SerieEntrepot
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    annuler_reception_confirmee, confirm_reception_fournisseur,
)

User = get_user_model()


class SeriesReceptionTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht14', defaults={'nom': 'Co ACHT14'})
        self.user = User.objects.create_user(
            username='resp-acht14', password='x', company=self.company,
            role_legacy='responsable')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ACHT14', prix_vente=100)
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fourn ACHT14')
        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, fournisseur=fournisseur,
            reference='BC-ACHT14')
        self._n = 0

    def _ligne_cmd(self, quantite):
        return LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=10)

    def _reception(self, ligne_cmd, quantite, series):
        self._n += 1
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ACHT14-{self._n}',
            bon_commande=self.bc)
        LigneReceptionFournisseur.objects.create(
            reception=reception, ligne_commande=ligne_cmd,
            produit=self.produit, quantite=quantite, numeros_serie=series)
        confirm_reception_fournisseur(reception, self.user)
        reception.refresh_from_db()
        return reception

    def _en_stock(self):
        return set(SerieEntrepot.objects.filter(
            company=self.company, produit=self.produit,
            statut=SerieEntrepot.Statut.EN_STOCK).values_list(
                'numero_serie', flat=True))

    def test_series_plafonnees_quantite_appliquee(self):
        ligne = self._ligne_cmd(2)
        self._reception(ligne, 5, ['S1', 'S2', 'S3', 'S4', 'S5'])
        self.assertEqual(self._en_stock(), {'S1', 'S2'})
        self.assertFalse(SerieEntrepot.objects.filter(
            company=self.company, numero_serie__in=['S3', 'S4', 'S5'])
            .exists())

    def test_re_reception_remet_en_stock(self):
        ligne = self._ligne_cmd(4)
        r1 = self._reception(ligne, 2, ['C8B1', 'C8B2'])
        annuler_reception_confirmee(r1, self.user)
        self.assertEqual(self._en_stock(), set())
        r2 = self._reception(ligne, 2, ['C8B1', 'C8B2'])
        self.assertEqual(self._en_stock(), {'C8B1', 'C8B2'})
        refs = set(SerieEntrepot.objects.filter(
            company=self.company, produit=self.produit).values_list(
                'reference_reception', flat=True))
        self.assertEqual(refs, {r2.reference})

    def test_serie_sortie_jamais_reactivee(self):
        ligne = self._ligne_cmd(4)
        SerieEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_serie='X1',
            statut=SerieEntrepot.Statut.SORTI, reference_reception='OLD')
        self._reception(ligne, 1, ['X1'])
        serie = SerieEntrepot.objects.get(company=self.company,
                                          numero_serie='X1')
        self.assertEqual(serie.statut, SerieEntrepot.Statut.SORTI)
        self.assertEqual(serie.reference_reception, 'OLD')
