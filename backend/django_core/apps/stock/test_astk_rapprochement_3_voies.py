"""ASTK107 — rapprochement 3 voies rebranché côté stock : au lien BCF (PATCH),
le HT facturé est comparé au reçu × PU du BCF ; hors tolérance ⇒ exception
+ motif, paiement bloqué ; dans la tolérance ⇒ normale ; une exception
résolue n'est jamais re-basculée.

Run:
    python manage.py test apps.stock.test_astk_rapprochement_3_voies
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, BonCommandeFournisseur, FactureFournisseur,
    Fournisseur, LigneBonCommandeFournisseur, LigneReceptionFournisseur,
    Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    evaluer_rapprochement_3_voies, factures_en_exception,
    resoudre_exception_facture,
)

User = get_user_model()


class Rapprochement3VoiesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='astk107-co', slug='astk107-co')
        role = Role.objects.create(
            company=self.company, nom='r-astk107',
            permissions=['stock_voir', 'stock_modifier',
                         # ASTK17-20 (D-ASTK-3) : l'acheteur porte les codes achats.
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        self.user = User.objects.create_user(
            username='astk107-user', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        params = AchatsParametres.for_company(self.company)
        params.tolerance_prix_pct = Decimal('0')
        params.save()
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK107')
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASTK107',
            prix_vente=Decimal('200'), prix_achat=Decimal('100'))
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK107-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=produit, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK107-1',
            bon_commande=self.bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=produit,
            quantite=10)

    def _facture_ocr(self, ht):
        tva = (ht * Decimal('0.2')).quantize(Decimal('0.01'))
        return FactureFournisseur.objects.create(
            company=self.company, reference=f'FF-ASTK107-{ht}',
            fournisseur=self.fournisseur, montant_ht=ht, montant_tva=tva,
            montant_ttc=ht + tva)

    def _lier(self, facture):
        return self.api.patch(
            f'/api/django/stock/factures-fournisseur/{facture.id}/',
            {'bon_commande': self.bcf.id}, format='json')

    def test_lien_bcf_hors_tolerance_exception(self):
        facture = self._facture_ocr(Decimal('1500'))
        resp = self._lier(facture)
        self.assertEqual(resp.status_code, 200, resp.data)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(
            facture.statut_controle,
            FactureFournisseur.StatutControle.EXCEPTION)
        self.assertIn('500,00', facture.motif_ecart)
        self.assertIn('50,00 %', facture.motif_ecart)
        self.assertIn(facture.id, [
            f.id for f in factures_en_exception(self.company)])

    def test_paiement_bloque(self):
        facture = self._facture_ocr(Decimal('1500'))
        self._lier(facture)
        resp = self.api.post(
            f'/api/django/stock/factures-fournisseur/{facture.id}/paiements/',
            {'montant': '1800', 'date_paiement': '2026-10-02'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(facture.paiements.count(), 0)

    def test_dans_tolerance_normale(self):
        facture = self._facture_ocr(Decimal('1000'))
        resp = self._lier(facture)
        self.assertEqual(resp.status_code, 200, resp.data)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(
            facture.statut_controle, FactureFournisseur.StatutControle.NORMALE)
        # Tolérance 10 % : 1 050 HT pour 1 000 reçus reste normale.
        params = AchatsParametres.for_company(self.company)
        params.tolerance_prix_pct = Decimal('10')
        params.save()
        facture.delete()
        f2 = self._facture_ocr(Decimal('1050'))
        self._lier(f2)
        f2 = FactureFournisseur.objects.get(pk=f2.pk)
        self.assertEqual(
            f2.statut_controle, FactureFournisseur.StatutControle.NORMALE)

    def test_resolue_jamais_rebasculee(self):
        facture = self._facture_ocr(Decimal('1500'))
        self._lier(facture)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        resoudre_exception_facture(
            facture, user=self.user, commentaire='Prix renégocié')
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(
            evaluer_rapprochement_3_voies(facture),
            FactureFournisseur.StatutControle.RESOLUE)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(
            facture.statut_controle, FactureFournisseur.StatutControle.RESOLUE)
        resp = self.api.post(
            f'/api/django/stock/factures-fournisseur/{facture.id}/paiements/',
            {'montant': '1800', 'date_paiement': '2026-10-02'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_sur_livraison_plafonnee_attendu_sur_quantite_appliquee(self):
        """ASTK245 — rejoue la sonde C-ASTK-VER-002 : BCF 10 × 100, réception
        de 12 confirmée (10 appliqués) ⇒ 1 200 HT facturés passent en
        exception (attendu 1 000) ; 1 000 HT restent « normale »."""
        from apps.stock.services import confirm_reception_fournisseur
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PAN-ASTK245',
            prix_vente=Decimal('200'), prix_achat=Decimal('100'))
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK245',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = bcf.lignes.create(
            produit=produit, quantite=10, prix_achat_unitaire=Decimal('100'))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK245', bon_commande=bcf,
            statut=ReceptionFournisseur.Statut.BROUILLON, created_by=self.user)
        rec.lignes.create(ligne_commande=ligne, produit=produit, quantite=12)
        confirm_reception_fournisseur(rec, self.user)
        self.assertEqual(rec.lignes.get().quantite_appliquee, 10)
        for ht, statut, motif in (
                (Decimal('1200'), FactureFournisseur.StatutControle.EXCEPTION,
                 '20,00 %'),
                (Decimal('1000'), FactureFournisseur.StatutControle.NORMALE,
                 '')):
            facture = FactureFournisseur.objects.create(
                company=self.company, reference=f'FF-ASTK245-{ht}',
                fournisseur=self.fournisseur, bon_commande=bcf, montant_ht=ht,
                montant_tva=Decimal('0'), montant_ttc=ht)
            evaluer_rapprochement_3_voies(facture)
            facture = FactureFournisseur.objects.get(pk=facture.pk)
            self.assertEqual(facture.statut_controle, statut, ht)
            self.assertIn(motif, facture.motif_ecart or '')
            facture.delete()
