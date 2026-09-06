"""AUD601 — aucune FK cross-app d'un sérialiseur CPQ ne peut pointer une AUTRE
société.

Les six FK concernées (``PrixContractuel.client``/``produit``,
``OptionProduit.produit``, ``ContrainteCompatibilite.produit_a``/``produit_b``,
``LigneOffreGroupee.produit``) sortaient toutes de DRF en
``PrimaryKeyRelatedField`` sur le queryset COMPLET de la table cible : la clé
primaire d'une société voisine était acceptée. La plus grave est
``LigneOffreGroupee.produit`` — ``services.appliquer_offre_groupee`` recopie la
ligne du bundle dans un DEVIS, donc dans le PDF remis au client.

Run :
    python manage.py test apps.cpq.tests.test_aud601_fk_meme_societe -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.cpq.serializers import (
    ContrainteCompatibiliteSerializer, LigneOffreGroupeeSerializer,
    OptionProduitSerializer, PrixContractuelSerializer,
)
from testkit.factories import ClientFactory, CompanyFactory, ProduitFactory


class BaseDeuxSocietes(TestCase):
    def setUp(self):
        self.nous = CompanyFactory()
        self.eux = CompanyFactory()
        self.produit_nous = ProduitFactory(
            company=self.nous, prix_vente=Decimal('1000.00'))
        self.produit_eux = ProduitFactory(
            company=self.eux, prix_vente=Decimal('1000.00'))
        self.client_nous = ClientFactory(company=self.nous)
        self.client_eux = ClientFactory(company=self.eux)

        class _Utilisateur:
            company_id = self.nous.pk

        class _Req:
            user = _Utilisateur()

        self.contexte = {'request': _Req()}

    def _refuse(self, serializer_cls, champ, etranger, local):
        ser = serializer_cls(data={champ: etranger}, partial=True,
                             context=self.contexte)
        self.assertFalse(
            ser.is_valid(),
            f'{serializer_cls.__name__}.{champ} accepte une ligne voisine')
        self.assertIn(champ, ser.errors)

        ok = serializer_cls(data={champ: local}, partial=True,
                            context=self.contexte)
        ok.is_valid()
        self.assertNotIn(
            champ, ok.errors,
            f'{serializer_cls.__name__}.{champ} refuse sa PROPRE société')


class TestFkCpq(BaseDeuxSocietes):
    def test_prix_contractuel_client(self):
        self._refuse(PrixContractuelSerializer, 'client',
                     self.client_eux.pk, self.client_nous.pk)

    def test_prix_contractuel_produit(self):
        self._refuse(PrixContractuelSerializer, 'produit',
                     self.produit_eux.pk, self.produit_nous.pk)

    def test_option_produit(self):
        self._refuse(OptionProduitSerializer, 'produit',
                     self.produit_eux.pk, self.produit_nous.pk)

    def test_contrainte_produit_a(self):
        self._refuse(ContrainteCompatibiliteSerializer, 'produit_a',
                     self.produit_eux.pk, self.produit_nous.pk)

    def test_contrainte_produit_b(self):
        self._refuse(ContrainteCompatibiliteSerializer, 'produit_b',
                     self.produit_eux.pk, self.produit_nous.pk)

    def test_ligne_offre_groupee_produit(self):
        """La FK qui atteint le DEVIS puis son PDF client."""
        self._refuse(LigneOffreGroupeeSerializer, 'produit',
                     self.produit_eux.pk, self.produit_nous.pk)


class TestLigneImbriqueeDansUnBundle(BaseDeuxSocietes):
    """Le bundle écrit ses lignes en IMBRIQUÉ : le garde doit y descendre.

    ``OffreGroupeeSerializer.lignes`` est un ``many=True`` — si la validation
    ne traversait pas le sérialiseur enfant, le chemin réellement utilisé par
    l'écran (POST d'un bundle complet) resterait ouvert.
    """

    def test_le_produit_voisin_est_refuse_dans_la_ligne_imbriquee(self):
        from apps.cpq.serializers import OffreGroupeeSerializer

        ser = OffreGroupeeSerializer(data={
            'nom': 'Kit voisin',
            'lignes': [{'produit': self.produit_eux.pk, 'quantite': '1'}],
        }, context=self.contexte)
        valide = ser.is_valid()
        self.assertFalse(valide, 'un produit voisin passe par la ligne '
                                 'imbriquée du bundle')
        self.assertIn('lignes', ser.errors)

    def test_le_produit_local_passe_dans_la_ligne_imbriquee(self):
        from apps.cpq.serializers import OffreGroupeeSerializer

        ser = OffreGroupeeSerializer(data={
            'nom': 'Kit maison',
            'lignes': [{'produit': self.produit_nous.pk, 'quantite': '1'}],
        }, context=self.contexte)
        self.assertTrue(ser.is_valid(), ser.errors)
