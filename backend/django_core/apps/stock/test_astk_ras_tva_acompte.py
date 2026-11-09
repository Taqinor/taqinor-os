"""ASTK175 — RAS-TVA par facture fournisseur, règle (a) tranchée par le
fondateur le 07/10/2026 (réponse à ASTK171, « Toute la TVA ») : la retenue
due = TVA × taux de la facture ENTIÈRE, ventilée sur ses règlements, le
DERNIER règlement portant le solde de retenue au centime. Un acompte imputé
ne porte pas de retenue propre (aucun champ RAS sur l'acompte) : sa part de
retenue est portée par les paiements suivants.

Run:
    python manage.py test apps.stock.test_astk_ras_tva_acompte
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
    AchatsParametres, AcompteFournisseur, BonCommandeFournisseur,
    FactureFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, PaiementFournisseur, Produit,
    ReceptionFournisseur,
)
from apps.stock.services import facturer_reception

User = get_user_model()


class RasTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='astk175-co', slug='astk175-co')
        role = Role.objects.create(
            company=self.company, nom='r-astk175',
            permissions=['stock_voir', 'stock_modifier',
                         # ASTK17-20 (D-ASTK-3) : l'acheteur porte les codes achats.
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        self.user = User.objects.create_user(
            username='astk175-user', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        params = AchatsParametres.for_company(self.company)
        params.ras_tva_actif = True
        params.save()
        # Fournisseur SANS ARF : biens ⇒ retenue 100 %.
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK175')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASTK175',
            prix_vente=Decimal('200'), prix_achat=Decimal('100'),
            tva=Decimal('20'))

    def _facture_avec_acompte(self, acompte):
        """Facture de biens TTC 1 200 / TVA 200 avec un acompte imputé."""
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK175-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK175-1',
            bon_commande=bcf, statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit,
            quantite=10)
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf, montant=acompte)
        facture = facturer_reception(self.company, self.user, rec)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(facture.type_achat, FactureFournisseur.TypeAchat.BIENS)
        self.assertEqual(facture.montant_ttc, Decimal('1200.00'))
        self.assertEqual(facture.montant_tva, Decimal('200.00'))
        self.assertEqual(facture.total_acomptes_imputes, acompte)
        return facture

    def _payer(self, facture, montant):
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': montant,
            'date_paiement': '2026-10-05',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return PaiementFournisseur.objects.get(pk=resp.data['id'])

    def test_avoir_impute_reduit_la_base(self):
        """AAPV4 (D-AAPV-1) — facture TTC 1 200 / TVA 200, avoir 600 TTC (TVA
        100) imputé : le paiement de 600 retient 100,00 (TVA nette)."""
        from apps.stock.models import AvoirFournisseur
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-AAPV4', fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-AAPV4', fournisseur=self.fournisseur,
            montant_ht=Decimal('500'), montant_tva=Decimal('100'),
            montant_ttc=Decimal('600'), statut=AvoirFournisseur.Statut.VALIDE)
        r = self.api.post(f'/api/django/stock/avoirs-fournisseur/{avoir.id}/imputer/',
                          {'facture': facture.id}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        paiement = self._payer(facture, '600')
        self.assertEqual(paiement.montant_ras_tva, Decimal('100.00'))
        self.assertEqual(paiement.montant_net_paye, Decimal('500.00'))
        facture.refresh_from_db()
        self.assertEqual(facture.statut, FactureFournisseur.Statut.PAYEE)

    def _facture_sans_acompte(self):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AAPV5-1', fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-AAPV5-1', bon_commande=bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit, quantite=10)
        facture = facturer_reception(self.company, self.user, rec)
        return bcf, FactureFournisseur.objects.get(pk=facture.pk)

    def test_paiement_puis_acompte_somme_exacte(self):
        """AAPV5 (D-AAPV-2) — paiement 840 (RAS 140) puis acompte 360 qui
        solde : l'imputation porte 60,00, Σ 200,00 ; le relevé liste 140 et 60."""
        from apps.stock.models import ImputationAcompteFournisseur
        from apps.stock.services import relevé_ras_tva
        bcf, facture = self._facture_sans_acompte()
        self.assertEqual(self._payer(facture, '840').montant_ras_tva, Decimal('140.00'))
        r = self.api.post('/api/django/stock/acomptes-fournisseur/', {
            'bon_commande': bcf.id, 'montant': '360',
            'date_versement': '2026-10-06'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, FactureFournisseur.Statut.PAYEE)
        imp = ImputationAcompteFournisseur.objects.get(facture=facture)
        self.assertEqual(imp.montant_ras_tva, Decimal('60.00'))
        montants = sorted(r['montant_ras_tva'] for r in relevé_ras_tva(self.company))
        self.assertEqual(montants, [Decimal('60.00'), Decimal('140.00')])

    def test_acompte_brut_qui_solde_constate_une_creance(self):
        """AAPV86 (D-AAPV-6 = creance_fournisseur) — paiement 840 puis acompte
        360 versé brut qui solde : la RAS de 60 déclarée sur l'imputation n'a pas
        été retenue ⇒ créance de 60 sur le fournisseur (avoir validé, imputable,
        lié à la facture). Acompte imputé AVANT le paiement : aucune créance."""
        from apps.stock.models import AvoirFournisseur
        bcf, facture = self._facture_sans_acompte()
        self._payer(facture, '840')
        self.assertFalse(AvoirFournisseur.objects.filter(company=self.company).exists())
        r = self.api.post('/api/django/stock/acomptes-fournisseur/', {
            'bon_commande': bcf.id, 'montant': '360',
            'date_versement': '2026-10-06'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        creance = AvoirFournisseur.objects.get(company=self.company)
        self.assertEqual((creance.montant_ttc, creance.montant_tva, creance.montant_disponible),
                         (Decimal('60.00'), Decimal('0.00'), Decimal('60.00')))
        self.assertEqual((creance.statut, creance.fournisseur_id, creance.facture_origine_id),
                         (AvoirFournisseur.Statut.VALIDE, self.fournisseur.id, facture.id))
        self.assertIn('RAS-TVA', creance.note)
        self._facture_avec_acompte_temoin()

    def _facture_avec_acompte_temoin(self):
        from apps.stock.models import AvoirFournisseur
        avant = AvoirFournisseur.objects.filter(company=self.company).count()
        facture = self._facture_avec_acompte(Decimal('360'))
        self.assertEqual(self._payer(facture, '840').montant_ras_tva, Decimal('200.00'))
        self.assertEqual(AvoirFournisseur.objects.filter(company=self.company).count(), avant)

    def test_paiement_puis_avoir_qui_solde(self):
        """AAPV5 — même chaîne par un avoir 360 (sans TVA propre) : 60,00 ;
        une imputation qui ne solde pas ne porte rien."""
        from apps.stock.models import AvoirFournisseur, ImputationAvoirFournisseur
        from apps.stock.services import imputer_avoir_fournisseur
        _bcf, facture = self._facture_sans_acompte()
        self._payer(facture, '840')
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-AAPV5', fournisseur=self.fournisseur,
            montant_ht=Decimal('360'), montant_tva=Decimal('0'),
            montant_ttc=Decimal('360'), statut=AvoirFournisseur.Statut.VALIDE)
        imputer_avoir_fournisseur(avoir, facture, Decimal('100'), user=self.user)
        imputer_avoir_fournisseur(avoir, facture, None, user=self.user)
        ras = list(ImputationAvoirFournisseur.objects.filter(
            facture=facture).order_by('id').values_list('montant_ras_tva', flat=True))
        self.assertEqual(ras, [Decimal('0.00'), Decimal('60.00')])

    def test_ras_totale_facture(self):
        """Sonde FACF-12 rejouée : 140,00 observé au prorata, 200,00 sous (a)."""
        facture = self._facture_avec_acompte(Decimal('360'))
        paiement = self._payer(facture, '840')
        self.assertEqual(paiement.montant_ras_tva, Decimal('200.00'))
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        total_ras = sum(
            (p.montant_ras_tva for p in facture.paiements.all()),
            Decimal('0'))
        self.assertEqual(total_ras, Decimal('200.00'))

    def test_ras_ventilee_dernier_reglement_porte_le_solde(self):
        facture = self._facture_avec_acompte(Decimal('360'))
        p1 = self._payer(facture, '400')
        # Part réglée après p1 = 360 + 400 = 760 / 1 200 ⇒ 126,67 dus.
        self.assertEqual(p1.montant_ras_tva, Decimal('126.67'))
        p2 = self._payer(facture, '440')
        self.assertEqual(p2.montant_ras_tva, Decimal('73.33'))
        self.assertEqual(
            p1.montant_ras_tva + p2.montant_ras_tva, Decimal('200.00'))

    def test_trois_reglements_somme_exacte_au_centime(self):
        facture = self._facture_avec_acompte(Decimal('100'))
        paiements = [self._payer(facture, m) for m in ('333', '333', '434')]
        self.assertEqual(
            sum((p.montant_ras_tva for p in paiements), Decimal('0')),
            Decimal('200.00'))
