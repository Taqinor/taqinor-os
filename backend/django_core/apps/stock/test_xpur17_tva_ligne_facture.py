"""XPUR17 — TVA par ligne sur la facture fournisseur (taux marocains).

Couvre :
  * une facture mixte 20 %+10 % sort les bons sous-totaux par taux ;
  * une facture historique (lignes sans taux_tva) n'apparaît pas dans les
    sous-totaux par taux — compat totale, montant_tva global inchangé ;
  * la facturation depuis réception (FG56) reprend le taux du produit ;
  * le relevé de déductions TVA agrège correctement par taux, sur période.

Run:
    python manage.py test apps.stock.test_xpur17_tva_ligne_facture -v 2
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
    BonCommandeFournisseur, FactureFournisseur, Fournisseur, Produit,
    ReceptionFournisseur,
)
from apps.stock.selectors import (
    releve_deductions_tva_par_taux, sous_totaux_tva_facture_fournisseur,
)
from apps.stock.services import confirm_reception_fournisseur, facturer_reception

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xpur17Base(TestCase):
    def setUp(self):
        self.company = _company('xpur17-co')
        self.user = _user(
            self.company, 'xpur17-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur TVA X17')


class TestSousTotauxParTaux(Xpur17Base):
    def test_facture_mixte_20_et_10(self):
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-X17-1',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('3000'), montant_tva=Decimal('500'),
            montant_ttc=Decimal('3500'))
        facture.lignes.create(
            designation='Panneaux', quantite=1,
            prix_unitaire_ht=Decimal('2000'), taux_tva=Decimal('10'))
        facture.lignes.create(
            designation='Onduleur', quantite=1,
            prix_unitaire_ht=Decimal('1000'), taux_tva=Decimal('20'))

        sous_totaux = sous_totaux_tva_facture_fournisseur(facture)
        self.assertEqual(len(sous_totaux), 2)
        par_taux = {e['taux_tva']: e for e in sous_totaux}
        self.assertEqual(par_taux[Decimal('20')]['total_ht'], Decimal('1000'))
        self.assertEqual(par_taux[Decimal('20')]['total_tva'], Decimal('200.00'))
        self.assertEqual(par_taux[Decimal('10')]['total_ht'], Decimal('2000'))
        self.assertEqual(par_taux[Decimal('10')]['total_tva'], Decimal('200.00'))

    def test_facture_historique_sans_taux_ligne_absente(self):
        """Compat : une ligne sans taux_tva (facture émise avant XPUR17)
        n'apparaît PAS dans les sous-totaux — le montant_tva global de la
        facture reste l'unique source de vérité, rendu inchangé."""
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-X17-2',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        facture.lignes.create(
            designation='Ligne historique', quantite=1,
            prix_unitaire_ht=Decimal('1000'), taux_tva=None)
        sous_totaux = sous_totaux_tva_facture_fournisseur(facture)
        self.assertEqual(sous_totaux, [])
        # Le montant global n'a jamais bougé.
        self.assertEqual(facture.montant_tva, Decimal('200'))

    def test_endpoint_expose_sous_totaux(self):
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-X17-3',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        facture.lignes.create(
            designation='Onduleur', quantite=1,
            prix_unitaire_ht=Decimal('1000'), taux_tva=Decimal('20'))
        resp = self.api.get(
            f'/api/django/stock/factures-fournisseur/{facture.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['sous_totaux_par_taux']), 1)


class TestFacturationReprendTauxProduit(Xpur17Base):
    def test_facturer_reception_reprend_taux_produit(self):
        produit_10 = Produit.objects.create(
            company=self.company, nom='Panneau X17', sku='PAN-XPUR17',
            prix_vente=Decimal('900'), prix_achat=Decimal('500'),
            tva=Decimal('10'))
        produit_20 = Produit.objects.create(
            company=self.company, nom='Onduleur X17', sku='OND-XPUR17',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'),
            tva=Decimal('20'))
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X17-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_10 = bc.lignes.create(
            produit=produit_10, quantite=2,
            prix_achat_unitaire=Decimal('500'))
        ligne_20 = bc.lignes.create(
            produit=produit_20, quantite=1,
            prix_achat_unitaire=Decimal('1200'))

        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-X17-1', bon_commande=bc)
        reception.lignes.create(
            ligne_commande=ligne_10, produit=produit_10, quantite=2)
        reception.lignes.create(
            ligne_commande=ligne_20, produit=produit_20, quantite=1)
        confirm_reception_fournisseur(reception, self.user)

        facture = facturer_reception(self.company, self.user, reception)
        lignes = {ln.designation: ln for ln in facture.lignes.all()}
        self.assertEqual(lignes['Panneau X17'].taux_tva, Decimal('10'))
        self.assertEqual(lignes['Onduleur X17'].taux_tva, Decimal('20'))
        # HT : 2*500 + 1*1200 = 2200. TVA : 1000*10% + 1200*20% = 100+240=340.
        self.assertEqual(facture.montant_ht, Decimal('2200'))
        self.assertEqual(facture.montant_tva, Decimal('340.00'))

    def test_produit_sans_tva_prend_le_defaut_20(self):
        produit = Produit.objects.create(
            company=self.company, nom='Produit Sans TVA X17',
            sku='SKU-X17-NOTVA', prix_vente=Decimal('100'),
            prix_achat=Decimal('50'))
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X17-2',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = bc.lignes.create(
            produit=produit, quantite=1, prix_achat_unitaire=Decimal('50'))
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-X17-2', bon_commande=bc)
        reception.lignes.create(
            ligne_commande=ligne, produit=produit, quantite=1)
        confirm_reception_fournisseur(reception, self.user)
        facture = facturer_reception(self.company, self.user, reception)
        ligne_facture = facture.lignes.first()
        self.assertEqual(ligne_facture.taux_tva, Decimal('20'))


