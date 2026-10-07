"""ASTK3 (C-ASTK-001) — une expédition transporteur ne traverse plus la
frontière société.

Sonde WMS-6 d'origine : un responsable de A PATCH son expédition vers une
unité scellée de B (200), puis ``generer-etiquette`` (200) sortait 3 × PB du
stock de B (5 → 2) avec un ``MouvementStock(company=A, produit=PB)``.

Désormais : le PATCH répond 400 « objet inexistant » (même code qu'un id
99999999) et ``decrementer_stock_expedition`` relit chaque produit borné à
la société de l'expédition — aucune ligne étrangère n'est jamais décomptée.

Seul le dépôt MinIO de l'étiquette est simulé (``_stocker_etiquette``) ; le
connecteur NoOp et le décrément sont réels.

Run :
    python manage.py test apps.stock.test_astk_fk_expedition -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import MouvementStock, Produit
from apps.stock.models_wms import (
    ExpeditionTransporteur, UniteLogistique, UniteLogistiqueLigne,
)
from apps.stock.services import (
    ajouter_ligne_unite_logistique, creer_expedition_transporteur,
    creer_unite_logistique, sceller_unite_logistique,
)

User = get_user_model()

STOCKER = 'apps.stock.services_wms._stocker_etiquette'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class FkExpeditionTests(TestCase):
    def setUp(self):
        self.a = make_company('astk3-a', 'ASTK3 A')
        self.b = make_company('astk3-b', 'ASTK3 B')
        self.resp_a = User.objects.create_user(
            username='astk3_resp_a', password='x', role_legacy='responsable',
            company=self.a)
        self.resp_b = User.objects.create_user(
            username='astk3_resp_b', password='x', role_legacy='responsable',
            company=self.b)
        self.pa = Produit.objects.create(
            company=self.a, nom='ProdA', sku='ASTK3-PA',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=10)
        self.pb = Produit.objects.create(
            company=self.b, nom='ProdB-secret', sku='ASTK3-PB',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=5)
        # Unité scellée de A + son expédition.
        self.ua = creer_unite_logistique(company=self.a)
        ajouter_ligne_unite_logistique(
            company=self.a, unite=self.ua, produit=self.pa, quantite=1)
        sceller_unite_logistique(unite=self.ua, user=self.resp_a)
        self.expedition = creer_expedition_transporteur(
            company=self.a, unite=self.ua)
        # Unité scellée de B contenant 3 × PB.
        self.ub = creer_unite_logistique(company=self.b)
        ajouter_ligne_unite_logistique(
            company=self.b, unite=self.ub, produit=self.pb, quantite=3)
        sceller_unite_logistique(unite=self.ub, user=self.resp_b)
        self.client_a = auth_client(self.resp_a)
        self.url = f'/api/django/stock/expeditions/{self.expedition.id}/'

    def _stock_pb(self):
        self.pb.refresh_from_db()
        return self.pb.quantite_stock

    def _mouvements_pb(self):
        return MouvementStock.objects.filter(produit=self.pb).count()

    def test_patch_unite_logistique_etrangere_refuse(self):
        mvts_avant = self._mouvements_pb()
        r = self.client_a.patch(
            self.url, {'unite_logistique': self.ub.id}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        inconnu = self.client_a.patch(
            self.url, {'unite_logistique': 99999999}, format='json')
        self.assertEqual(inconnu.status_code, 400, inconnu.content)
        # Indiscernable d'un id inexistant : même code d'erreur DRF.
        self.assertEqual(r.data['unite_logistique'][0].code,
                         inconnu.data['unite_logistique'][0].code)
        self.assertEqual(r.data['unite_logistique'][0].code, 'does_not_exist')

        with mock.patch(STOCKER, return_value='stock/x/etiquettes/t.pdf'):
            etiquette = self.client_a.post(f'{self.url}generer-etiquette/')
        self.assertEqual(etiquette.status_code, 200, etiquette.content)

        # Persistance relue.
        self.expedition.refresh_from_db()
        self.assertEqual(self.expedition.unite_logistique_id, self.ua.id)
        self.assertEqual(self._stock_pb(), 5)
        self.assertEqual(self._mouvements_pb(), mvts_avant)
        self.assertFalse(MouvementStock.objects.filter(
            company=self.a, produit=self.pb).exists())

    def test_etiquette_ne_decremente_pas_autre_societe(self):
        """Lignes étrangères injectées en base (état hérité d'avant la
        borne) : le décrément refuse au lieu de sortir le stock de B."""
        mvts_avant = self._mouvements_pb()
        # (1) une unité étrangère rattachée directement en base.
        ExpeditionTransporteur.objects.filter(pk=self.expedition.pk).update(
            unite_logistique=self.ub)
        with mock.patch(STOCKER, return_value='stock/x/etiquettes/t.pdf'):
            r = self.client_a.post(f'{self.url}generer-etiquette/')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(self._stock_pb(), 5)
        self.assertEqual(self._mouvements_pb(), mvts_avant)

        # (2) une ligne de produit étranger injectée dans l'unité de A.
        ua2 = creer_unite_logistique(company=self.a)
        UniteLogistiqueLigne.objects.create(
            company=self.a, unite=ua2, produit=self.pb, quantite=3)
        UniteLogistique.objects.filter(pk=ua2.pk).update(
            statut=UniteLogistique.Statut.SCELLE)
        ua2.refresh_from_db()
        exp2 = creer_expedition_transporteur(company=self.a, unite=ua2)
        with mock.patch(STOCKER, return_value='stock/x/etiquettes/t.pdf'):
            r2 = self.client_a.post(
                f'/api/django/stock/expeditions/{exp2.id}/generer-etiquette/')
        self.assertEqual(r2.status_code, 400, r2.content)
        self.assertEqual(self._stock_pb(), 5)
        self.assertEqual(self._mouvements_pb(), mvts_avant)
        self.assertFalse(MouvementStock.objects.filter(
            company=self.a, produit=self.pb).exists())
