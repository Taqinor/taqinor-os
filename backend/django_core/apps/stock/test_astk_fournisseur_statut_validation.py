"""ASTK23 — `statut_validation` (et `company`, `tiers`) du fournisseur non
inscriptibles par PUT/PATCH : seule l'action admin `decider-candidature`
fait entrer un candidat au sourcing.

Rejoue FOUR-7 de l'audit stock du 2026-10-06 : avant correction, un
Responsable (stock_modifier, sans droit admin) passait un candidat
en_attente_validation → valide par un simple PATCH (200, relu « valide »)
alors que `decider-candidature` lui répondait 403.

Run:
    python manage.py test apps.stock.test_astk_fournisseur_statut_validation -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import Fournisseur

User = get_user_model()

EN_ATTENTE = Fournisseur.StatutValidation.EN_ATTENTE
VALIDE = Fournisseur.StatutValidation.VALIDE


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FournisseurStatutValidationTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='astk23-a', slug='astk23-a')
        self.autre = Company.objects.create(nom='astk23-b', slug='astk23-b')
        role = Role.objects.create(
            company=self.co, nom='r-astk23-resp',
            permissions=['stock_modifier', 'stock_voir',
                         # ASTK17-20 (D-ASTK-3) : l'acheteur porte les codes achats.
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        self.resp = User.objects.create_user(
            username='astk23-resp', password='x', company=self.co,
            role=role, role_legacy='responsable')
        self.admin = User.objects.create_user(
            username='astk23-admin', password='x', company=self.co,
            role_legacy='admin')
        self.candidat = Fournisseur.objects.create(
            company=self.co, nom='Candidat ASTK23',
            statut_validation=EN_ATTENTE)
        self.url = f'/api/django/stock/fournisseurs/{self.candidat.pk}/'

    def _relu(self):
        self.candidat.refresh_from_db()
        return self.candidat

    def test_patch_statut_validation_sans_effet(self):
        r = _api(self.resp).patch(
            self.url, {'statut_validation': 'valide', 'nom': 'Renommé'},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['statut_validation'], EN_ATTENTE)
        relu = self._relu()
        self.assertEqual(relu.statut_validation, EN_ATTENTE)
        self.assertEqual(relu.nom, 'Renommé')

    def test_put_ecran_complet_sans_effet(self):
        api = _api(self.resp)
        complet = api.get(self.url).json()
        complet['statut_validation'] = 'valide'
        complet['company'] = self.autre.pk
        corps = {k: v for k, v in complet.items() if v is not None}
        r = api.put(self.url, corps, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        relu = self._relu()
        self.assertEqual(relu.statut_validation, EN_ATTENTE)
        self.assertEqual(relu.company_id, self.co.pk)

    def test_decider_candidature_reste_admin(self):
        url = f'{self.url}decider-candidature/'
        r = _api(self.resp).post(url, {'valider': True}, format='json')
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(self._relu().statut_validation, EN_ATTENTE)
        r = _api(self.admin).post(url, {'valider': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._relu().statut_validation, VALIDE)
