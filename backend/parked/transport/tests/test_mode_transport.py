"""NTLOG4 — affectation flotte propre vs affrètement : un ordre en
affrètement ne peut pas être affecté à un véhicule/conducteur interne
(validation serveur), et réciproquement pour la flotte propre."""
from django.test import TestCase

from apps.transport.models import OrdreTransport

from ._helpers import auth, make_company, make_user

BASE = '/api/django/transport/ordres-transport/'


class ModeTransportTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-mt-a', 'A')
        self.user_a = make_user(self.co_a, 'transport-mt-a')

    def test_affretement_avec_actif_flotte_refuse(self):
        resp = auth(self.user_a).post(BASE, {
            'mode_transport': OrdreTransport.ModeTransport.AFFRETEMENT,
            'flotte_actif_id': 7,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('mode_transport', resp.data)

    def test_affretement_avec_conducteur_refuse(self):
        conducteur = make_user(self.co_a, 'transport-mt-conducteur')
        resp = auth(self.user_a).post(BASE, {
            'mode_transport': OrdreTransport.ModeTransport.AFFRETEMENT,
            'conducteur': conducteur.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_affretement_avec_transporteur_seul_accepte(self):
        resp = auth(self.user_a).post(BASE, {
            'mode_transport': OrdreTransport.ModeTransport.AFFRETEMENT,
            'installations_transporteur_id': 3,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_flotte_propre_avec_transporteur_tiers_refuse(self):
        resp = auth(self.user_a).post(BASE, {
            'mode_transport': OrdreTransport.ModeTransport.FLOTTE_PROPRE,
            'installations_transporteur_id': 3,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_flotte_propre_avec_actif_seul_accepte(self):
        resp = auth(self.user_a).post(BASE, {
            'mode_transport': OrdreTransport.ModeTransport.FLOTTE_PROPRE,
            'flotte_actif_id': 7,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_bascule_vers_affretement_avec_actif_deja_pose_refusee(self):
        ordre = OrdreTransport.objects.create(
            company=self.co_a,
            mode_transport=OrdreTransport.ModeTransport.FLOTTE_PROPRE,
            flotte_actif_id=7)
        resp = auth(self.user_a).patch(
            f'{BASE}{ordre.id}/',
            {'mode_transport': OrdreTransport.ModeTransport.AFFRETEMENT},
            format='json')
        self.assertEqual(resp.status_code, 400)
        ordre.refresh_from_db()
        self.assertEqual(
            ordre.mode_transport, OrdreTransport.ModeTransport.FLOTTE_PROPRE)
