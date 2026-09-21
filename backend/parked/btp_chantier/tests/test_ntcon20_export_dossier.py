"""Tests NTCON20 — Export « dossier chantier » consolidé (ZIP).

Couvre : présence des pièces d'UN chantier (journal NTCON6, réserves LEVÉES
NTCON1/2 + preuves, visas APPROUVÉS NTCON5, DGD NTCON9, PPSPS signé NTCON16),
exclusion de tout ce qui appartient à un autre chantier ou à une autre société
(cross-tenant), et refus 404 sur un chantier d'une autre société.
"""
import io
import zipfile
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier import services
from apps.btp_chantier.models import (
    DecompteGeneral, JournalChantier, PPSPSChantier, ReserveChantier,
    VisaDocument,
)

from .helpers import (
    attach, auth, make_chantier, make_company, make_fournisseur, make_user,
)

EXPORT = '/api/django/btp-chantier/chantiers/{}/export-dossier-btp/'
PDF_FAKE = b'%PDF-1.4 test'


class ExportDossierBtpTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.api = auth(self.user)

        JournalChantier.objects.create(
            company=self.co, chantier=self.chantier, date='2026-02-02',
            evenements='Coulage dalle')

        self.reserve_levee = ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, description='Fissure',
            statut=ReserveChantier.Statut.LEVEE)
        attach(self.co, self.user, self.reserve_levee, 'apres', 'preuve.png')
        ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier,
            description='Encore ouverte')

        VisaDocument.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=7,
            reference='VIS-N20-0001',
            statut=VisaDocument.Statut.APPROUVE_SANS_RESERVE)
        VisaDocument.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=8,
            reference='VIS-N20-0002', statut=VisaDocument.Statut.SOUMIS)

        DecompteGeneral.objects.create(
            company=self.co, chantier=self.chantier,
            reference='DGD-N20-0001')

        ppsps = PPSPSChantier.objects.create(
            company=self.co, chantier=self.chantier, titre='PPSPS Villa',
            date_validation='2026-01-15')
        services.signer_ppsps(
            ppsps, sous_traitant=make_fournisseur(self.co),
            signataire_nom='M. Alaoui')
        self.ppsps_id = ppsps.id

        # Bruit : un AUTRE chantier de la MÊME société + une AUTRE société.
        self.autre_chantier = make_chantier(self.co)
        self.reserve_voisine = ReserveChantier.objects.create(
            company=self.co, chantier=self.autre_chantier,
            description='Réserve voisine',
            statut=ReserveChantier.Statut.LEVEE)
        VisaDocument.objects.create(
            company=self.co, chantier=self.autre_chantier,
            document_ged_id=9, reference='VIS-N20-0003',
            statut=VisaDocument.Statut.APPROUVE_SANS_RESERVE)

    def _zip(self):
        with patch('apps.btp_chantier.pdf.render_journal_chantier_pdf',
                   return_value=PDF_FAKE), \
                patch('apps.btp_chantier.pdf.render_dgd_pdf',
                      return_value=PDF_FAKE), \
                patch('apps.records.storage.fetch_attachment',
                      return_value=(b'octets-preuve', None)):
            data = services.export_dossier_btp(self.chantier)
        return zipfile.ZipFile(io.BytesIO(data))

    def test_zip_contient_toutes_les_pieces(self):
        zf = self._zip()
        noms = zf.namelist()
        self.assertIn('manifeste.txt', noms)
        self.assertIn('journal-chantier.pdf', noms)
        self.assertIn('reserves/reserves-levees.csv', noms)
        self.assertIn(
            f'reserves/{self.reserve_levee.id}/preuve.png', noms)
        self.assertIn('visas/visas-approuves.csv', noms)
        self.assertIn('dgd/DGD-N20-0001.pdf', noms)
        self.assertIn(f'ppsps/ppsps-{self.ppsps_id}.txt', noms)

    def test_seules_les_reserves_levees_sont_incluses(self):
        zf = self._zip()
        csv_reserves = zf.read('reserves/reserves-levees.csv').decode('utf-8')
        self.assertIn('Fissure', csv_reserves)
        self.assertNotIn('Encore ouverte', csv_reserves)

    def test_seuls_les_visas_approuves_sont_inclus(self):
        zf = self._zip()
        csv_visas = zf.read('visas/visas-approuves.csv').decode('utf-8')
        self.assertIn('VIS-N20-0001', csv_visas)
        self.assertNotIn('VIS-N20-0002', csv_visas)

    def test_rien_d_un_autre_chantier(self):
        zf = self._zip()
        csv_reserves = zf.read('reserves/reserves-levees.csv').decode('utf-8')
        csv_visas = zf.read('visas/visas-approuves.csv').decode('utf-8')
        self.assertNotIn('Réserve voisine', csv_reserves)
        self.assertNotIn('VIS-N20-0003', csv_visas)
        self.assertNotIn(
            f'reserves/{self.reserve_voisine.id}/', ' '.join(zf.namelist()))

    def test_ppsps_liste_ses_signataires(self):
        zf = self._zip()
        contenu = zf.read(
            f'ppsps/ppsps-{self.ppsps_id}.txt').decode('utf-8')
        self.assertIn('M. Alaoui', contenu)
        self.assertIn('2026-01-15', contenu)

    def test_endpoint_renvoie_un_zip(self):
        with patch('apps.btp_chantier.pdf.render_journal_chantier_pdf',
                   return_value=PDF_FAKE), \
                patch('apps.btp_chantier.pdf.render_dgd_pdf',
                      return_value=PDF_FAKE), \
                patch('apps.records.storage.fetch_attachment',
                      return_value=(b'octets-preuve', None)):
            resp = self.api.get(EXPORT.format(self.chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/zip')
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        self.assertIn('manifeste.txt', zf.namelist())

    def test_cross_tenant_refuse(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        resp = self.api.get(EXPORT.format(chantier_autre.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
