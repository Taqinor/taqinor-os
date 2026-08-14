"""NTLOG3 — étapes de transport : avancement automatique du statut de
l'ordre quand une étape est marquée « fait »."""
from django.test import TestCase

from apps.transport.models import EtapeTransport, OrdreTransport

from ._helpers import auth, make_company, make_user

ETAPES_BASE = '/api/django/transport/etapes-transport/'


class EtapeTransportTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-et-a', 'A')
        self.co_b = make_company('transport-et-b', 'B')
        self.user_a = make_user(self.co_a, 'transport-et-a')
        self.user_b = make_user(self.co_b, 'transport-et-b')
        self.ordre = OrdreTransport.objects.create(
            company=self.co_a, statut=OrdreTransport.Statut.PLANIFIE)
        self.e1 = EtapeTransport.objects.create(
            company=self.co_a, ordre=self.ordre, sequence=1,
            type_etape=EtapeTransport.TypeEtape.ENLEVEMENT)
        self.e2 = EtapeTransport.objects.create(
            company=self.co_a, ordre=self.ordre, sequence=2,
            type_etape=EtapeTransport.TypeEtape.LIVRAISON)

    def _patch_statut(self, api, etape, statut):
        return api.patch(
            f'{ETAPES_BASE}{etape.id}/', {'statut_etape': statut},
            format='json')

    # ── Avancement automatique du statut de l'ordre ───────────────────────
    def test_premiere_etape_faite_passe_ordre_en_cours(self):
        api = auth(self.user_a)
        resp = self._patch_statut(
            api, self.e1, EtapeTransport.StatutEtape.FAIT)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.statut, OrdreTransport.Statut.EN_COURS)

    def test_toutes_etapes_faites_passe_ordre_livre(self):
        api = auth(self.user_a)
        self._patch_statut(api, self.e1, EtapeTransport.StatutEtape.FAIT)
        self._patch_statut(api, self.e2, EtapeTransport.StatutEtape.FAIT)
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.statut, OrdreTransport.Statut.LIVRE)

    def test_etape_incident_ne_livre_pas_l_ordre(self):
        api = auth(self.user_a)
        self._patch_statut(api, self.e1, EtapeTransport.StatutEtape.FAIT)
        self._patch_statut(api, self.e2, EtapeTransport.StatutEtape.INCIDENT)
        self.ordre.refresh_from_db()
        self.assertNotEqual(self.ordre.statut, OrdreTransport.Statut.LIVRE)

    def test_lecture_imbriquee_des_etapes(self):
        resp = auth(self.user_a).get(
            f'/api/django/transport/ordres-transport/{self.ordre.id}/etapes/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    # ── Isolation multi-société ────────────────────────────────────────
    def test_etape_cross_tenant_404(self):
        resp = auth(self.user_b).patch(
            f'{ETAPES_BASE}{self.e1.id}/', {'statut_etape': 'fait'},
            format='json')
        self.assertEqual(resp.status_code, 404)
