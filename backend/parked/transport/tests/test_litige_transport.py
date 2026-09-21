"""NTLOG17 — litiges transport : machine à états calquée sur
`litiges.Reclamation` (LITIGE2) — ouvert → en_traitement → résolu, ou
rejeté depuis ouvert/en_traitement ; transition illégale → 400."""
from django.test import TestCase

from apps.transport.models import LitigeTransport, OrdreTransport

from ._helpers import auth, make_company, make_user

BASE = '/api/django/transport/litiges-transport/'


class LitigeTransportWorkflowTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-lt-a', 'A')
        self.co_b = make_company('transport-lt-b', 'B')
        self.user_a = make_user(self.co_a, 'transport-lt-a')
        self.user_b = make_user(self.co_b, 'transport-lt-b')
        self.ordre = OrdreTransport.objects.create(company=self.co_a)

    def _make(self, **kw):
        defaults = {'company': self.co_a, 'ordre_transport': self.ordre}
        defaults.update(kw)
        return LitigeTransport.objects.create(**defaults)

    def test_default_statut_ouvert(self):
        litige = self._make()
        self.assertEqual(litige.statut, LitigeTransport.Statut.OUVERT)

    # ── Transitions légales ───────────────────────────────────────────
    def test_prendre_en_charge_ouvert_to_en_traitement(self):
        litige = self._make()
        resp = auth(self.user_a).post(f'{BASE}{litige.id}/prendre-en-charge/')
        self.assertEqual(resp.status_code, 200, resp.data)
        litige.refresh_from_db()
        self.assertEqual(litige.statut, LitigeTransport.Statut.EN_TRAITEMENT)

    def test_resoudre_en_traitement_to_resolu(self):
        litige = self._make(statut=LitigeTransport.Statut.EN_TRAITEMENT)
        resp = auth(self.user_a).post(f'{BASE}{litige.id}/resoudre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        litige.refresh_from_db()
        self.assertEqual(litige.statut, LitigeTransport.Statut.RESOLU)

    def test_rejeter_from_ouvert(self):
        litige = self._make()
        resp = auth(self.user_a).post(f'{BASE}{litige.id}/rejeter/')
        self.assertEqual(resp.status_code, 200, resp.data)
        litige.refresh_from_db()
        self.assertEqual(litige.statut, LitigeTransport.Statut.REJETE)

    # ── Transitions illégales (400) ───────────────────────────────────
    def test_resoudre_from_ouvert_refuse(self):
        litige = self._make()
        resp = auth(self.user_a).post(f'{BASE}{litige.id}/resoudre/')
        self.assertEqual(resp.status_code, 400)
        litige.refresh_from_db()
        self.assertEqual(litige.statut, LitigeTransport.Statut.OUVERT)

    def test_prendre_en_charge_from_resolu_refuse(self):
        litige = self._make(statut=LitigeTransport.Statut.RESOLU)
        resp = auth(self.user_a).post(f'{BASE}{litige.id}/prendre-en-charge/')
        self.assertEqual(resp.status_code, 400)

    def test_rejeter_from_resolu_refuse(self):
        litige = self._make(statut=LitigeTransport.Statut.RESOLU)
        resp = auth(self.user_a).post(f'{BASE}{litige.id}/rejeter/')
        self.assertEqual(resp.status_code, 400)

    # ── Isolation multi-société ────────────────────────────────────────
    def test_transition_cross_tenant_404(self):
        litige = self._make()
        resp = auth(self.user_b).post(f'{BASE}{litige.id}/prendre-en-charge/')
        self.assertEqual(resp.status_code, 404)

    def test_statut_non_modifiable_par_patch_direct(self):
        litige = self._make()
        resp = auth(self.user_a).patch(
            f'{BASE}{litige.id}/', {'statut': LitigeTransport.Statut.RESOLU},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        litige.refresh_from_db()
        self.assertEqual(litige.statut, LitigeTransport.Statut.OUVERT)

    def test_creation_cross_tenant_ordre_refusee(self):
        autre_ordre = OrdreTransport.objects.create(company=self.co_b)
        resp = auth(self.user_a).post(BASE, {
            'ordre_transport': autre_ordre.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
