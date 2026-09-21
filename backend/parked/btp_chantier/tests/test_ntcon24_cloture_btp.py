"""Tests NTCON24 — Assistant guidé « Clôture de chantier » (DGD + export).

Couvre : refus EXPLICITE tant qu'un pré-requis manque (réserve bloquante
ouverte NTCON1/2, visa non décidé ou refusé NTCON5, PPSPS non signé NTCON16),
succès qui enchaîne DGD (NTCON9) + notification + URL d'export du dossier
(NTCON20) sans étape manuelle, et refus cross-tenant.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier import services
from apps.btp_chantier.models import (
    DecompteGeneral, PPSPSChantier, ReserveChantier, VisaDocument,
)

from .helpers import (
    auth, make_chantier, make_company, make_fournisseur,
    make_ordre_sous_traitance, make_user,
)

CLOTURE = '/api/django/btp-chantier/chantiers/{}/cloture-btp/'


class ClotureBtpTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.api = auth(self.user)

    # ── Pré-requis ──────────────────────────────────────────────────────
    def test_chantier_propre_est_pret(self):
        resp = self.api.get(CLOTURE.format(self.chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(resp.data['pret'])
        self.assertEqual(resp.data['blocages'], [])

    def test_reserve_bloquante_ouverte_empeche(self):
        ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, description='Fissure',
            gravite=ReserveChantier.Gravite.BLOQUANTE)
        resp = self.api.get(CLOTURE.format(self.chantier.id))
        self.assertFalse(resp.data['pret'])
        self.assertTrue(any(
            'bloquante' in b for b in resp.data['blocages']))

    def test_visa_en_attente_empeche_en_le_nommant(self):
        VisaDocument.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=3,
            reference='VIS-N24-0001', statut=VisaDocument.Statut.SOUMIS)
        resp = self.api.get(CLOTURE.format(self.chantier.id))
        self.assertFalse(resp.data['pret'])
        self.assertTrue(any(
            'VIS-N24-0001' in b for b in resp.data['blocages']))

    def test_visa_refuse_empeche(self):
        VisaDocument.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=4,
            reference='VIS-N24-0002', statut=VisaDocument.Statut.REFUSE)
        resp = self.api.get(CLOTURE.format(self.chantier.id))
        self.assertFalse(resp.data['pret'])
        self.assertTrue(any('refusé' in b for b in resp.data['blocages']))

    def test_ppsps_non_signe_par_un_sous_traitant_actif_empeche(self):
        PPSPSChantier.objects.create(
            company=self.co, chantier=self.chantier,
            date_validation='2026-01-01')
        fournisseur = make_fournisseur(self.co)
        make_ordre_sous_traitance(
            self.co, self.chantier, fournisseur, statut='emis')
        resp = self.api.get(CLOTURE.format(self.chantier.id))
        self.assertFalse(resp.data['pret'])
        self.assertTrue(any(
            fournisseur.nom in b for b in resp.data['blocages']))

    def test_ppsps_signe_ne_bloque_plus(self):
        ppsps = PPSPSChantier.objects.create(
            company=self.co, chantier=self.chantier,
            date_validation='2026-01-01')
        fournisseur = make_fournisseur(self.co)
        make_ordre_sous_traitance(
            self.co, self.chantier, fournisseur, statut='emis')
        services.signer_ppsps(
            ppsps, sous_traitant=fournisseur, signataire_nom='M. Alaoui')
        resp = self.api.get(CLOTURE.format(self.chantier.id))
        self.assertTrue(resp.data['pret'], resp.data)

    # ── Clôture enchaînée ───────────────────────────────────────────────
    def test_cloture_refusee_liste_les_blocages(self):
        ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, description='Fissure',
            gravite=ReserveChantier.Gravite.BLOQUANTE)
        resp = self.api.post(CLOTURE.format(self.chantier.id), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Clôture impossible', resp.data['detail'])
        self.assertTrue(resp.data['blocages'])
        self.assertFalse(DecompteGeneral.objects.exists())

    def test_cloture_enchaine_dgd_notification_et_export(self):
        resp = self.api.post(CLOTURE.format(self.chantier.id), {
            'montant_marche_initial_ht': '250000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        dgd = DecompteGeneral.objects.get(chantier=self.chantier)
        self.assertEqual(dgd.company_id, self.co.id)
        self.assertEqual(
            dgd.montant_marche_initial_ht, Decimal('250000.00'))
        # Notifié dans la foulée (NTCON9), sans étape manuelle.
        self.assertEqual(dgd.statut, DecompteGeneral.Statut.NOTIFIE)
        self.assertIsNotNone(dgd.date_notification)
        self.assertIn(
            f'chantiers/{self.chantier.id}/export-dossier-btp/',
            resp.data['export_dossier_url'])

    def test_reserve_non_bloquante_ouverte_ne_bloque_pas(self):
        ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, description='Retouche',
            gravite=ReserveChantier.Gravite.MINEURE)
        resp = self.api.post(CLOTURE.format(self.chantier.id), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_cross_tenant_refuse(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        resp = self.api.get(CLOTURE.format(chantier_autre.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
