"""NTP2P9 — Tolérances de rapprochement 3 voies configurables par catégorie.

Couvre :
  * une catégorie SANS override retombe sur le défaut société (XPUR10,
    comportement historique inchangé) ;
  * une catégorie AVEC override élargi (ex. consommables 5 %) empêche une
    facture qui aurait été mise en exception sous le défaut société (0 %) de
    l'être ;
  * un BCF dont les lignes couvrent PLUSIEURS catégories retombe sur le
    défaut société (pas d'ambiguïté silencieuse) ;
  * CRUD API de la grille (lecture tout rôle, écriture stock_modifier).

Run:
    python manage.py test apps.stock.test_ntp2p9_tolerance_categorie -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, BonCommandeFournisseur, Categorie, FactureFournisseur,
    Fournisseur, LigneBonCommandeFournisseur, Produit,
    ReceptionFournisseur, LigneReceptionFournisseur,
    ToleranceRapprochementCategorie,
)
from apps.stock.services import evaluate_facture_exception, evaluer_tolerance_ecart

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


class Ntp2p9Base(TestCase):
    def setUp(self):
        self.company = _company('ntp2p9-co')
        self.user = _user(
            self.company, 'ntp2p9-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTP2P9')
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Consommables')
        self.produit = Produit.objects.create(
            company=self.company, nom='Consommable X', sku='CONS-NTP2P9',
            categorie=self.categorie,
            prix_vente=Decimal('200'), prix_achat=Decimal('100'))

    def _bcf_recu(self, quantite=10, prix=Decimal('1000'), produit=None):
        produit = produit or self.produit
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTP2P9-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=produit, quantite=quantite,
            prix_achat_unitaire=prix, quantite_recue=quantite)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-NTP2P9-0001',
            bon_commande=bcf, statut=ReceptionFournisseur.Statut.CONFIRME)
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=produit,
            quantite=quantite)
        return bcf


class TestDefautSocieteSansOverride(Ntp2p9Base):
    def test_sans_ligne_categorie_retombe_sur_defaut_societe(self):
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('2'))
        bcf = self._bcf_recu()
        self.assertEqual(
            evaluer_tolerance_ecart(self.company, bcf.id), Decimal('2'))


class TestOverrideCategorieElargit(Ntp2p9Base):
    def test_categorie_elargie_evite_exception_que_defaut_societe_aurait_signalee(self):
        # Défaut société STRICT (0 %) — sans override, tout écart positif
        # basculerait la facture en exception (comme XPUR10 le documente).
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('0'))
        ToleranceRapprochementCategorie.objects.create(
            company=self.company, categorie=self.categorie,
            tolerance_prix_pct=Decimal('5'))
        bcf = self._bcf_recu()

        self.assertEqual(
            evaluer_tolerance_ecart(self.company, bcf.id), Decimal('5'))

        from apps.compta.models import Rapprochement
        Rapprochement.objects.create(
            company=self.company, bon_commande=bcf,
            montant_commande=Decimal('10000'), montant_recu=Decimal('10000'),
            montant_facture=Decimal('10300'), ecart=Decimal('300'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-NTP2P9-0001',
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ht=Decimal('10300'), montant_ttc=Decimal('12360'))
        en_exception, ecart_pct = evaluate_facture_exception(
            self.company, facture)
        # +3 % : hors du défaut société (0 %) mais DANS l'override catégorie
        # (5 %) — la facture ne doit PAS être mise en exception.
        self.assertAlmostEqual(float(ecart_pct), 3.0, places=1)
        self.assertFalse(en_exception)
        facture.refresh_from_db()
        self.assertEqual(
            facture.statut_controle, FactureFournisseur.StatutControle.NORMALE)


class TestBcfMultiCategorieRetombeSurDefaut(Ntp2p9Base):
    def test_lignes_de_categories_differentes_retombe_sur_defaut(self):
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('2'))
        autre_categorie = Categorie.objects.create(
            company=self.company, nom='Équipements')
        autre_produit = Produit.objects.create(
            company=self.company, nom='Équipement Y', sku='EQUIP-NTP2P9',
            categorie=autre_categorie,
            prix_vente=Decimal('500'), prix_achat=Decimal('300'))
        ToleranceRapprochementCategorie.objects.create(
            company=self.company, categorie=self.categorie,
            tolerance_prix_pct=Decimal('5'))

        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTP2P9-0002',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('100'), quantite_recue=1)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=autre_produit, quantite=1,
            prix_achat_unitaire=Decimal('300'), quantite_recue=1)

        # Mélange de catégories → pas de spécificité claire → défaut société.
        self.assertEqual(
            evaluer_tolerance_ecart(self.company, bcf.id), Decimal('2'))


class TestApiCrud(Ntp2p9Base):
    def test_creer_et_lister_via_api(self):
        resp = self.api.post(
            '/api/django/stock/tolerances-rapprochement-categorie/',
            {'categorie': self.categorie.id,
             'tolerance_prix_pct': '7.5'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = self.api.get(
            '/api/django/stock/tolerances-rapprochement-categorie/')
        self.assertEqual(resp.status_code, 200, resp.data)
        lignes = (resp.data.get('results') if isinstance(resp.data, dict)
                  else resp.data)
        self.assertEqual(len(lignes), 1)

    def test_ecriture_refusee_sans_permission(self):
        viewer = _user(self.company, 'ntp2p9-viewer', permissions=['stock_voir'])
        api = _api(viewer)
        resp = api.post(
            '/api/django/stock/tolerances-rapprochement-categorie/',
            {'categorie': self.categorie.id,
             'tolerance_prix_pct': '7.5'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
