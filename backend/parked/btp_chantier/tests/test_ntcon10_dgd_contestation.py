"""Tests NTCON10 — Contestation & solde du DGD.

Couvre :
* contestation trace motif + montant contesté ;
* finalisation verrouille (403 sur toute écriture ultérieure) ;
* déverrouillage admin JOURNALISÉ (non-admin refusé) ;
* déverrouiller un DGD non verrouillé → 400.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import DecompteGeneral

from .helpers import auth, make_chantier, make_company, make_user

BASE = '/api/django/btp-chantier/decomptes-generaux/'


class DgdContestationTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.admin = make_user(self.co, role='admin')
        self.chantier = make_chantier(self.co)
        self.dgd = DecompteGeneral.objects.create(
            company=self.co, chantier=self.chantier, reference='DGD-T-0001',
            montant_marche_initial_ht=Decimal('10000.00'),
            statut=DecompteGeneral.Statut.NOTIFIE)

    def test_contester_trace_motif_et_montant(self):
        api = auth(self.user)
        resp = api.post(f'{BASE}{self.dgd.id}/contester/', {
            'motif': 'Désaccord sur les quantités',
            'montant_conteste': '1500.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'conteste')
        self.assertEqual(resp.data['motif_contestation'],
                         'Désaccord sur les quantités')
        self.assertEqual(Decimal(resp.data['montant_conteste']), Decimal('1500.00'))

    def test_finaliser_verrouille(self):
        api = auth(self.user)
        resp = api.post(f'{BASE}{self.dgd.id}/finaliser/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'definitif')

        # Toute écriture ultérieure est refusée en 403.
        resp2 = api.patch(
            f'{BASE}{self.dgd.id}/', {'motif_contestation': 'x'},
            format='json')
        self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)

    def test_finaliser_deux_fois_refuse(self):
        self.dgd.statut = DecompteGeneral.Statut.DEFINITIF
        self.dgd.save(update_fields=['statut'])
        api = auth(self.user)
        resp = api.post(f'{BASE}{self.dgd.id}/finaliser/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deverrouiller_non_admin_refuse(self):
        self.dgd.statut = DecompteGeneral.Statut.DEFINITIF
        self.dgd.save(update_fields=['statut'])
        api = auth(self.user)
        resp = api.post(
            f'{BASE}{self.dgd.id}/deverrouiller/', {'motif': 'Erreur'},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_deverrouiller_admin_journalise(self):
        self.dgd.statut = DecompteGeneral.Statut.DEFINITIF
        self.dgd.save(update_fields=['statut'])
        api = auth(self.admin)
        resp = api.post(
            f'{BASE}{self.dgd.id}/deverrouiller/',
            {'motif': 'Erreur de saisie'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'accepte')
        self.assertEqual(len(resp.data['historique_deverrouillage']), 1)
        self.assertEqual(
            resp.data['historique_deverrouillage'][0]['motif'],
            'Erreur de saisie')

    def test_deverrouiller_non_verrouille_refuse(self):
        api = auth(self.admin)
        resp = api.post(
            f'{BASE}{self.dgd.id}/deverrouiller/', {'motif': 'x'},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
