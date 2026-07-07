"""ZPUR10 — Section « Bons de commande envoyés » (engagements) sur la fiche
produit + exposition de la quantité en-commande.

Le sélecteur `quantite_en_commande_produit`/`bcf_sources_en_commande_produit`
(YPROC9) existait déjà et alimentait le NET de réappro, mais n'était PAS
exposé sur la fiche produit. Ce test couvre :
  * le calcul (Σ des restants sur BCF BROUILLON/ENVOYE, jamais ANNULE/RECU) ;
  * l'exposition sur `ProduitSerializer` (retrieve) avec les BCF sources ;
  * cross-company : un produit d'une autre société ne fuit rien ;
  * l'impact réappro (le net déduit déjà l'en-commande — non-régression).

Run:
    python manage.py test apps.stock.test_zpur10_produit_en_commande -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from apps.stock.selectors import (
    bcf_sources_en_commande_produit, quantite_en_commande_produit,
)

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


class Zpur10Base(TestCase):
    def setUp(self):
        self.company = _company('zpur10-co')
        self.user = _user(
            self.company, 'zpur10-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZPUR10')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ZPUR10', sku='PAN-ZPUR10',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))

    def _bcf(self, reference, statut, quantite=10, quantite_recue=0,
             prix=Decimal('1000')):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=reference,
            fournisseur=self.fournisseur, statut=statut)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=prix, quantite_recue=quantite_recue)
        return bcf


class TestCalculEnCommande(Zpur10Base):
    def test_somme_restants_brouillon_et_envoye(self):
        statut_envoye = BonCommandeFournisseur.Statut.ENVOYE
        statut_brouillon = BonCommandeFournisseur.Statut.BROUILLON
        self._bcf('BCF-ZPUR10-0001', statut_envoye,
                  quantite=50, quantite_recue=0)
        self._bcf('BCF-ZPUR10-0002', statut_brouillon,
                  quantite=10, quantite_recue=4)
        total = quantite_en_commande_produit(self.company, self.produit.id)
        self.assertEqual(total, 50 + 6)

    def test_annule_et_recu_exclus(self):
        statut_annule = BonCommandeFournisseur.Statut.ANNULE
        statut_recu = BonCommandeFournisseur.Statut.RECU
        self._bcf('BCF-ZPUR10-0003', statut_annule,
                  quantite=99, quantite_recue=0)
        self._bcf('BCF-ZPUR10-0004', statut_recu,
                  quantite=20, quantite_recue=20)
        total = quantite_en_commande_produit(self.company, self.produit.id)
        self.assertEqual(total, 0)

    def test_sans_bcf_zero(self):
        total = quantite_en_commande_produit(self.company, self.produit.id)
        self.assertEqual(total, 0)

    def test_sources_detail(self):
        statut_envoye = BonCommandeFournisseur.Statut.ENVOYE
        self._bcf('BCF-ZPUR10-0005', statut_envoye,
                  quantite=30, quantite_recue=10)
        sources = bcf_sources_en_commande_produit(
            self.company, self.produit.id)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['reference'], 'BCF-ZPUR10-0005')
        self.assertEqual(sources[0]['quantite_restante'], 20)
        self.assertEqual(
            sources[0]['fournisseur_nom'], self.fournisseur.nom)


class TestExpositionFicheProduit(Zpur10Base):
    def test_retrieve_expose_en_commande_et_sources(self):
        statut_envoye = BonCommandeFournisseur.Statut.ENVOYE
        self._bcf('BCF-ZPUR10-0006', statut_envoye,
                  quantite=50, quantite_recue=0)
        url = f'/api/django/stock/produits/{self.produit.id}/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['quantite_en_commande'], 50)
        self.assertEqual(len(resp.data['bcf_sources_en_commande']), 1)
        self.assertEqual(
            resp.data['bcf_sources_en_commande'][0]['reference'],
            'BCF-ZPUR10-0006')

    def test_retrieve_sans_bcf_zero_et_liste_vide(self):
        url = f'/api/django/stock/produits/{self.produit.id}/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['quantite_en_commande'], 0)
        self.assertEqual(resp.data['bcf_sources_en_commande'], [])

    def test_cross_company_isolated(self):
        other_co = _company('zpur10-autre')
        other_user = _user(
            other_co, 'zpur10-autre-user',
            permissions=['stock_modifier', 'stock_voir'])
        other_api = _api(other_user)
        statut_envoye = BonCommandeFournisseur.Statut.ENVOYE
        self._bcf('BCF-ZPUR10-0007', statut_envoye,
                  quantite=50, quantite_recue=0)
        url = f'/api/django/stock/produits/{self.produit.id}/'
        resp = other_api.get(url)
        self.assertEqual(resp.status_code, 404)


class TestImpactReappro(Zpur10Base):
    def test_reappro_deduit_partiellement_en_commande(self):
        from apps.stock.services import produits_a_reapprovisionner

        self.produit.seuil_alerte = 100
        self.produit.quantite_stock = 0
        self.produit.save(update_fields=['seuil_alerte', 'quantite_stock'])
        statut_envoye = BonCommandeFournisseur.Statut.ENVOYE
        self._bcf('BCF-ZPUR10-0008', statut_envoye,
                  quantite=40, quantite_recue=0)
        besoins = produits_a_reapprovisionner(self.company)
        entry = next(
            (b for b in besoins if b['produit_id'] == self.produit.id), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry['en_commande'], 40)
        # FG54 (comportement historique préservé) — sans
        # `quantite_reappro_cible` explicite, la cible est seuil × 2 = 200 ;
        # YPROC9 ne déduit que le pipeline déjà en commande : 200 - 40 = 160.
        self.assertEqual(entry['quantite_suggere'], 160)

    def test_reappro_exclut_produit_quand_en_commande_couvre_tout(self):
        from apps.stock.services import produits_a_reapprovisionner

        # `quantite_reappro_cible` explicite (100) — sans elle la cible par
        # défaut serait seuil × 2 = 200 (FG54, comportement historique).
        self.produit.seuil_alerte = 100
        self.produit.quantite_reappro_cible = 100
        self.produit.quantite_stock = 0
        self.produit.save(update_fields=[
            'seuil_alerte', 'quantite_reappro_cible', 'quantite_stock'])
        statut_envoye = BonCommandeFournisseur.Statut.ENVOYE
        self._bcf('BCF-ZPUR10-0009', statut_envoye,
                  quantite=100, quantite_recue=0)
        besoins = produits_a_reapprovisionner(self.company)
        entry = next(
            (b for b in besoins if b['produit_id'] == self.produit.id), None)
        self.assertIsNone(entry)
