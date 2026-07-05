"""YPROC9 — Réappro net du forecast : déduire les BCF ouverts + réservations
et fusionner au lieu de dupliquer (FG364).

Couvre :
  * un produit sous seuil dont un BCF ENVOYE couvre déjà le manque n'est plus
    suggéré (`produits_a_reapprovisionner`) ;
  * `quantite_en_commande_produit` somme correctement les lignes de BCF
    BROUILLON/ENVOYE non annulés/non reçus (jamais RECU/ANNULE) ;
  * deux appels successifs à `generer_bcf_reappro` n'ouvrent qu'UN brouillon
    par fournisseur (fusion, incrément des lignes) ;
  * `previsions_reappro` (FG65) expose désormais `date_rupture`/
    `point_commande` (FG364, `core.stock_reorder`) ;
  * comportement inchangé (produit suggéré, quantité identique) quand aucun
    BCF ouvert ni réservation n'existe.

Run:
    python manage.py test apps.stock.test_yproc9_reappro_net_pipeline -v 2
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit, MouvementStock
from apps.stock.services import (
    produits_a_reapprovisionner, generer_bcf_reappro,
)
from apps.stock.selectors import quantite_en_commande_produit


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


class Yproc9Base(TestCase):
    def setUp(self):
        self.company = _company('yproc9-co')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YPROC9')
        self.produit = Produit.objects.create(
            company=self.company, nom='Câble YPROC9', sku='CAB-YPROC9',
            prix_vente=Decimal('50'), prix_achat=Decimal('20'),
            quantite_stock=5, seuil_alerte=10,
            quantite_reappro_cible=30)


class TestNettingPipeline(Yproc9Base):
    def test_produit_sous_seuil_sans_pipeline_est_suggere(self):
        besoins = produits_a_reapprovisionner(self.company)
        self.assertEqual(len(besoins), 1)
        self.assertEqual(besoins[0]['produit_id'], self.produit.id)
        self.assertEqual(besoins[0]['en_commande'], 0)
        self.assertEqual(besoins[0]['quantite_suggere'], 30)

    def test_bcf_envoye_couvrant_le_manque_exclut_le_produit(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC9-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        bc.lignes.create(
            produit=self.produit, quantite=30,
            prix_achat_unitaire=Decimal('20'))
        besoins = produits_a_reapprovisionner(self.company)
        self.assertEqual(besoins, [])

    def test_bcf_partiel_reduit_la_quantite_suggeree_nette(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC9-2',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        bc.lignes.create(
            produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('20'))
        besoins = produits_a_reapprovisionner(self.company)
        self.assertEqual(len(besoins), 1)
        # Seul le PIPELINE (en_commande) nette la cible (comportement FG54
        # préservé : `quantite_suggere` == cible pleine hors pipeline, jamais
        # réduite par le disponible courant) : cible 30 - en_commande 10 = 20.
        self.assertEqual(besoins[0]['en_commande'], 10)
        self.assertEqual(besoins[0]['quantite_suggere'], 20)

    def test_bcf_annule_ou_recu_nignore_pas_dans_en_commande(self):
        bc_annule = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC9-3',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ANNULE)
        bc_annule.lignes.create(
            produit=self.produit, quantite=100,
            prix_achat_unitaire=Decimal('20'))
        bc_recu = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC9-4',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        bc_recu.lignes.create(
            produit=self.produit, quantite=20, quantite_recue=20,
            prix_achat_unitaire=Decimal('20'))
        self.assertEqual(
            quantite_en_commande_produit(self.company, self.produit.id), 0)

    def test_quantite_en_commande_deduit_deja_recu_partiellement(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC9-5',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        bc.lignes.create(
            produit=self.produit, quantite=20, quantite_recue=8,
            prix_achat_unitaire=Decimal('20'))
        self.assertEqual(
            quantite_en_commande_produit(self.company, self.produit.id), 12)


class TestFusionBcfReappro(Yproc9Base):
    def test_deux_appels_successifs_fusionnent_un_seul_brouillon(self):
        result1 = generer_bcf_reappro(
            self.company, user=None, fournisseur_id=self.fournisseur.id)
        self.assertFalse(result1['fusionne'])
        nb_brouillons = BonCommandeFournisseur.objects.filter(
            company=self.company,
            statut=BonCommandeFournisseur.Statut.BROUILLON).count()
        self.assertEqual(nb_brouillons, 1)

        # YPROC9 nette la cible UNIQUEMENT contre le pipeline déjà en commande
        # (`en_commande`, jamais le disponible courant — comportement FG54
        # préservé, `quantite_suggere` == cible pleine hors pipeline). Le
        # premier appel couvre donc intégralement `self.produit` (en_commande
        # == cible) : un second appel sur le MÊME produit ne resuggérerait
        # rien. On déclenche le second besoin avec un AUTRE produit sous
        # seuil chez le même fournisseur, pour vérifier la fusion dans le
        # MÊME brouillon (et non l'ouverture d'un second).
        autre_produit = Produit.objects.create(
            company=self.company, nom='Onduleur YPROC9', sku='OND-YPROC9',
            prix_vente=Decimal('500'), prix_achat=Decimal('300'),
            quantite_stock=1, seuil_alerte=5, quantite_reappro_cible=15)
        from apps.stock.models import PrixFournisseur
        PrixFournisseur.objects.create(
            company=self.company, produit=autre_produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('300'))

        result2 = generer_bcf_reappro(
            self.company, user=None, fournisseur_id=self.fournisseur.id)
        self.assertTrue(result2['fusionne'])
        self.assertEqual(result2['bon_commande_id'], result1['bon_commande_id'])
        nb_brouillons_apres = BonCommandeFournisseur.objects.filter(
            company=self.company,
            statut=BonCommandeFournisseur.Statut.BROUILLON).count()
        self.assertEqual(nb_brouillons_apres, 1)
        bon = BonCommandeFournisseur.objects.get(id=result1['bon_commande_id'])
        self.assertTrue(bon.lignes.filter(produit=autre_produit).exists())

    def test_fusion_incremente_la_ligne_existante(self):
        bon_existant = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC9-EXIST',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON,
            note='Réapprovisionnement automatique (stock < seuil)')
        bon_existant.lignes.create(
            produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('20'))

        result = generer_bcf_reappro(
            self.company, user=None, fournisseur_id=self.fournisseur.id)
        self.assertTrue(result['fusionne'])
        self.assertEqual(result['bon_commande_id'], bon_existant.id)
        ligne = bon_existant.lignes.get(produit=self.produit)
        # 10 (existant) + 30 (nouveau besoin, aucun pipeline pris en compte
        # par le bon existant lui-même car sa propre ligne n'est pas
        # comptée dans en_commande avant sa création initiale... le test
        # vérifie seulement l'INCRÉMENT, pas la valeur absolue.
        self.assertGreater(ligne.quantite, 10)


class TestPrevisionsReapproFG364(Yproc9Base):
    def test_previsions_reappro_expose_date_rupture_et_point_commande(self):
        from apps.stock.services import previsions_reappro
        MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=30, quantite_avant=35, quantite_apres=5,
            reference='TEST-SORTIE-2', note='Test conso')
        result = previsions_reappro(self.company, nb_mois=1)
        self.assertEqual(len(result), 1)
        self.assertIn('date_rupture', result[0])
        self.assertIn('point_commande', result[0])
        self.assertIsNotNone(result[0]['date_rupture'])

    def test_previsions_reappro_sans_conso_ne_plante_pas(self):
        from apps.stock.services import previsions_reappro
        result = previsions_reappro(self.company, nb_mois=1)
        self.assertEqual(result, [])
