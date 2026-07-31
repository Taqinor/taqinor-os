"""NTUX13 — Duplication indépendante d'un Devis (POST devis/<id>/dupliquer/).

Le duplicata repart TOUJOURS en brouillon avec un nouveau numéro, quel que
soit le statut de la source (jamais une copie de statut accepté/envoyé), et
ne porte aucun lien de version (à la différence de dupliquer-variante QJ15).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.services import dupliquer_devis

User = get_user_model()


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDupliquerDevis(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='ntux13-devis-co', defaults={'nom': 'NTUX13 Devis Co'})[0]
        self.user = User.objects.create_user(
            username='ntux13_devis_u', password='x', role_legacy='responsable',
            company=self.co)
        self.cli = Client.objects.create(
            company=self.co, nom='Client', prenom='NTUX13')
        self.source = Devis.objects.create(
            company=self.co, reference='DEV-NTUX13-0001', client=self.cli,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            note='Note originale')
        LigneDevis.objects.create(
            devis=self.source, designation='Panneau 500W',
            quantite=Decimal('10'), prix_unitaire=Decimal('1500'))

    def test_service_creates_independent_brouillon(self):
        copie = dupliquer_devis(self.source, user=self.user)
        self.assertNotEqual(copie.pk, self.source.pk)
        self.assertNotEqual(copie.reference, self.source.reference)
        self.assertEqual(copie.statut, Devis.Statut.BROUILLON)
        self.assertIsNone(copie.version_parent_id)
        self.assertEqual(copie.version, 1)
        self.assertEqual(copie.client_id, self.source.client_id)
        self.assertEqual(copie.lignes.count(), 1)
        ligne = copie.lignes.first()
        self.assertEqual(ligne.designation, 'Panneau 500W')
        self.assertEqual(ligne.quantite, Decimal('10'))
        # La source reste inchangée (statut, référence).
        self.source.refresh_from_db()
        self.assertEqual(self.source.statut, Devis.Statut.ACCEPTE)

    def test_endpoint_dupliquer(self):
        api = _auth(self.user)
        resp = api.post(f'/api/django/ventes/devis/{self.source.pk}/dupliquer/')
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data['statut'], 'brouillon')
        self.assertNotEqual(data['reference'], self.source.reference)
        new_devis = Devis.objects.get(pk=data['id'])
        self.assertEqual(new_devis.lignes.count(), 1)
