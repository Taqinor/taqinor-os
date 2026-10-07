"""ASTK104 — PDF facture fournisseur : chaîne complète Total TTC − paiements
− acomptes imputés − avoirs imputés = solde dû, bloc toujours rendu.

Rendu HTML réel du gabarit (WeasyPrint non requis pour l'assertion).

Run:
    python manage.py test apps.stock.test_astk_pdf_facture_fournisseur_solde
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AcompteFournisseur, BonCommandeFournisseur, FactureFournisseur,
    Fournisseur, LigneBonCommandeFournisseur, LigneReceptionFournisseur,
    PaiementFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    facturer_reception, recompute_facture_fournisseur_statut,
    render_facture_fournisseur_html,
)

User = get_user_model()


class PdfSoldeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='astk104-co', slug='astk104-co')
        role = Role.objects.create(
            company=self.company, nom='r-astk104',
            permissions=['stock_voir', 'stock_modifier'])
        self.user = User.objects.create_user(
            username='astk104-user', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK104')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASTK104',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            tva=Decimal('20'))

    def _facture_reception(self, acompte=None):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK104-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK104-1',
            bon_commande=bcf, statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit,
            quantite=10)
        if acompte is not None:
            AcompteFournisseur.objects.create(
                company=self.company, bon_commande=bcf, montant=acompte)
        return facturer_reception(self.company, self.user, rec)

    @staticmethod
    def _bloc_totaux(html):
        debut = html.index('Total TTC')
        return html[debut:html.index('<!-- Paiements -->', debut)]

    def _assert_ordre(self, bloc, attendus):
        position = 0
        for texte in attendus:
            idx = bloc.find(texte, position)
            self.assertNotEqual(
                idx, -1, f'« {texte} » absent ou hors ordre dans {bloc!r}')
            position = idx + len(texte)

    def test_chaine_boucle(self):
        facture = self._facture_reception(acompte=Decimal('3600'))
        PaiementFournisseur.objects.create(
            company=self.company, facture=facture, montant=Decimal('1000'),
            date_paiement=datetime.date(2026, 10, 2))
        recompute_facture_fournisseur_statut(facture)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        bloc = self._bloc_totaux(render_facture_fournisseur_html(facture))
        self._assert_ordre(
            bloc, ['12 000,00', '1 000,00', '3 600,00', '0,00', '7 400,00'])
        # La chaîne imprimée boucle au centime.
        self.assertEqual(
            facture.montant_ttc - facture.total_paye
            - facture.total_acomptes_imputes - facture.total_avoirs_imputes,
            facture.solde_du)
        self.assertEqual(facture.solde_du, Decimal('7400.00'))
        # Régénérer → même chaîne.
        bloc2 = self._bloc_totaux(render_facture_fournisseur_html(facture))
        self.assertEqual(bloc, bloc2)

    def test_sans_reglement_bloc_rendu(self):
        facture = self._facture_reception()
        bloc = self._bloc_totaux(render_facture_fournisseur_html(facture))
        self.assertIn('Solde dû', bloc)
        self._assert_ordre(
            bloc, ['12 000,00', '0,00', '0,00', '0,00', '12 000,00'])
