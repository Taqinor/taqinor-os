"""NTFPA1 — Modèle Département : hiérarchie 2 niveaux + arbre via ?tree=1."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.fpa.models import Departement

User = get_user_model()


class TestDepartementHierarchie(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa1-co', defaults={'nom': 'NTFPA1 Co'})
        self.user = User.objects.create_user(
            username='ntfpa1-admin', password='x', company=self.company,
            is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_hierarchie_deux_niveaux_et_arbre(self):
        holding = Departement.objects.create(
            company=self.company, code='HLD', nom='Holding')
        filiale1 = Departement.objects.create(
            company=self.company, code='F1', nom='Filiale 1', parent=holding)
        filiale2 = Departement.objects.create(
            company=self.company, code='F2', nom='Filiale 2', parent=holding)

        self.assertEqual(
            set(holding.sous_arbre_ids()), {holding.pk, filiale1.pk, filiale2.pk})

        resp = self.client.get('/api/django/fpa/departements/?tree=1')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['code'], 'HLD')
        self.assertEqual(len(data[0]['enfants']), 2)

    def test_filtre_actif(self):
        Departement.objects.create(
            company=self.company, code='A1', nom='Actif', actif=True)
        Departement.objects.create(
            company=self.company, code='A2', nom='Inactif', actif=False)
        resp = self.client.get('/api/django/fpa/departements/?actif=1')
        self.assertEqual(resp.status_code, 200)
        codes = [d['code'] for d in resp.json()['results']] if isinstance(
            resp.json(), dict) else [d['code'] for d in resp.json()]
        self.assertIn('A1', codes)
        self.assertNotIn('A2', codes)
