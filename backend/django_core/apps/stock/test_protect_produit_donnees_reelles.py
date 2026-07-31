"""Le catalogue produit porte des DONNÉES RÉELLES : toute ligne rattachée qui
contient un prix négocié, une fiche constructeur ou un fait de traçabilité
DOIT bloquer la suppression du produit au lieu d'être effacée en silence.

Contexte fondateur : `stock.Produit` et `crm.Lead` sont les deux seuls jeux de
données réels de l'ERP (prix d'achat fournisseur saisis à la main, courbes de
pompe, pipeline commercial). Un CASCADE sur ces liens = perte métier réelle.

Ce module verrouille les 10 liens passés en ``on_delete=PROTECT`` :

  achats.PrixFournisseur          prix d'achat fournisseur négocié
  cpq.LigneOffreGroupee           prix imposé / remise d'un bundle
  cpq.PrixContractuel             prix contractuel client×produit
  ventes.LignePrixListe           prix unitaire d'une liste de prix
  ventes.RegleListePrix           règle de prix (palier / remise)
  ventes.FicheTechnique           fiche constructeur + PDF datasheet
  stock.FicheTechnique            fiche constructeur (paramètres STC)
  stock.LotEntrepot               lot tracé (« jamais supprimé »)
  stock.StockEmplacement          quantité réelle par emplacement
  installations.SerieEntrepot     numéro de série d'une unité physique

PROTECT est appliqué par le COLLECTEUR Django (``django.db.models.deletion``),
pas par une contrainte SQL : il fonctionne donc même sur un FK déclaré
``db_constraint=False`` (patron string-FK cross-app de ce dépôt).

Run :
    python manage.py test apps.stock.test_protect_produit_donnees_reelles -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models as dj_models
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.achats.models import PrixFournisseur
from apps.cpq.models import LigneOffreGroupee, OffreGroupee, PrixContractuel
from apps.crm.models import Client
from apps.installations.models_serie_entrepot import SerieEntrepot
from apps.stock.models import (
    EmplacementStock,
    FicheTechnique,
    Fournisseur,
    LotEntrepot,
    MouvementStock,
    Produit,
    StockEmplacement,
)
from apps.ventes.models import (
    FicheTechnique as FicheTechniqueVentes,
    LignePrixListe,
    ListePrix,
    RegleListePrix,
)
from authentication.models import Company

User = get_user_model()


class ProtectProduitBase(TestCase):
    """Un produit du catalogue + les objets pivots réutilisés par les tests."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='protect-prod-co', defaults={'nom': 'Protect Prod Co'})[0]
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550 Wc',
            prix_achat=Decimal('900.00'), prix_vente=Decimal('1200.00'))

    def assert_delete_refuse(self, dependant_model, dependant_pk):
        """Le produit refuse la suppression ET les deux lignes survivent."""
        with self.assertRaises(ProtectedError):
            self.produit.delete()
        self.assertTrue(
            Produit.objects.filter(pk=self.produit.pk).exists(),
            'le produit doit survivre à la tentative de suppression')
        self.assertTrue(
            dependant_model.objects.filter(pk=dependant_pk).exists(),
            f'{dependant_model.__name__} doit survivre (donnée réelle)')


class TestPrixProtegees(ProtectProduitBase):
    """Tout ce qui porte un PRIX convenu bloque la suppression du produit."""

    def test_prix_fournisseur_bloque_la_suppression(self):
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Réel')
        prix = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=fournisseur, prix_achat=Decimal('870.00'))
        self.assert_delete_refuse(PrixFournisseur, prix.pk)
        self.assertEqual(
            PrixFournisseur.objects.get(pk=prix.pk).prix_achat,
            Decimal('870.00'))

    def test_prix_contractuel_bloque_la_suppression(self):
        client = Client.objects.create(company=self.company, nom='Client Réel')
        prix = PrixContractuel.objects.create(
            company=self.company, client=client, produit=self.produit,
            prix_ht=Decimal('1150.00'))
        self.assert_delete_refuse(PrixContractuel, prix.pk)

    def test_ligne_offre_groupee_bloque_la_suppression(self):
        offre = OffreGroupee.objects.create(
            company=self.company, nom='Pack Résidentiel')
        ligne = LigneOffreGroupee.objects.create(
            offre=offre, produit=self.produit, valeur=Decimal('10.00'))
        self.assert_delete_refuse(LigneOffreGroupee, ligne.pk)

    def test_ligne_liste_prix_bloque_la_suppression(self):
        liste = ListePrix.objects.create(
            company=self.company, nom='Liste Détail')
        ligne = LignePrixListe.objects.create(
            liste=liste, produit=self.produit,
            prix_unitaire=Decimal('1250.00'))
        self.assert_delete_refuse(LignePrixListe, ligne.pk)

    def test_regle_liste_prix_bloque_la_suppression(self):
        """SET_NULL serait un PIÈGE ici : ``produit=NULL`` signifie « tout le
        catalogue », donc une règle produit deviendrait une remise globale."""
        liste = ListePrix.objects.create(
            company=self.company, nom='Liste Pro')
        regle = RegleListePrix.objects.create(
            liste=liste, produit=self.produit,
            type_regle=RegleListePrix.TypeRegle.PRIX_FIXE,
            valeur=Decimal('1100.0000'))
        self.assert_delete_refuse(RegleListePrix, regle.pk)
        self.assertEqual(
            RegleListePrix.objects.get(pk=regle.pk).produit_id,
            self.produit.pk,
            'la portée produit de la règle ne doit jamais devenir NULL')


