"""ASTK24 — `statut` de l'avoir fournisseur non inscriptible ; montants et
fournisseur figés hors brouillon : un avoir n'est validé ou imputé que par
ses actions.

Rejoue FACF-10 de l'audit stock du 2026-10-06 : avant correction, POST
{statut: 'valide'} → 201 valide (sans passer par `valider/`) et PATCH d'un
avoir imputé {statut: 'brouillon', montant_ttc: '9999'} → 200.

Run:
    python manage.py test apps.stock.test_astk_avoir_statut -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import (
    AvoirFournisseur, FactureFournisseur, Fournisseur,
)
from apps.stock.services import imputer_avoir_fournisseur

User = get_user_model()

URL = '/api/django/stock/avoirs-fournisseur/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AvoirStatutTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='astk24', slug='astk24')
        self.user = User.objects.create_user(
            username='astk24-resp', password='x', company=self.co,
            role_legacy='admin')
        self.api = _api(self.user)
        self.f = Fournisseur.objects.create(company=self.co, nom='F ASTK24')
        self.f2 = Fournisseur.objects.create(company=self.co, nom='F2 ASTK24')

    def test_creation_nait_brouillon(self):
        r = self.api.post(URL, {
            'fournisseur': self.f.pk, 'montant_ht': '83.33',
            'montant_tva': '16.67', 'montant_ttc': '100', 'statut': 'valide',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['statut'], AvoirFournisseur.Statut.BROUILLON)
        avoir = AvoirFournisseur.objects.get(pk=r.json()['id'])
        self.assertEqual(avoir.statut, AvoirFournisseur.Statut.BROUILLON)

    def test_patch_avoir_impute_refuse(self):
        avoir = AvoirFournisseur.objects.create(
            company=self.co, reference='AVF-ASTK24', fournisseur=self.f,
            montant_ht=Decimal('83.33'), montant_tva=Decimal('16.67'),
            montant_ttc=Decimal('100'),
            statut=AvoirFournisseur.Statut.VALIDE)
        facture = FactureFournisseur.objects.create(
            company=self.co, reference='FF-ASTK24', fournisseur=self.f,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        imputer_avoir_fournisseur(avoir, facture, user=self.user)
        avoir.refresh_from_db()
        self.assertEqual(avoir.statut, AvoirFournisseur.Statut.IMPUTE)
        nb_imputations = avoir.imputations.count()

        url = f'{URL}{avoir.pk}/'
        for corps in ({'statut': 'brouillon', 'montant_ttc': '9999'},
                      {'montant_ttc': '9999'},
                      {'fournisseur': self.f2.pk}):
            r = self.api.patch(url, corps, format='json')
            self.assertEqual(r.status_code, 400, r.content)
            self.assertIn('non modifiable', r.json()['detail'])

        avoir.refresh_from_db()
        self.assertEqual(avoir.statut, AvoirFournisseur.Statut.IMPUTE)
        self.assertEqual(avoir.montant_ttc, Decimal('100'))
        self.assertEqual(avoir.fournisseur_id, self.f.pk)
        self.assertEqual(avoir.imputations.count(), nb_imputations)

    def test_brouillon_reste_modifiable(self):
        avoir = AvoirFournisseur.objects.create(
            company=self.co, reference='AVF-ASTK24-B', fournisseur=self.f,
            montant_ht=Decimal('10'), montant_tva=Decimal('2'),
            montant_ttc=Decimal('12'))
        r = self.api.patch(f'{URL}{avoir.pk}/',
                           {'montant_ttc': '24', 'statut': 'impute'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.content)
        avoir.refresh_from_db()
        self.assertEqual(avoir.montant_ttc, Decimal('24'))
        self.assertEqual(avoir.statut, AvoirFournisseur.Statut.BROUILLON)
