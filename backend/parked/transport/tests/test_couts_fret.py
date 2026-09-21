"""NTLOG16 — coûts de fret réels ventilés + selector unique consommable par
le landed cost FG316/DC38 (`apps.stock`), jamais de calcul dupliqué."""
from decimal import Decimal

from django.test import TestCase

from apps.transport import selectors
from apps.transport.models import CoutFretReel, OrdreTransport

from ._helpers import auth, make_company, make_user

BASE = '/api/django/transport/couts-fret/'


class CoutsFretReelsTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-cfr-a', 'A')
        self.co_b = make_company('transport-cfr-b', 'B')
        self.user_a = make_user(self.co_a, 'transport-cfr-a')
        self.ordre = OrdreTransport.objects.create(company=self.co_a)

    def test_selector_somme_les_couts_du_meme_bcf(self):
        CoutFretReel.objects.create(
            company=self.co_a, ordre_transport=self.ordre,
            montant_ht=Decimal('500.00'), stock_boncommandefournisseur_id=99,
            type_cout=CoutFretReel.TypeCout.TRANSPORT)
        CoutFretReel.objects.create(
            company=self.co_a, ordre_transport=self.ordre,
            montant_ht=Decimal('120.00'), stock_boncommandefournisseur_id=99,
            type_cout=CoutFretReel.TypeCout.DEDOUANEMENT)
        # Un autre BCF, jamais compté.
        CoutFretReel.objects.create(
            company=self.co_a, ordre_transport=self.ordre,
            montant_ht=Decimal('999.00'), stock_boncommandefournisseur_id=1)

        total = selectors.frais_transport_pour_landed_cost(self.co_a, 99)
        self.assertEqual(total, Decimal('620.00'))

    def test_selector_isole_par_societe(self):
        CoutFretReel.objects.create(
            company=self.co_a, ordre_transport=self.ordre,
            montant_ht=Decimal('500.00'), stock_boncommandefournisseur_id=99)
        total_b = selectors.frais_transport_pour_landed_cost(self.co_b, 99)
        self.assertEqual(total_b, Decimal('0'))

    def test_selector_sans_cout_renvoie_zero(self):
        total = selectors.frais_transport_pour_landed_cost(self.co_a, 12345)
        self.assertEqual(total, Decimal('0'))

    def test_endpoint_creation_et_filtre_par_ordre(self):
        api = auth(self.user_a)
        resp = api.post(BASE, {
            'ordre_transport': self.ordre.id, 'montant_ht': '250.00',
            'type_cout': CoutFretReel.TypeCout.MANUTENTION,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = api.get(BASE, {'ordre_transport': self.ordre.id})
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 1)

    def test_creation_cross_tenant_ordre_refusee(self):
        autre_ordre = OrdreTransport.objects.create(company=self.co_b)
        resp = auth(self.user_a).post(BASE, {
            'ordre_transport': autre_ordre.id, 'montant_ht': '10.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