class TestFichesEtTracabiliteProtegees(ProtectProduitBase):
    """Fiches constructeur et faits de traçabilité non reconstructibles."""

    def test_fiche_technique_stock_bloque_la_suppression(self):
        fiche = FicheTechnique.objects.create(
            company=self.company, produit=self.produit)
        self.assert_delete_refuse(FicheTechnique, fiche.pk)

    def test_fiche_technique_ventes_bloque_la_suppression(self):
        fiche = FicheTechniqueVentes.objects.create(
            company=self.company, produit=self.produit)
        self.assert_delete_refuse(FicheTechniqueVentes, fiche.pk)

    def test_lot_entrepot_bloque_la_suppression(self):
        lot = LotEntrepot.objects.create(
            company=self.company, produit=self.produit,
            numero_lot='LOT-2026-001', quantite_recue=10,
            quantite_restante=10)
        self.assert_delete_refuse(LotEntrepot, lot.pk)

    def test_stock_emplacement_bloque_la_suppression(self):
        emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal')
        ligne = StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=emplacement, quantite=7)
        self.assert_delete_refuse(StockEmplacement, ligne.pk)
        self.assertEqual(
            StockEmplacement.objects.get(pk=ligne.pk).quantite, 7)

    def test_serie_entrepot_bloque_la_suppression(self):
        serie = SerieEntrepot.objects.create(
            company=self.company, produit=self.produit,
            numero_serie='SN-0001')
        self.assert_delete_refuse(SerieEntrepot, serie.pk)


class TestPolitiqueOnDelete(TestCase):
    """Verrou structurel : la politique elle-même ne doit pas régresser.

    PROTECT est une fonction Python du collecteur Django, jamais une clause
    SQL ``ON DELETE`` — d'où son fonctionnement même sans contrainte en base.
    """

    LIENS_PROTEGES = [
        (PrixFournisseur, 'produit'),
        (LigneOffreGroupee, 'produit'),
        (PrixContractuel, 'produit'),
        (LignePrixListe, 'produit'),
        (RegleListePrix, 'produit'),
        (FicheTechnique, 'produit'),
        (FicheTechniqueVentes, 'produit'),
        (LotEntrepot, 'produit'),
        (StockEmplacement, 'produit'),
        (SerieEntrepot, 'produit'),
    ]

    def test_tous_les_liens_reels_sont_protect(self):
        for model, field_name in self.LIENS_PROTEGES:
            with self.subTest(model=model.__name__):
                field = model._meta.get_field(field_name)
                self.assertIs(
                    field.remote_field.on_delete, dj_models.PROTECT,
                    f'{model.__name__}.{field_name} doit rester PROTECT '
                    '(donnée réelle du catalogue)')

    def test_protect_est_applique_par_le_collecteur_pas_par_la_base(self):
        """``on_delete`` n'émet aucun SQL : Django le classe non-DB."""
        self.assertIn('on_delete', dj_models.Field.non_db_attrs)


class TestForceDeleteRefuseLesDonneesReelles(TestCase):
    """``/produits/<id>/force-delete/`` ne doit plus détruire de prix réel —
    et ne doit pas non plus perdre les mouvements en cours de route."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='protect-fd-co', defaults={'nom': 'Protect FD Co'})[0]
        self.user = User.objects.create_superuser(
            username='protect_fd_admin', password='x',
            email='fd@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Variateur VEICHI 5,5 kW',
            prix_achat=Decimal('4200.00'), prix_vente=Decimal('5900.00'),
            is_archived=True)

    def test_refuse_409_et_conserve_prix_et_mouvements(self):
        liste = ListePrix.objects.create(
            company=self.company, nom='Liste Revendeur')
        ligne = LignePrixListe.objects.create(
            liste=liste, produit=self.produit,
            prix_unitaire=Decimal('5600.00'))
        mouvement = MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=3, quantite_avant=0, quantite_apres=3)

        reponse = self.api.delete(
            f'/api/django/stock/produits/{self.produit.pk}/force-delete/')

        self.assertEqual(reponse.status_code, 409)
        self.assertTrue(Produit.objects.filter(pk=self.produit.pk).exists())
        self.assertTrue(LignePrixListe.objects.filter(pk=ligne.pk).exists())
        self.assertTrue(
            MouvementStock.objects.filter(pk=mouvement.pk).exists(),
            'la transaction doit annuler la suppression des mouvements')

    def test_produit_sans_donnee_reelle_reste_supprimable(self):
        """La garde ne doit pas bloquer un produit réellement jetable."""
        mouvement = MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=1, quantite_avant=0, quantite_apres=1)

        reponse = self.api.delete(
            f'/api/django/stock/produits/{self.produit.pk}/force-delete/')

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Produit.objects.filter(pk=self.produit.pk).exists())
        self.assertFalse(
            MouvementStock.objects.filter(pk=mouvement.pk).exists())