class TestReleveDeductionsTva(Xpur17Base):
    def test_releve_agrege_par_taux_sur_periode(self):
        f1 = FactureFournisseur.objects.create(
            company=self.company, reference='FF-X17-R1',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 6, 5),
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        f1.lignes.create(
            designation='A', quantite=1, prix_unitaire_ht=Decimal('1000'),
            taux_tva=Decimal('20'))
        f2 = FactureFournisseur.objects.create(
            company=self.company, reference='FF-X17-R2',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 6, 20),
            montant_ht=Decimal('500'), montant_tva=Decimal('50'),
            montant_ttc=Decimal('550'))
        f2.lignes.create(
            designation='B', quantite=1, prix_unitaire_ht=Decimal('500'),
            taux_tva=Decimal('10'))
        # Hors période — ne doit pas compter.
        f3 = FactureFournisseur.objects.create(
            company=self.company, reference='FF-X17-R3',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 1, 1),
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'))
        f3.lignes.create(
            designation='C', quantite=1, prix_unitaire_ht=Decimal('100'),
            taux_tva=Decimal('20'))

        releve = releve_deductions_tva_par_taux(
            self.company, date_debut=datetime.date(2026, 6, 1),
            date_fin=datetime.date(2026, 6, 30))
        par_taux = {e['taux_tva']: e for e in releve}
        self.assertEqual(par_taux[Decimal('20')]['total_ht'], Decimal('1000'))
        self.assertEqual(par_taux[Decimal('10')]['total_ht'], Decimal('500'))
        self.assertNotIn(Decimal('100'), [e['total_ht'] for e in releve])

    def test_endpoint_releve_deductions(self):
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-X17-R4',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        facture.lignes.create(
            designation='A', quantite=1, prix_unitaire_ht=Decimal('1000'),
            taux_tva=Decimal('20'))
        resp = self.api.get(
            '/api/django/stock/factures-fournisseur/'
            'releve-deductions-tva/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
