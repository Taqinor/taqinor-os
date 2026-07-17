"""Tests NTCON9 — DGD (Décompte Général et Définitif).

Couvre :
* création recalcule immédiatement les totaux exacts (avenants approuvés +
  situations facturées incluses) ;
* ``notifier/`` recalcule + passe en notifié ;
* export PDF correct (WeasyPrint via ``core.pdf``) ;
* cross-tenant refusé.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import AvenantChantier, DecompteGeneral

from .helpers import (
    auth, make_chantier, make_company, make_ligne_situation,
    make_projet_lie, make_situation, make_user,
)

BASE = '/api/django/btp-chantier/decomptes-generaux/'


class DecompteGeneralApiTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.projet = make_projet_lie(self.co, self.chantier)
        self.situation = make_situation(self.co, self.projet, numero=1)
        make_ligne_situation(
            self.co, self.situation, montant_periode=Decimal('20000.00'))
        AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier,
            reference='AVC-DGD-0001', description='Avenant approuvé',
            montant_ht=Decimal('3000.00'),
            statut=AvenantChantier.Statut.APPROUVE)
        # Un avenant NON approuvé ne doit jamais compter.
        AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier,
            reference='AVC-DGD-0002', description='Avenant brouillon',
            montant_ht=Decimal('9999.00'))

    def test_creer_dgd_recalcule_totaux(self):
        api = auth(self.user)
        resp = api.post(BASE, {
            'chantier': self.chantier.id,
            'montant_marche_initial_ht': '100000.00',
            'situations_incluses': [self.situation.id],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data['reference'].startswith('DGD-'))
        self.assertEqual(
            Decimal(resp.data['total_avenants_ht']), Decimal('3000.00'))
        self.assertEqual(
            Decimal(resp.data['total_situations_facturees_ht']),
            Decimal('20000.00'))
        self.assertEqual(
            Decimal(resp.data['solde_du_ht']),
            Decimal('100000.00') + Decimal('3000.00') - Decimal('20000.00'))

    def test_notifier_recalcule_et_change_statut(self):
        dgd = DecompteGeneral.objects.create(
            company=self.co, chantier=self.chantier, reference='DGD-T-0001',
            montant_marche_initial_ht=Decimal('50000.00'),
            situations_incluses=[self.situation.id])
        api = auth(self.user)
        resp = api.post(f'{BASE}{dgd.id}/notifier/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'notifie')
        self.assertEqual(
            Decimal(resp.data['total_situations_facturees_ht']),
            Decimal('20000.00'))

    def test_export_pdf(self):
        dgd = DecompteGeneral.objects.create(
            company=self.co, chantier=self.chantier, reference='DGD-T-0002',
            montant_marche_initial_ht=Decimal('10000.00'))
        api = auth(self.user)
        resp = api.get(f'{BASE}{dgd.id}/export-pdf/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_cross_tenant_refused(self):
        other_co = make_company()
        other_chantier = make_chantier(other_co)
        other_dgd = DecompteGeneral.objects.create(
            company=other_co, chantier=other_chantier,
            reference='DGD-OTHER-0001', montant_marche_initial_ht=0)
        api = auth(self.user)
        resp = api.get(f'{BASE}{other_dgd.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
