"""DC10 — le produit est REQUIS sur une nouvelle ligne d'avoir (lien fort).

Le FK LigneAvoir.produit reste nullable en base (SET_NULL) pour ne pas
invalider les lignes historiques dont le produit a été supprimé, MAIS toute
NOUVELLE ligne doit désigner un produit : contrainte appliquée au niveau
applicatif (model.clean + serializer + endpoint creer-avoir).
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Facture, LigneAvoir
from apps.ventes.serializers import LigneAvoirSerializer
from apps.ventes.tests.test_quote_engine import make_company, make_user


class TestDC10AvoirProduit(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='C', prenom='D', email='c@d.ma')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-DC10',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-DC10-1', client=self.client_obj,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))
        self.avoir = Avoir.objects.create(
            company=self.company, reference='AVO-DC10-1', facture=self.facture,
            client=self.client_obj, statut=Avoir.Statut.EMISE,
            taux_tva=Decimal('20'))

    def test_clean_rejects_new_line_without_produit(self):
        ligne = LigneAvoir(
            avoir=self.avoir, designation='Sans produit',
            quantite=Decimal('1'), prix_unitaire=Decimal('100'))
        with self.assertRaises(ValidationError):
            ligne.full_clean()

    def test_clean_accepts_new_line_with_produit(self):
        ligne = LigneAvoir(
            avoir=self.avoir, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20'))
        # ne doit pas lever pour l'absence de produit
        try:
            ligne.full_clean()
        except ValidationError as exc:
            self.assertNotIn('produit', exc.message_dict)

    def test_historical_null_line_stays_valid_at_db_level(self):
        # Création directe (bypass clean) d'une ligne historique sans produit :
        # elle reste enregistrable — la contrainte est applicative, pas base.
        ligne = LigneAvoir.objects.create(
            avoir=self.avoir, designation='Historique', quantite=Decimal('1'),
            prix_unitaire=Decimal('100'), taux_tva=Decimal('20'))
        self.assertIsNone(ligne.produit_id)
        # Une modification ULTÉRIEURE (pas une création) ne re-déclenche pas la
        # contrainte de création.
        ligne.designation = 'Historique modifiée'
        ligne.full_clean()  # ne lève pas : self._state.adding est False

    def test_serializer_requires_produit(self):
        s = LigneAvoirSerializer(data={
            'designation': 'X', 'quantite': '1', 'prix_unitaire': '100'})
        self.assertFalse(s.is_valid())
        self.assertIn('produit', s.errors)
