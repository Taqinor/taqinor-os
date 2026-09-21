"""NTSCM1 — Modèle PrevisionDemande par article/segment.

Critère d'acceptation : une prévision par produit/segment/mois est créable,
listable et filtrable, scopée par société.

Le produit stock est créé directement via ``apps.stock.models.Produit``
UNIQUEMENT pour construire la fixture de test (setUp) — la production
(``views.py``/``serializers.py``) ne lit le produit QUE via son FK
string-safe ``'stock.Produit'`` (jamais un import de modèle), frontière
cross-app documentée dans CLAUDE.md."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.scm.models import PrevisionDemande
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user, rows


class PrevisionDemandeApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('scm-prev-a', 'Supply A')
        self.co_b = make_company('scm-prev-b', 'Supply B')
        self.admin_a = make_user(self.co_a, 'scm-prev-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'scm-prev-admin-b', 'admin')
        self.produit_a = Produit.objects.create(
            company=self.co_a, nom='Panneau 550W', prix_vente=1200)
        self.produit_b = Produit.objects.create(
            company=self.co_b, nom='Produit société B', prix_vente=500)

    def test_create_list_and_filter_by_produit_segment_periode(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/scm/previsions-demande/', {
            'produit': self.produit_a.id, 'segment': 'residentiel',
            'periode': '2026-09', 'quantite_prevue': '42.50',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['produit_nom'], 'Panneau 550W')

        api.post('/api/django/scm/previsions-demande/', {
            'produit': self.produit_a.id, 'segment': 'industriel',
            'periode': '2026-09', 'quantite_prevue': '10',
        }, format='json')

        resp = api.get(
            '/api/django/scm/previsions-demande/'
            f'?produit={self.produit_a.id}&segment=residentiel')
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['segment'], 'residentiel')

        resp = api.get(
            '/api/django/scm/previsions-demande/'
            '?periode_min=2026-09&periode_max=2026-09')
        self.assertEqual(len(rows(resp)), 2)

    def test_company_scoping_hides_other_tenant_rows(self):
        PrevisionDemande.objects.create(
            company=self.co_b, produit=self.produit_b, periode='2026-09',
            quantite_prevue=5)
        api = auth(self.admin_a)
        resp = api.get('/api/django/scm/previsions-demande/')
        self.assertEqual(rows(resp), [])

    def test_unique_per_company_produit_segment_periode(self):
        PrevisionDemande.objects.create(
            company=self.co_a, produit=self.produit_a, segment='',
            periode='2026-10', quantite_prevue=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PrevisionDemande.objects.create(
                    company=self.co_a, produit=self.produit_a, segment='',
                    periode='2026-10', quantite_prevue=2)

    def test_save_rejects_malformed_periode(self):
        with self.assertRaises(ValueError):
            PrevisionDemande.objects.create(
                company=self.co_a, produit=self.produit_a,
                periode='2026-13', quantite_prevue=1)
