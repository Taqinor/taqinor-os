"""NTSAN40 — export des feuilles de soins par LOT (fin de journée/mois).

RÉUTILISE le générateur PDF de NTSAN14 (``services.imprimer_feuille_soins``)
EN BOUCLE — jamais un moteur PDF alternatif (``services.
exporter_feuilles_soins_lot``). Comme NTSAN14, ``render_pdf`` est stubbé
(WeasyPrint absent du poste de build) : ces tests portent sur le CONTENU du
ZIP produit, jamais sur les octets PDF réels."""
import datetime as dt
import io
import zipfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company

from apps.sante.models import ActeMedical, Admission, Patient, Praticien
from apps.sante.services import (
    creer_facture_sante, exporter_feuilles_soins_lot, realiser_acte,
)

User = get_user_model()
DATE_REALISATION = timezone.make_aware(dt.datetime(2026, 8, 12, 9, 0))


def _stub_pdf(*args, **kwargs):
    return b'%PDF-1.4 fake'


class NTSAN40FixtureMixin:
    def setUp(self):
        super().setUp()
        self.company, _ = Company.objects.get_or_create(
            slug='sante-export-lot-co', defaults={'nom': 'Clinique Export Lot'})
        self.user = User.objects.create_user(
            username='admin@sante-export-lot.ma', password='x',
            company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Naciri')
        self.acte_medical = ActeMedical.objects.create(
            company=self.company, libelle='Consultation', code_ngap='C',
            tarif_base_ttc='200.00')

    def _creer_facture(self, patient_nom, *, date_emission=None):
        patient = Patient.objects.create(company=self.company, nom=patient_nom)
        admission = Admission.objects.create(
            company=self.company, patient=patient, praticien=self.praticien,
            date_admission=DATE_REALISATION)
        acte = realiser_acte(
            admission=admission, patient=patient, praticien=self.praticien,
            acte=self.acte_medical, date_realisation=DATE_REALISATION)
        facture = creer_facture_sante(admission=admission, actes_realises=[acte])
        if date_emission is not None:
            facture.date_emission = date_emission
            facture.save(update_fields=['date_emission'])
        return facture


class NTSAN40ExportLotTests(NTSAN40FixtureMixin, TestCase):
    def test_une_feuille_exactement_par_facture_zero_doublon(self):
        f1 = self._creer_facture('Bennani')
        f2 = self._creer_facture('Alaoui')

        with mock.patch(
                'apps.sante.feuille_soins_pdf.render_pdf', side_effect=_stub_pdf):
            zip_bytes = exporter_feuilles_soins_lot(self.company)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            noms = sorted(zf.namelist())
        self.assertEqual(
            noms,
            sorted([f'feuille_soins_{f1.id}.pdf', f'feuille_soins_{f2.id}.pdf']))
        self.assertEqual(len(noms), len(set(noms)))

    def test_filtre_par_periode_date_emission(self):
        dans = self._creer_facture(
            'Bennani', date_emission=timezone.make_aware(dt.datetime(2026, 8, 5)))
        self._creer_facture(
            'Alaoui', date_emission=timezone.make_aware(dt.datetime(2026, 9, 15)))

        with mock.patch(
                'apps.sante.feuille_soins_pdf.render_pdf', side_effect=_stub_pdf):
            zip_bytes = exporter_feuilles_soins_lot(
                self.company, date_debut='2026-08-01', date_fin='2026-08-31')

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            noms = zf.namelist()
        self.assertEqual(noms, [f'feuille_soins_{dans.id}.pdf'])

    def test_lot_vide_sans_facture_dans_la_periode(self):
        with mock.patch(
                'apps.sante.feuille_soins_pdf.render_pdf', side_effect=_stub_pdf):
            zip_bytes = exporter_feuilles_soins_lot(
                self.company, date_debut='2099-01-01', date_fin='2099-01-31')

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            self.assertEqual(zf.namelist(), [])

    def test_scope_par_societe(self):
        autre, _ = Company.objects.get_or_create(
            slug='sante-export-lot-autre', defaults={'nom': 'Clinique Autre'})
        patient_autre = Patient.objects.create(company=autre, nom='Étranger')
        praticien_autre = Praticien.objects.create(company=autre, nom='Dr. X')
        admission_autre = Admission.objects.create(
            company=autre, patient=patient_autre, praticien=praticien_autre,
            date_admission=DATE_REALISATION)
        acte_autre_ref = ActeMedical.objects.create(
            company=autre, libelle='Consultation', code_ngap='C',
            tarif_base_ttc='200.00')
        acte_autre = realiser_acte(
            admission=admission_autre, patient=patient_autre,
            praticien=praticien_autre, acte=acte_autre_ref,
            date_realisation=DATE_REALISATION)
        creer_facture_sante(admission=admission_autre, actes_realises=[acte_autre])
        mienne = self._creer_facture('Bennani')

        with mock.patch(
                'apps.sante.feuille_soins_pdf.render_pdf', side_effect=_stub_pdf):
            zip_bytes = exporter_feuilles_soins_lot(self.company)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            noms = zf.namelist()
        self.assertEqual(noms, [f'feuille_soins_{mienne.id}.pdf'])


class NTSAN40EndpointTests(NTSAN40FixtureMixin, TestCase):
    def test_export_lot_telechargeable_en_zip(self):
        self._creer_facture('Bennani')
        self._creer_facture('Alaoui')

        with mock.patch(
                'apps.sante.feuille_soins_pdf.render_pdf', side_effect=_stub_pdf):
            resp = self.client.get(
                '/api/django/sante/factures-sante/export-lot/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            self.assertEqual(len(zf.namelist()), 2)
