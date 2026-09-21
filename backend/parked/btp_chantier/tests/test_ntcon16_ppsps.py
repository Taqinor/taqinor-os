"""Tests NTCON16 — Lien PPSPS ↔ QHSE (plan de prévention par chantier/lot).

Couvre : création/validation d'un PPSPS, signature tracée par sous-traitant
(e-sign loi 53-05, une seule fois), lots couverts validés, et le SOFT-GUARD
« un ordre de sous-traitance (FG305) ne démarre pas sans PPSPS signé » dans
ses deux modes (bloquant / avertissement) — sans AUCUNE écriture dans
``installations`` (le guard passe par un signal ``pre_save``).
"""
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from rest_framework import status

from apps.btp_chantier import services
from apps.btp_chantier.models import PPSPSChantier, PPSPSSignature

from .helpers import (
    auth, make_chantier, make_company, make_fournisseur, make_lot,
    make_ordre_sous_traitance, make_user,
)

PPSPS = '/api/django/btp-chantier/ppsps/'


class PPSPSCrudTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.api = auth(self.user)

    def test_creation_validation_et_signature(self):
        resp = self.api.post(PPSPS, {
            'chantier': self.chantier.id, 'titre': 'PPSPS Villa',
            'document_ged_id': 42,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        ppsps_id = resp.data['id']
        self.assertFalse(resp.data['est_valide'])
        self.assertEqual(
            PPSPSChantier.objects.get(pk=ppsps_id).company_id, self.co.id)

        resp = self.api.post(f'{PPSPS}{ppsps_id}/valider/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(resp.data['est_valide'])
        self.assertIsNotNone(resp.data['date_validation'])

        fournisseur = make_fournisseur(self.co)
        resp = self.api.post(f'{PPSPS}{ppsps_id}/signer/', {
            'sous_traitant': fournisseur.id, 'signataire_nom': 'M. Alaoui',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['signataire_nom'], 'M. Alaoui')
        signature = PPSPSSignature.objects.get(pk=resp.data['id'])
        self.assertEqual(signature.company_id, self.co.id)
        self.assertEqual(signature.methode, PPSPSSignature.Methode.TYPED)

    def test_signature_en_double_refusee(self):
        ppsps = PPSPSChantier.objects.create(
            company=self.co, chantier=self.chantier)
        fournisseur = make_fournisseur(self.co)
        self.api.post(f'{PPSPS}{ppsps.id}/signer/', {
            'sous_traitant': fournisseur.id, 'signataire_nom': 'M. Alaoui',
        }, format='json')
        resp = self.api.post(f'{PPSPS}{ppsps.id}/signer/', {
            'sous_traitant': fournisseur.id, 'signataire_nom': 'M. Alaoui',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('déjà signé', resp.data['detail'])
        self.assertEqual(PPSPSSignature.objects.count(), 1)

    def test_signature_exige_un_nom(self):
        ppsps = PPSPSChantier.objects.create(
            company=self.co, chantier=self.chantier)
        fournisseur = make_fournisseur(self.co)
        resp = self.api.post(f'{PPSPS}{ppsps.id}/signer/', {
            'sous_traitant': fournisseur.id, 'signataire_nom': '  ',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('signataire_nom', resp.data)

    def test_sous_traitant_cross_tenant_refuse(self):
        ppsps = PPSPSChantier.objects.create(
            company=self.co, chantier=self.chantier)
        autre = make_company()
        fournisseur_autre = make_fournisseur(autre)
        resp = self.api.post(f'{PPSPS}{ppsps.id}/signer/', {
            'sous_traitant': fournisseur_autre.id, 'signataire_nom': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('sous_traitant', resp.data)

    def test_lot_d_un_autre_chantier_refuse(self):
        autre_chantier = make_chantier(self.co)
        lot_etranger = make_lot(self.co, autre_chantier, nom='Lot ailleurs')
        resp = self.api.post(PPSPS, {
            'chantier': self.chantier.id,
            'lots_couverts': [lot_etranger.id],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('lots_couverts', resp.data)

    def test_chantier_cross_tenant_refuse(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        resp = self.api.post(
            PPSPS, {'chantier': chantier_autre.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('chantier', resp.data)


class GuardPPSPSOrdreSousTraitanceTests(TestCase):
    """Le soft-guard vit dans un ``pre_save`` branché sur
    ``installations.OrdreSousTraitance`` — zéro ligne écrite dans cette app."""

    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.fournisseur = make_fournisseur(self.co)
        self.ordre = make_ordre_sous_traitance(
            self.co, self.chantier, self.fournisseur)

    def _ppsps_valide(self):
        return PPSPSChantier.objects.create(
            company=self.co, chantier=self.chantier,
            date_validation='2026-01-01')

    def test_sans_ppsps_le_demarrage_passe(self):
        self.ordre.statut = 'en_cours'
        self.ordre.save()
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.statut, 'en_cours')

    def test_ppsps_non_signe_bloque_le_demarrage(self):
        self._ppsps_valide()
        self.ordre.statut = 'en_cours'
        with self.assertRaises(PermissionDenied) as ctx:
            self.ordre.save()
        self.assertIn('PPSPS non signé', str(ctx.exception))
        self.ordre.refresh_from_db()
        self.assertNotEqual(self.ordre.statut, 'en_cours')

    def test_ppsps_signe_laisse_demarrer(self):
        ppsps = self._ppsps_valide()
        services.signer_ppsps(
            ppsps, sous_traitant=self.fournisseur, signataire_nom='M. Alaoui')
        self.ordre.statut = 'en_cours'
        self.ordre.save()
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.statut, 'en_cours')

    def test_ppsps_non_valide_ne_bloque_pas(self):
        # Un PPSPS pas encore validé n'est pas opposable.
        PPSPSChantier.objects.create(
            company=self.co, chantier=self.chantier)
        self.ordre.statut = 'en_cours'
        self.ordre.save()
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.statut, 'en_cours')

    def test_mode_avertissement_laisse_passer(self):
        self._ppsps_valide()
        config = dict(services.CONFIG_BTP_DEFAUTS)
        config['guard_ppsps_bloquant'] = False
        with patch.object(services, 'config_btp', return_value=config):
            self.ordre.statut = 'en_cours'
            self.ordre.save()
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.statut, 'en_cours')

    def test_ordre_deja_en_cours_n_est_pas_rebloque(self):
        ppsps = self._ppsps_valide()
        services.signer_ppsps(
            ppsps, sous_traitant=self.fournisseur, signataire_nom='M. Alaoui')
        self.ordre.statut = 'en_cours'
        self.ordre.save()
        # La signature disparaît (litige) : un ordre DÉJÀ en cours reste
        # sauvegardable — le guard ne garde que la TRANSITION.
        PPSPSSignature.objects.all().delete()
        self.ordre.prestation = 'Prestation révisée'
        self.ordre.save()
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.prestation, 'Prestation révisée')

    def test_selecteur_de_signature(self):
        ppsps = self._ppsps_valide()
        self.assertTrue(services.chantier_a_un_ppsps(self.chantier.id))
        self.assertFalse(services.sous_traitant_a_signe_ppsps(
            self.chantier.id, self.fournisseur.id))
        services.signer_ppsps(
            ppsps, sous_traitant=self.fournisseur, signataire_nom='M. Alaoui')
        self.assertTrue(services.sous_traitant_a_signe_ppsps(
            self.chantier.id, self.fournisseur.id))
