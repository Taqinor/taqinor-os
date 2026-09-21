"""Tests NTAGR9 — Équipes journalières + pointage par tâche/parcelle.

Couvre : saisie d'un pointage par équipe/tâche/parcelle/jour, agrégation du
coût main d'œuvre de campagne (``cout_main_oeuvre_campagne``), pointage avec
travailleur libre (sans équipe RH), garde « équipe ou nom libre requis ».
"""
from decimal import Decimal

from django.test import TestCase

from apps.agriculture.models import (
    CampagneCulturale, EquipeSaisonniere, Exploitation, Parcelle,
)
from apps.agriculture.selectors import cout_main_oeuvre_campagne

from .helpers import auth, make_company, make_user, rows


class MainOeuvreApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('agr-mo-a', 'Ferme MO A')
        self.admin_a = make_user(self.co_a, 'agr-mo-admin-a', 'admin')
        exploitation = Exploitation.objects.create(company=self.co_a, nom='Domaine')
        self.parcelle = Parcelle.objects.create(
            company=self.co_a, exploitation=exploitation, nom='Parcelle 1')
        self.campagne = CampagneCulturale.objects.create(
            company=self.co_a, parcelle=self.parcelle, culture='Tomate')
        self.equipe = EquipeSaisonniere.objects.create(
            company=self.co_a, nom='Équipe récolte')

    def test_create_pointage_by_equipe_tache_parcelle_jour(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/pointages/', {
            'equipe': self.equipe.id, 'campagne': self.campagne.id,
            'parcelle': self.parcelle.id, 'date': '2026-06-10',
            'tache': 'Récolte', 'nombre_journees': '5.0',
            'taux_journalier_mad': '90.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_create_pointage_free_worker_name(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/pointages/', {
            'travailleur_nom': 'Fatima Z.', 'parcelle': self.parcelle.id,
            'date': '2026-06-11', 'tache': 'Désherbage',
            'nombre_journees': '1.0', 'taux_journalier_mad': '80.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_create_pointage_without_equipe_or_name_rejected(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/agriculture/pointages/', {
            'parcelle': self.parcelle.id, 'date': '2026-06-11',
            'tache': 'Désherbage', 'nombre_journees': '1.0',
            'taux_journalier_mad': '80.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_cout_main_oeuvre_campagne_aggregates(self):
        self.campagne.pointages.create(
            company=self.co_a, equipe=self.equipe, parcelle=self.parcelle,
            date='2026-06-10', tache='Récolte', nombre_journees=Decimal('5'),
            taux_journalier_mad=Decimal('90'))
        self.campagne.pointages.create(
            company=self.co_a, travailleur_nom='Ahmed', parcelle=self.parcelle,
            date='2026-06-11', tache='Récolte', nombre_journees=Decimal('2.5'),
            taux_journalier_mad=Decimal('80'))
        # 5*90 + 2.5*80 = 450 + 200 = 650
        self.assertEqual(
            cout_main_oeuvre_campagne(self.campagne), Decimal('650.00'))

    def test_filter_by_campagne_parcelle_equipe(self):
        self.campagne.pointages.create(
            company=self.co_a, equipe=self.equipe, parcelle=self.parcelle,
            date='2026-06-10', tache='Récolte', nombre_journees=Decimal('1'),
            taux_journalier_mad=Decimal('90'))
        api = auth(self.admin_a)
        resp = api.get('/api/django/agriculture/pointages/', {
            'campagne_id': self.campagne.id, 'parcelle_id': self.parcelle.id,
            'equipe_id': self.equipe.id,
        })
        self.assertEqual(len(rows(resp)), 1)
