"""NTLOG18 — réserve à réception : une réserve saisie à la livraison crée
automatiquement un `LitigeTransport` « ouvert » avec référence croisée."""
from decimal import Decimal

from django.test import TestCase

from apps.transport.models import (
    EtapeTransport, LitigeTransport, OrdreTransport, ReserveReception,
)

from ._helpers import auth, make_company, make_user

BASE = '/api/django/transport/reserves-reception/'


class ReserveReceptionTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-rr-a', 'A')
        self.co_b = make_company('transport-rr-b', 'B')
        self.user_a = make_user(self.co_a, 'transport-rr-a')
        self.ordre = OrdreTransport.objects.create(company=self.co_a)
        self.etape = EtapeTransport.objects.create(
            company=self.co_a, ordre=self.ordre, sequence=1,
            type_etape=EtapeTransport.TypeEtape.LIVRAISON)

    def test_reserve_cree_automatiquement_un_litige_ouvert(self):
        resp = auth(self.user_a).post(BASE, {
            'etape': self.etape.id, 'nature_reserve': 'Panneau fissuré',
            'montant_estime_dommage': '1500.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        reserve = ReserveReception.objects.get(id=resp.data['id'])
        self.assertIsNotNone(reserve.litige_id)
        self.assertEqual(reserve.litige.statut, LitigeTransport.Statut.OUVERT)
        self.assertEqual(
            reserve.litige.montant_conteste, Decimal('1500.00'))
        self.assertEqual(reserve.litige.ordre_transport_id, self.ordre.id)

    def test_reponse_expose_la_reference_croisee(self):
        resp = auth(self.user_a).post(BASE, {
            'etape': self.etape.id, 'nature_reserve': 'Carton écrasé',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNotNone(resp.data['litige'])

    def test_creation_cross_tenant_etape_refusee(self):
        autre_ordre = OrdreTransport.objects.create(company=self.co_b)
        autre_etape = EtapeTransport.objects.create(
            company=self.co_b, ordre=autre_ordre, sequence=1)
        resp = auth(self.user_a).post(BASE, {
            'etape': autre_etape.id, 'nature_reserve': 'x',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
