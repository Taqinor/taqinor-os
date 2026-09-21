"""NTHOT18 — Salles événementielles.

Done = un conflit de réservation de salle est refusé (400), tests.
"""
from django.test import TestCase

from apps.hospitality.models import EvenementBanquet, SalleEvenement

from .helpers import auth, make_company, make_user


class SalleEvenementApiTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-salle', 'Hôtel')
        self.resp = make_user(self.co, 'hot-salle-resp', role='responsable')
        self.salle = SalleEvenement.objects.create(
            company=self.co, nom='Salle Atlas', capacite_max=150,
            types_amenagement_disponibles=['banquet', 'theatre'],
            tarif_location_ht='5000.00')

    def test_creer_salle(self):
        resp = auth(self.resp).post(
            '/api/django/hospitality/salles-evenement/',
            {
                'nom': 'Salle Palmeraie', 'capacite_max': 80,
                'types_amenagement_disponibles': ['cocktail'],
                'tarif_location_ht': '3000.00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)

    def test_evenement_confirme_sans_conflit_est_accepte(self):
        resp = auth(self.resp).post(
            '/api/django/hospitality/evenements/',
            {
                'nom_evenement': 'Mariage Hassan', 'salle': self.salle.pk,
                'date_debut': '2026-09-01T10:00:00Z',
                'date_fin': '2026-09-01T22:00:00Z',
                'nb_convives': 100, 'statut': 'confirme',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)

    def test_conflit_reservation_salle_refuse_400(self):
        EvenementBanquet.objects.create(
            company=self.co, nom_evenement='Événement A', salle=self.salle,
            date_debut='2026-09-01T10:00:00Z', date_fin='2026-09-01T22:00:00Z',
            statut=EvenementBanquet.Statut.CONFIRME,
        )
        resp = auth(self.resp).post(
            '/api/django/hospitality/evenements/',
            {
                'nom_evenement': 'Événement B', 'salle': self.salle.pk,
                'date_debut': '2026-09-01T18:00:00Z',
                'date_fin': '2026-09-02T02:00:00Z',
                'nb_convives': 50, 'statut': 'confirme',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('salle', resp.data)

    def test_brouillon_ne_bloque_jamais_la_salle(self):
        EvenementBanquet.objects.create(
            company=self.co, nom_evenement='Brouillon A', salle=self.salle,
            date_debut='2026-09-01T10:00:00Z', date_fin='2026-09-01T22:00:00Z',
            statut=EvenementBanquet.Statut.BROUILLON,
        )
        resp = auth(self.resp).post(
            '/api/django/hospitality/evenements/',
            {
                'nom_evenement': 'Événement B', 'salle': self.salle.pk,
                'date_debut': '2026-09-01T10:00:00Z',
                'date_fin': '2026-09-01T22:00:00Z',
                'nb_convives': 50, 'statut': 'confirme',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)

    def test_update_reapplique_la_garde_de_chevauchement(self):
        EvenementBanquet.objects.create(
            company=self.co, nom_evenement='Événement A', salle=self.salle,
            date_debut='2026-09-01T10:00:00Z', date_fin='2026-09-01T22:00:00Z',
            statut=EvenementBanquet.Statut.CONFIRME,
        )
        autre = EvenementBanquet.objects.create(
            company=self.co, nom_evenement='Événement C', salle=self.salle,
            date_debut='2026-10-01T10:00:00Z', date_fin='2026-10-01T22:00:00Z',
            statut=EvenementBanquet.Statut.BROUILLON,
        )
        resp = auth(self.resp).patch(
            f'/api/django/hospitality/evenements/{autre.pk}/',
            {
                'statut': 'confirme',
                'date_debut': '2026-09-01T18:00:00Z',
                'date_fin': '2026-09-02T02:00:00Z',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_salle_autre_societe_refusee(self):
        autre_co = make_company('hot-salle-b', 'B')
        salle_b = SalleEvenement.objects.create(
            company=autre_co, nom='Salle B', capacite_max=50)
        resp = auth(self.resp).post(
            '/api/django/hospitality/evenements/',
            {
                'nom_evenement': 'Événement X', 'salle': salle_b.pk,
                'date_debut': '2026-09-01T10:00:00Z',
                'date_fin': '2026-09-01T22:00:00Z',
                'nb_convives': 10, 'statut': 'brouillon',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_tenant_isolation(self):
        autre_co = make_company('hot-salle-c', 'C')
        autre_user = make_user(autre_co, 'hot-salle-c-user')
        resp = auth(autre_user).get('/api/django/hospitality/salles-evenement/')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 0)
