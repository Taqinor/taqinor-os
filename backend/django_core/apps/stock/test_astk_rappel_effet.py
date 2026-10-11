"""ASTK199 (C-ASTK-048, volet WMS-11) — un rappel produit/lot MET EN
QUARANTAINE le stock restant du lot (ou du produit) rappelé ; le plan de
picking FEFO n'en propose plus rien ; une sortie sur ce lot est refusée ; la
clôture du rappel lève ses blocages (idempotent).

Sonde WMS-11 d'origine : rappel 201, blocages créés 0, plan FEFO proposait
LOT-RAPPEL, sortie du lot 200.

Aucun mock : vues, services WMS et sélecteurs réels.

Run :
    python manage.py test apps.stock.test_astk_rappel_effet -v 2
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Categorie, LotEntrepot, Produit
from apps.stock.models_wms import BlocageQualite
from apps.stock.selectors_wms import resoudre_allocation_picking

User = get_user_model()

URL = '/api/django/stock/alertes-rappel/'
CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'wms_rappels_qualite.json')


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RappelTests(TestCase):
    def setUp(self):
        self.co = make_company('astk199-co', 'ASTK199 Co')
        self.admin = User.objects.create_user(
            username='astk199_admin', password='x', role_legacy='admin',
            company=self.co)
        self.api = auth(self.admin)
        categorie = Categorie.objects.create(
            company=self.co, nom='Batteries ASTK199',
            strategie_picking_defaut=Categorie.StrategiePicking.FEFO)
        self.produit = Produit.objects.create(
            company=self.co, nom='Batterie ASTK199', sku='ASTK199-1',
            categorie=categorie, prix_achat=Decimal('100'),
            prix_vente=Decimal('200'), quantite_stock=15)
        # LOT-RAPPEL périme le premier : FEFO le proposerait d'abord.
        self.lot_rappel = LotEntrepot.objects.create(
            company=self.co, produit=self.produit, numero_lot='LOT-RAPPEL',
            date_peremption=datetime.date(2027, 1, 1),
            quantite_recue=10, quantite_restante=10)
        self.lot_sain = LotEntrepot.objects.create(
            company=self.co, produit=self.produit, numero_lot='LOT-SAIN',
            date_peremption=datetime.date(2028, 1, 1),
            quantite_recue=5, quantite_restante=5)

    def _declarer(self, lot=True):
        corps = {'produit': self.produit.id, 'motif': 'Défaut cellule'}
        if lot:
            corps['lot'] = self.lot_rappel.id
        rep = self.api.post(URL, corps, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        return rep

    def _actifs(self):
        return BlocageQualite.objects.filter(
            company=self.co, produit=self.produit,
            statut=BlocageQualite.Statut.EN_QUARANTAINE)

    def test_rappel_cree_le_blocage(self):
        rep = self._declarer()
        actifs = self._actifs()
        self.assertEqual(actifs.count(), 1)
        blocage = actifs.get()
        self.assertEqual(blocage.quantite, 10)
        self.assertEqual(blocage.lot_id, self.lot_rappel.id)
        self.assertEqual(rep.json()['blocages'], [{
            'id': blocage.id, 'quantite': 10, 'lot': self.lot_rappel.id,
            'statut': 'en_quarantaine'}])
        # Rouvrir l'alerte → mêmes blocages (persistance).
        relu = self.api.get(f'{URL}{rep.json()["id"]}/')
        self.assertEqual(relu.json()['blocages'], rep.json()['blocages'])

    def test_rappel_produit_bloque_chaque_lot(self):
        self._declarer(lot=False)
        actifs = self._actifs()
        self.assertEqual(
            sorted(actifs.values_list('lot__numero_lot', 'quantite')),
            [('LOT-RAPPEL', 10), ('LOT-SAIN', 5)])

    def test_picking_exclut_lot_rappele(self):
        avant = resoudre_allocation_picking(self.produit, 3)
        self.assertEqual(avant[0]['numero_lot'], 'LOT-RAPPEL')
        self._declarer()
        plan = resoudre_allocation_picking(self.produit, 8)
        self.assertEqual([ligne['numero_lot'] for ligne in plan],
                         ['LOT-SAIN'])
        self.assertEqual(plan[0]['quantite'], 5)
        # Sortie du lot rappelé → 400 nommant le lot ; aucun stock ne bouge.
        rep = self.api.post(
            f'/api/django/stock/lots-entrepot/{self.lot_rappel.id}/sortir/',
            {'quantite': 1}, format='json')
        self.assertEqual(rep.status_code, 400, rep.content)
        self.assertIn('LOT-RAPPEL', rep.json()['detail'])
        self.lot_rappel.refresh_from_db()
        self.produit.refresh_from_db()
        self.assertEqual(self.lot_rappel.quantite_restante, 10)
        self.assertEqual(self.produit.quantite_stock, 15)

    def test_cloture_leve_les_blocages(self):
        rep = self._declarer()
        alerte_id = rep.json()['id']
        clos = self.api.post(f'{URL}{alerte_id}/cloturer/')
        self.assertEqual(clos.status_code, 200, clos.content)
        self.assertEqual(self._actifs().count(), 0)
        self.assertEqual(
            [b['statut'] for b in clos.json()['blocages']], ['levee'])
        # Idempotent : une seconde clôture ne recrée ni ne relève rien.
        again = self.api.post(f'{URL}{alerte_id}/cloturer/')
        self.assertEqual(again.status_code, 200)
        self.assertEqual(BlocageQualite.objects.filter(
            company=self.co, produit=self.produit).count(), 1)
        plan = resoudre_allocation_picking(self.produit, 3)
        self.assertEqual(plan[0]['numero_lot'], 'LOT-RAPPEL')

    def test_sorties_hors_lot_respectent_la_quarantaine(self):
        """ASTK248 — rejoue la sonde C-ASTK-VER-004 : stock 15 dont 10
        rappelés. Une SORTIE de 12 est refusée (400 / ValueError nommant le
        produit et les 10 unités) par le poste scanner, le mouvement manuel et
        la confirmation d'expédition : stock 15, aucun mouvement. Une sortie de
        5 passe ; après levée du rappel, l'expédition (part bloquée comprise)
        passe."""
        from unittest import mock
        from apps.stock.models import MouvementStock
        from apps.stock.providers import NoOpProvider
        from apps.stock.services import (
            ajouter_ligne_unite_logistique, creer_expedition_transporteur,
            creer_unite_logistique, generer_etiquette_expedition,
            sceller_unite_logistique,
        )
        alerte_id = self._declarer().json()['id']
        colis = creer_unite_logistique(company=self.co)
        ajouter_ligne_unite_logistique(
            company=self.co, unite=colis, produit=self.produit, quantite=12)
        sceller_unite_logistique(unite=colis, user=self.admin)
        expedition = creer_expedition_transporteur(company=self.co, unite=colis)
        corps = {'produit': self.produit.id, 'type_mouvement': 'sortie',
                 'quantite': 12}
        for url in ('/api/django/stock/scanner/mouvement/',
                    '/api/django/stock/mouvements/'):
            rep = self.api.post(url, corps, format='json')
            self.assertEqual(rep.status_code, 400, rep.content)
            self.assertIn('Batterie ASTK199', str(rep.json()))
            self.assertIn('10 unité(s) en quarantaine', str(rep.json()))
        with mock.patch.object(NoOpProvider, 'creer_expedition',
                               return_value=('INT-ASTK248', b'')):
            with self.assertRaisesMessage(ValueError, '10 unité(s) en quarantaine'):
                generer_etiquette_expedition(expedition=expedition, user=self.admin)
            self.produit.refresh_from_db()
            self.assertEqual(self.produit.quantite_stock, 15)
            self.assertFalse(
                MouvementStock.objects.filter(produit=self.produit).exists())
            rep = self.api.post('/api/django/stock/mouvements/',
                                {**corps, 'quantite': 5}, format='json')
            self.assertEqual(rep.status_code, 201, rep.content)
            self.assertEqual(
                self.api.post(f'{URL}{alerte_id}/cloturer/').status_code, 200)
            generer_etiquette_expedition(expedition=expedition, user=self.admin)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)

    def test_reponse_conforme_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        route = contrat['routes']['alertes_rappel']
        rep = self._declarer()
        self.assertEqual(sorted(rep.json()), sorted(route['exemple_element']))
        self.assertEqual(sorted(rep.json()['blocages'][0]),
                         sorted(route['exemple_element']['blocages'][0]))
        clos = self.api.post(f'{URL}{rep.json()["id"]}/cloturer/')
        self.assertEqual(
            sorted(clos.json()),
            sorted(contrat['routes']['alertes_rappel_cloturer']['exemple']))
