"""AUD213 — le prix d'achat par fournisseur passe par le gate `prix_achat_voir`.

Défaut d'origine : `PrixFournisseurViewSet` gardait ses lectures (et son
export xlsx) avec `IsAnyRole`, et l'action `produits/<id>/prix-fournisseurs/`
retombait sur `IsAdminRole` (un rôle « roles_gerer » sans `prix_achat_voir`
passait donc) — alors que le MÊME champ `prix_achat` est masqué partout
ailleurs par `can_view_buy_prices` (`ProduitSerializer.get_fields`,
`reporting/sav_pivot`, `sav/maintenance`…). Un rôle interne sans la permission
recevait `prix_achat` et les paliers de quantité en clair.

Correctif : `HasPermissionOrLegacy('prix_achat_voir')` sur les lectures +
`export_xlsx` du ViewSet ET sur l'action produit (posée dans `get_permissions`,
qui prime sur le `permission_classes` de l'@action), doublé d'un masquage
serializer (défense en profondeur : `prix_achat` et `paliers` retirés).

Run :
    python manage.py test apps.stock.test_aud213_prix_fournisseur_gate -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.stock.models import (
    Fournisseur, PalierPrixFournisseur, PrixFournisseur, Produit,
)
from apps.stock.serializers import PrixFournisseurSerializer
from authentication.models import Company

User = get_user_model()

URL_LISTE = '/api/django/stock/prix-fournisseurs/'
URL_EXPORT = '/api/django/stock/prix-fournisseurs/export-xlsx/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Aud213Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD213 Co', slug='aud213-co')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau AUD213', sku='AUD213-1',
            prix_achat=Decimal('900'), prix_vente=Decimal('1400'),
            quantite_stock=10)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur AUD213')
        self.prix = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('820.00'))
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=self.prix, qte_min=10, prix=Decimal('780.00'))

    def _user(self, username, permissions):
        role = Role.objects.create(
            company=self.company, nom=f'r-{username}', permissions=permissions)
        return User.objects.create_user(
            username=username, password='x', company=self.company, role=role,
            role_legacy='responsable')


class Aud213ViewSetTests(Aud213Base):
    """Les lectures du ViewSet exigent `prix_achat_voir`."""

    def test_liste_refusee_sans_prix_achat_voir(self):
        user = self._user('aud213_sans', ['stock_voir'])
        rep = _api(user).get(URL_LISTE)
        self.assertEqual(rep.status_code, 403)

    def test_detail_refuse_sans_prix_achat_voir(self):
        user = self._user('aud213_sans_detail', ['stock_voir'])
        rep = _api(user).get(f'{URL_LISTE}{self.prix.pk}/')
        self.assertEqual(rep.status_code, 403)

    def test_export_xlsx_refuse_sans_prix_achat_voir(self):
        user = self._user('aud213_sans_export', ['stock_voir'])
        rep = _api(user).get(
            URL_EXPORT, {'fournisseur': self.fournisseur.pk})
        self.assertEqual(rep.status_code, 403)

    def test_liste_autorisee_avec_prix_achat_voir(self):
        user = self._user('aud213_avec', ['stock_voir', 'prix_achat_voir'])
        rep = _api(user).get(URL_LISTE)
        self.assertEqual(rep.status_code, 200)
        lignes = rep.data['results'] if isinstance(rep.data, dict) else rep.data
        self.assertEqual(len(lignes), 1)
        self.assertIn('prix_achat', lignes[0])
        self.assertEqual(len(lignes[0]['paliers']), 1)


class Aud213ActionProduitTests(Aud213Base):
    """`produits/<id>/prix-fournisseurs/` : même gate que le ViewSet."""

    def _url(self):
        return f'/api/django/stock/produits/{self.produit.pk}/prix-fournisseurs/'

    def test_action_refusee_sans_prix_achat_voir(self):
        # Rôle ADMIN (roles_gerer) mais SANS prix_achat_voir : avant AUD213 le
        # repli `IsAdminRole` le laissait passer et renvoyait les prix en clair.
        user = self._user('aud213_admin_sans', ['roles_gerer', 'stock_voir'])
        rep = _api(user).get(self._url())
        self.assertEqual(rep.status_code, 403)

    def test_action_refusee_pour_role_lecture_seule(self):
        user = self._user('aud213_lecture', ['stock_voir'])
        rep = _api(user).get(self._url())
        self.assertEqual(rep.status_code, 403)

    def test_action_autorisee_avec_prix_achat_voir(self):
        user = self._user('aud213_ok', ['stock_voir', 'prix_achat_voir'])
        rep = _api(user).get(self._url())
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(len(rep.data), 1)
        self.assertEqual(Decimal(str(rep.data[0]['prix_achat'])),
                         Decimal('820.00'))


class Aud213SerializerTests(Aud213Base):
    """Défense en profondeur : le serializer masque le champ lui-même."""

    class _FauxRequest:
        def __init__(self, user):
            self.user = user

    def test_champs_masques_sans_permission(self):
        user = self._user('aud213_ser_sans', ['stock_voir'])
        data = PrixFournisseurSerializer(
            self.prix, context={'request': self._FauxRequest(user)}).data
        self.assertNotIn('prix_achat', data)
        self.assertNotIn('paliers', data)
        # Le reste de la fiche fournisseur reste lisible.
        self.assertEqual(data['fournisseur_nom'], 'Fournisseur AUD213')

    def test_champs_presents_avec_permission(self):
        user = self._user('aud213_ser_avec',
                          ['stock_voir', 'prix_achat_voir'])
        data = PrixFournisseurSerializer(
            self.prix, context={'request': self._FauxRequest(user)}).data
        self.assertIn('prix_achat', data)
        self.assertEqual(len(data['paliers']), 1)

    def test_sans_request_le_comportement_historique_est_conserve(self):
        # Aucun contexte (usage interne/service) : rien n'est masqué.
        data = PrixFournisseurSerializer(self.prix).data
        self.assertIn('prix_achat', data)
