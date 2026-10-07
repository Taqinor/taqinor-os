"""ASTK51 (C-ASTK-010) — valider un retour fournisseur scanné est UNE
transaction qui contrôle d'abord le statut : un second clic ne pose aucun
transfert fantôme.

Sonde WMS-15 d'origine : 1er POST valider-scanne → 200, 2e → 400 (« seul un
retour en brouillon… ») MAIS 2 mouvements TRANSFERT vers la zone de départs
(1 attendu) : le déplacement était posé AVANT le contrôle d'état, hors
transaction.

Aucun mock : services et vues réels.

Run :
    python manage.py test apps.stock.test_astk_retour_scanne -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, Fournisseur, LigneRetourFournisseur, MouvementStock,
    Produit, RetourFournisseur,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class RetourScanneTests(TestCase):
    def setUp(self):
        from apps.installations.models import BinLocation

        self.co = make_company('astk51-co', 'ASTK51 Co')
        self.resp = User.objects.create_user(
            username='astk51_resp', password='x', role_legacy='responsable',
            company=self.co)
        emp = EmplacementStock.objects.create(
            company=self.co, nom='Dépôt ASTK51', is_principal=True)
        self.casier_departs = BinLocation.objects.create(
            company=self.co, emplacement=emp, code='EXP-01', ordre=990)
        fournisseur = Fournisseur.objects.create(
            company=self.co, nom='Fournisseur ASTK51')
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur ASTK51', sku='ASTK51-1',
            fournisseur=fournisseur, prix_achat=Decimal('100'),
            prix_vente=Decimal('150'), quantite_stock=10)
        self.retour = RetourFournisseur.objects.create(
            company=self.co, reference='RET-ASTK51-0001',
            fournisseur=fournisseur)
        LigneRetourFournisseur.objects.create(
            retour=self.retour, produit=self.produit, quantite=1,
            motif='Défaut')
        self.url = (f'/api/django/stock/retours-fournisseur/'
                    f'{self.retour.id}/valider-scanne/')

    def _transferts(self):
        return MouvementStock.objects.filter(
            company=self.co, reference='RET-ASTK51-0001',
            type_mouvement=MouvementStock.TypeMouvement.TRANSFERT)

    def test_double_validation_un_seul_transfert(self):
        api = auth_client(self.resp)
        premier = api.post(self.url, {'bins_source': {}}, format='json')
        self.assertEqual(premier.status_code, 200, premier.content)
        second = api.post(self.url, {'bins_source': {}}, format='json')
        self.assertEqual(second.status_code, 400, second.content)
        self.assertIn('brouillon', second.data['detail'])
        # Persistance relue : UN seul transfert vers la zone de départs.
        self.assertEqual(self._transferts().count(), 1)
        self.assertEqual(self._transferts().get().bin_destination_id,
                         self.casier_departs.id)
        self.retour.refresh_from_db()
        self.assertEqual(self.retour.statut, RetourFournisseur.Statut.VALIDE)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 9)
