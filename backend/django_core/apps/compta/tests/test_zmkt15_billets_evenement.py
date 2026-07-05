"""ZMKT15 — Billets d'événement (types, prix MAD, quotas, fenêtre de vente).

Couvre : définir plusieurs billets, une inscription au-delà du quota est
refusée avec motif, un billet hors fenêtre n'est pas sélectionnable, le
total inscrits par billet est exact, migration additive, tests.
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.compta.models import BilletEvenement, EvenementMarketing


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class BilletsEvenementTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt15', 'ZMKT15')
        self.evt = EvenementMarketing.objects.create(
            company=self.co, nom='Salon', date_debut=timezone.now())

    def test_definir_plusieurs_billets(self):
        BilletEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Standard',
            prix_ttc_mad=Decimal('100'))
        BilletEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='VIP',
            prix_ttc_mad=Decimal('300'))
        self.assertEqual(self.evt.billets.count(), 2)

    def test_inscription_au_dela_du_quota_refusee(self):
        billet = BilletEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Limité',
            prix_ttc_mad=Decimal('50'), quota=1)
        services.inscrire_evenement(self.evt, nom='Premier', billet=billet)
        with self.assertRaises(ValueError):
            services.inscrire_evenement(self.evt, nom='Second', billet=billet)

    def test_billet_hors_fenetre_non_selectionnable(self):
        billet = BilletEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Expiré',
            prix_ttc_mad=Decimal('50'),
            date_fin_vente=timezone.now() - datetime.timedelta(days=1))
        with self.assertRaises(ValueError):
            services.inscrire_evenement(self.evt, nom='Retardataire', billet=billet)

    def test_total_inscrits_par_billet_exact(self):
        billet = BilletEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Standard2',
            prix_ttc_mad=Decimal('80'), quota=10)
        services.inscrire_evenement(self.evt, nom='A', billet=billet)
        services.inscrire_evenement(self.evt, nom='B', billet=billet)
        self.assertEqual(billet.inscriptions.count(), 2)
        self.assertEqual(billet.places_restantes, 8)

    def test_sans_quota_illimite(self):
        billet = BilletEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Illimité',
            prix_ttc_mad=Decimal('0'))
        self.assertIsNone(billet.places_restantes)
        services.inscrire_evenement(self.evt, nom='X', billet=billet)
        self.assertIsNone(billet.places_restantes)

    def test_inscription_sans_billet_toujours_possible(self):
        inscription = services.inscrire_evenement(self.evt, nom='SansBillet')
        self.assertIsNone(inscription.billet)

    def test_endpoint_inscription_publique_billet(self):
        billet = BilletEvenement.objects.create(
            company=self.co, evenement=self.evt, libelle='Public',
            prix_ttc_mad=Decimal('50'), quota=1)
        resp = self.client.post(
            f'/api/django/compta/evenements-marketing/{self.evt.id}/'
            'inscription-publique/',
            data={'nom': 'Test', 'billet_id': billet.id},
            content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        resp2 = self.client.post(
            f'/api/django/compta/evenements-marketing/{self.evt.id}/'
            'inscription-publique/',
            data={'nom': 'Test2', 'billet_id': billet.id},
            content_type='application/json')
        self.assertEqual(resp2.status_code, 400)
