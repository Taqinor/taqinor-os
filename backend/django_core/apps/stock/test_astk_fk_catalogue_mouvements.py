"""ASTK5 — `CompanyScopedRelationsMixin` sur les sérialiseurs catalogue et
mouvements (conditionnement, kit et composants, mouvement, transfert,
nomenclature et règle de code-barres, tolérance de rapprochement, produit) :
aucune FK écrite ne rattache un objet d'une autre société.

Rejoue CAT-4 (POST conditionnement sur le produit de B = 201, produit_nom
SECRET-PRODUIT-B, unité touret) et TEN-5 (PATCH d'une règle vers la
nomenclature de B = 200, la règle d'A s'évaluait alors chez B) de l'audit
stock du 2026-10-06.

Run:
    python manage.py test apps.stock.test_astk_fk_catalogue_mouvements -v 2
"""
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.relations import PrimaryKeyRelatedField
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.serializers import CompanyScopedPrimaryKeyRelatedField
from apps.stock.models import (
    Categorie, ConditionnementProduit, EmplacementStock,
    KitProduit, MouvementStock, NomenclatureCodeBarres, Produit,
    RegleCodeBarres, ToleranceRapprochementCategorie, TransfertStock,
)
from apps.stock.selectors import resolve_via_nomenclature
from apps.stock.serializers import ProduitSerializer

User = get_user_model()

ID_ABSENT = 99999999


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _inexistant(pk):
    """Message DRF « objet inexistant » pour ``pk`` (langue active)."""
    gabarit = PrimaryKeyRelatedField.default_error_messages['does_not_exist']
    return str(gabarit).format(pk_value=pk)


def _sans_id(corps, pk):
    """Remplace le message « objet inexistant » de ``pk`` par un jeton."""
    if isinstance(corps, dict):
        return {k: _sans_id(v, pk) for k, v in corps.items()}
    if isinstance(corps, (list, tuple)):
        return [_sans_id(v, pk) for v in corps]
    return '<INEXISTANT>' if str(corps) == _inexistant(pk) else str(corps)


