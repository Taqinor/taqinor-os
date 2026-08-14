"""NTLOG1 — ordre de transport : numérotation anti-collision, filtre statut,
création depuis un chantier, isolation multi-société."""
from django.test import TestCase

from apps.transport.models import OrdreTransport

from ._helpers import auth, make_company, make_user

BASE = '/api/django/transport/ordres-transport/'


def _rows(resp):
    """Liste paginée (`StandardPagination` — `{'results': [...]}`) ou liste
    brute selon l'action."""
    return resp.data['results'] if isinstance(resp.data, dict) else resp.data


class OrdreTransportTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-ot-a', 'A')
        self.co_b = make_company('transport-ot-b', 'B')
        self.user_a = make_user(self.co_a, 'transport-ot-a')
        self.user_b = make_user(self.co_b, 'transport-ot-b')

    def _create(self, api, **kw):
        payload = {
            'type_flux': OrdreTransport.TypeFlux.ENLEVEMENT_LIVRAISON,
            'expediteur_nom': 'Dépôt Bouskoura',
            'destinataire_nom': 'Chantier Client X',
        }
        payload.update(kw)
        return api.post(BASE, payload, format='json')

    # ── Numérotation anti-collision (ARC6, jamais count()+1) ─────────────
    def test_numero_attribue_a_la_creation(self):
        resp = self._create(auth(self.user_a))
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['numero'])
        self.assertTrue(resp.data['numero'].startswith('OT-'))

    def test_numeros_sequentiels_uniques(self):
        api = auth(self.user_a)
        r1 = self._create(api)
        r2 = self._create(api)
        self.assertNotEqual(r1.data['numero'], r2.data['numero'])

    def test_numero_non_modifiable_par_le_corps_de_requete(self):
        resp = self._create(auth(self.user_a), numero='FORCE-0001')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotEqual(resp.data['numero'], 'FORCE-0001')

    # ── Filtre statut ──────────────────────────────────────────────────
    def test_filtre_statut(self):
        api = auth(self.user_a)
        r1 = self._create(api)
        OrdreTransport.objects.filter(id=r1.data['id']).update(
            statut=OrdreTransport.Statut.PLANIFIE)
        self._create(api)  # reste brouillon
        resp = api.get(BASE, {'statut': 'planifie'})
        self.assertEqual(resp.status_code, 200)
        ids = [row['id'] for row in _rows(resp)]
        self.assertIn(r1.data['id'], ids)
        self.assertEqual(len(ids), 1)

    # ── Se crée depuis un chantier (string-FK) ────────────────────────────
    def test_creation_depuis_un_chantier(self):
        resp = self._create(
            auth(self.user_a), installations_installation_id=42)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['installations_installation_id'], 42)

    # ── Isolation multi-société ────────────────────────────────────────
    def test_liste_isolee_par_societe(self):
        self._create(auth(self.user_a))
        resp = auth(self.user_b).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(_rows(resp)), 0)

    def test_detail_cross_tenant_404(self):
        ordre_id = self._create(auth(self.user_a)).data['id']
        resp = auth(self.user_b).get(f'{BASE}{ordre_id}/')
        self.assertEqual(resp.status_code, 404)
