"""Tests NTAGR6 — Garde bloquante DAR (délai avant récolte).

Couvre : un traitement phyto dont le DAR dépasse la date de récolte prévue
est refusé à la création, un traitement conforme passe, le cas sans DAR
défini sur l'intrant (pas de blocage), et le cas d'une saisie a posteriori
qui violerait le DAR compte tenu d'une date de récolte réelle plus proche que
la date prévue.
"""
from django.test import TestCase

from apps.agriculture.models import (
    CampagneCulturale, Exploitation, IntrantAgricole, Parcelle,
)
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user


class DarGuardApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('agr-dar-a', 'Ferme DAR A')
        self.admin_a = make_user(self.co_a, 'agr-dar-admin-a', 'admin')
        exploitation = Exploitation.objects.create(
            company=self.co_a, nom='Domaine')
        self.parcelle = Parcelle.objects.create(
            company=self.co_a, exploitation=exploitation, nom='Parcelle 1')
        self.campagne = CampagneCulturale.objects.create(
            company=self.co_a, parcelle=self.parcelle, culture='Tomate',
            statut='en_cours', date_recolte_prevue='2026-06-01')
        produit = Produit.objects.create(
            company=self.co_a, nom='Fongicide X', prix_vente=120)
        self.intrant_phyto = IntrantAgricole.objects.create(
            company=self.co_a, produit_id=produit.id, categorie='phyto',
            delai_avant_recolte_jours=21, matiere_active='Cuivre',
            numero_amm='AMM-1234')

    def test_treatment_beyond_dar_is_rejected(self):
        # 2026-05-25 + 21 j = 2026-06-15 > 2026-06-01 (récolte prévue) → refus.
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/etapes-campagne/', {
            'campagne': self.campagne.id, 'type_etape': 'traitement',
            'date': '2026-05-25', 'intrant': self.intrant_phyto.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('date', resp.data)
        message = str(resp.data['date'])
        self.assertIn('21', message)

    def test_compliant_treatment_passes(self):
        # 2026-05-01 + 21 j = 2026-05-22 <= 2026-06-01 → conforme.
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/etapes-campagne/', {
            'campagne': self.campagne.id, 'type_etape': 'traitement',
            'date': '2026-05-01', 'intrant': self.intrant_phyto.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_no_dar_defined_never_blocks(self):
        produit = Produit.objects.create(
            company=self.co_a, nom='Fongicide sans DAR', prix_vente=90)
        intrant_sans_dar = IntrantAgricole.objects.create(
            company=self.co_a, produit_id=produit.id, categorie='phyto')
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/etapes-campagne/', {
            'campagne': self.campagne.id, 'type_etape': 'traitement',
            'date': '2026-05-31', 'intrant': intrant_sans_dar.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_late_entry_against_actual_harvest_date_blocked(self):
        # date_recolte_reelle plus proche que date_recolte_prevue : une
        # saisie a posteriori qui violerait le DAR par rapport à la
        # récolte RÉELLE est bloquée même si elle respectait la prévision.
        self.campagne.date_recolte_reelle = '2026-05-10'
        self.campagne.save(update_fields=['date_recolte_reelle'])

        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/etapes-campagne/', {
            'campagne': self.campagne.id, 'type_etape': 'traitement',
            'date': '2026-04-25', 'intrant': self.intrant_phyto.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_non_traitement_step_never_blocked(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/etapes-campagne/', {
            'campagne': self.campagne.id, 'type_etape': 'irrigation',
            'date': '2026-06-05',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