class FkCatalogueMouvementsTests(TestCase):
    def setUp(self):
        # Même import local que test_ntwms1_casiers (modèle de casier FG319).
        from apps.installations.models import BinLocation

        self.co_a = Company.objects.create(nom='astk5-a', slug='astk5-a')
        self.co_b = Company.objects.create(nom='astk5-b', slug='astk5-b')
        self.resp_a = User.objects.create_user(
            username='astk5-resp-a', password='x', company=self.co_a,
            role_legacy='admin')
        self.api = _api(self.resp_a)
        self.pa = Produit.objects.create(
            company=self.co_a, nom='Produit A', sku='ASTK5-PA',
            prix_vente=Decimal('30'), quantite_stock=10)
        self.pb = Produit.objects.create(
            company=self.co_b, nom='SECRET-PRODUIT-B', sku='ASTK5-PB',
            prix_vente=Decimal('30'), quantite_stock=10, unite_stock='touret')
        self.cat_b = Categorie.objects.create(company=self.co_b, nom='CAT-B')
        self.nom_a = NomenclatureCodeBarres.objects.create(
            company=self.co_a, nom='Nomenclature A', actif=True)
        self.nom_b = NomenclatureCodeBarres.objects.create(
            company=self.co_b, nom='Nomenclature B', actif=True)
        self.regle_a = RegleCodeBarres.objects.create(
            nomenclature=self.nom_a, motif='77', encode='produit')
        self.emp_a = EmplacementStock.objects.create(
            company=self.co_a, nom='Dépôt A')
        self.emp_b = EmplacementStock.objects.create(
            company=self.co_b, nom='Dépôt B')
        self.bin_b = BinLocation.objects.create(
            company=self.co_b, emplacement=self.emp_b, code='B-01-01',
            zone='B', allee='01', casier='01', ordre=1)

    def _assert_comme_absent(self, r, r_absent, pk):
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r_absent.status_code, 400, r_absent.content)
        self.assertIn('<INEXISTANT>', str(_sans_id(r.json(), pk)))
        self.assertEqual(_sans_id(r.json(), pk),
                         _sans_id(r_absent.json(), ID_ABSENT))
        self.assertNotIn('SECRET-PRODUIT-B', r.content.decode())
        self.assertNotIn('touret', r.content.decode())

    def _post_compare(self, url, payload, champ, pk_etranger):
        r = self.api.post(url, {**payload, champ: pk_etranger}, format='json')
        r_absent = self.api.post(
            url, {**payload, champ: ID_ABSENT}, format='json')
        self._assert_comme_absent(r, r_absent, pk_etranger)

    def test_conditionnement_produit_etranger(self):
        self._post_compare('/api/django/stock/conditionnements/',
                           {'nom': 'Touret', 'facteur': '100'},
                           'produit', self.pb.pk)
        self.assertFalse(ConditionnementProduit.objects.exists())

    def test_regle_patch_nomenclature_etrangere(self):
        url = f'/api/django/stock/regles-code-barres/{self.regle_a.pk}/'
        r = self.api.patch(url, {'nomenclature': self.nom_b.pk},
                           format='json')
        r_absent = self.api.patch(url, {'nomenclature': ID_ABSENT},
                                  format='json')
        self._assert_comme_absent(r, r_absent, self.nom_b.pk)
        self.regle_a.refresh_from_db()
        self.assertEqual(self.regle_a.nomenclature_id, self.nom_a.pk)
        # La règle de A ne s'évalue jamais chez B.
        self.assertFalse(RegleCodeBarres.objects.filter(
            nomenclature=self.nom_b).exists())
        self.assertIsNone(resolve_via_nomenclature(self.co_b, '7712345'))

    def test_regle_creation_nomenclature_etrangere(self):
        self._post_compare('/api/django/stock/regles-code-barres/',
                           {'motif': '88', 'encode': 'produit'},
                           'nomenclature', self.nom_b.pk)
        self.assertEqual(RegleCodeBarres.objects.count(), 1)

    def test_tolerance_categorie_etrangere(self):
        self._post_compare(
            '/api/django/stock/tolerances-rapprochement-categorie/',
            {'tolerance_prix_pct': '7.5'}, 'categorie', self.cat_b.pk)
        self.assertFalse(ToleranceRapprochementCategorie.objects.exists())

    def test_mouvement_produit_etranger(self):
        self._post_compare('/api/django/stock/mouvements/',
                           {'type_mouvement': 'entree', 'quantite': 1},
                           'produit', self.pb.pk)
        self.pb.refresh_from_db()
        self.assertEqual(self.pb.quantite_stock, 10)
        self.assertFalse(MouvementStock.objects.exists())

    def test_mouvement_casier_etranger(self):
        self._post_compare('/api/django/stock/mouvements/', {
            'produit': self.pa.pk, 'type_mouvement': 'entree',
            'quantite': 1}, 'bin_source', self.bin_b.pk)
        self.pa.refresh_from_db()
        self.assertEqual(self.pa.quantite_stock, 10)
        self.assertFalse(MouvementStock.objects.exists())

    def test_transfert_source_etrangere(self):
        url = '/api/django/stock/transferts/'
        payload = {'produit': self.pa.pk, 'quantite': 1,
                   'destination': self.emp_a.pk}
        r = self.api.post(url, {**payload, 'source': self.emp_b.pk},
                          format='json')
        r_absent = self.api.post(url, {**payload, 'source': ID_ABSENT},
                                 format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json(), r_absent.json())
        self.assertFalse(TransfertStock.objects.exists())

    def test_kit_composant_produit_etranger(self):
        url = '/api/django/stock/kits/'

        def _payload(produit_id):
            return {'nom': 'Kit A', 'composants': [
                {'produit': produit_id, 'quantite': 1}]}
        r = self.api.post(url, _payload(self.pb.pk), format='json')
        r_absent = self.api.post(url, _payload(ID_ABSENT), format='json')
        self._assert_comme_absent(r, r_absent, self.pb.pk)
        self.assertFalse(KitProduit.objects.exists())

    def test_kit_sous_kit_etranger(self):
        kit_b = KitProduit.objects.create(company=self.co_b, nom='Kit B')
        url = '/api/django/stock/kits/'

        def _payload(kit_id):
            return {'nom': 'Kit A', 'composants': [
                {'composant_kit': kit_id, 'quantite': 1}]}
        r = self.api.post(url, _payload(kit_b.pk), format='json')
        r_absent = self.api.post(url, _payload(ID_ABSENT), format='json')
        self._assert_comme_absent(r, r_absent, kit_b.pk)
        self.assertEqual(KitProduit.objects.count(), 1)

    def test_produit_entite_bornee_societe(self):
        ser = ProduitSerializer(
            context={'request': SimpleNamespace(user=self.resp_a)})
        self.assertIsInstance(
            ser.fields['entite'], CompanyScopedPrimaryKeyRelatedField)
