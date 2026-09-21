"""NTSAN14 — feuille de soins (FSE-like) IMPRIMABLE.

WeasyPrint n'est pas installé partout (libs natives absentes du poste de
build) : ces tests portent sur le CONTEXTE et le GABARIT HTML, jamais sur les
octets rendus — ``render_pdf`` est stubbé pour la route HTTP.
"""
import ast
import datetime as dt
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from core.models import BrandedTemplate

from apps.sante.feuille_soins_pdf import (
    BRANDED_TEMPLATE_CODE, TITRE_DEFAUT, render_feuille_soins_html)
from apps.sante.models import (
    ActeMedical, Admission, Convention, GrilleTarifaire, Patient, Praticien)
from apps.sante.services import (
    contexte_feuille_soins, creer_facture_sante, imprimer_feuille_soins,
    realiser_acte)

User = get_user_model()
DATE_REALISATION = timezone.make_aware(dt.datetime(2026, 8, 12, 9, 0))


class FeuilleSoinsFixtureMixin:
    def setUp(self):
        super().setUp()
        self.company, _ = Company.objects.get_or_create(
            slug='sante-feuille-soins-co',
            defaults={'nom': 'Clinique Feuille de soins'})
        self.user = User.objects.create_user(
            username='admin@sante-feuille-soins.ma', password='x',
            company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.convention = Convention.objects.create(
            company=self.company, nom='CNOPS', type=Convention.Type.CNOPS)
        self.patient = Patient.objects.create(
            company=self.company, nom='Bennani', prenom='Yasmine',
            cin='AB12345', numero_dossier='PAT00001',
            convention=self.convention, numero_affiliation='CN-99')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Naciri')
        self.admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_admission=DATE_REALISATION)

        self.consultation = ActeMedical.objects.create(
            company=self.company, libelle='Consultation', code_ngap='C',
            tarif_base_ttc='200.00')
        self.radio = ActeMedical.objects.create(
            company=self.company, libelle='Radiographie', code_ngap='Z12',
            tarif_base_ttc='300.00')
        GrilleTarifaire.objects.create(
            company=self.company, convention=self.convention,
            acte=self.consultation, tarif_convention_ttc='150.00',
            taux_prise_charge_pct='80.00')

        self.acte1 = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.consultation,
            date_realisation=DATE_REALISATION)
        self.acte2 = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.radio,
            date_realisation=DATE_REALISATION)
        self.facture = creer_facture_sante(
            admission=self.admission,
            actes_realises=[self.acte1, self.acte2],
            convention=self.convention)


class NTSAN14ContexteTests(FeuilleSoinsFixtureMixin, TestCase):
    def test_un_item_par_acte_realise_avec_son_code(self):
        """Critère d'acceptation : un item PAR ACTE, avec son code."""
        contexte = contexte_feuille_soins(self.facture)
        self.assertEqual(len(contexte['actes']), 2)
        codes = [a['code'] for a in contexte['actes']]
        self.assertIn('C', codes)
        self.assertIn('Z12', codes)
        libelles = [a['libelle'] for a in contexte['actes']]
        self.assertEqual(sorted(libelles), ['Consultation', 'Radiographie'])

    def test_montants_patient_praticien_et_convention_presents(self):
        contexte = contexte_feuille_soins(self.facture)
        self.assertEqual(contexte['patient'], 'Yasmine Bennani')
        self.assertEqual(contexte['numero_dossier'], 'PAT00001')
        self.assertEqual(contexte['convention'], 'CNOPS')
        self.assertEqual(contexte['numero_affiliation'], 'CN-99')
        self.assertEqual(
            {a['praticien'] for a in contexte['actes']}, {'Dr. Naciri'})
        self.assertEqual(contexte['total_ttc'], self.facture.total_ttc)
        self.assertEqual(
            contexte['part_tiers_payant_ttc'],
            self.facture.part_tiers_payant_ttc)

    def test_montant_de_ligne_multiplie_par_la_quantite(self):
        self.acte2.quantite = 3
        self.acte2.save(update_fields=['quantite'])
        contexte = contexte_feuille_soins(self.facture)
        radio = [a for a in contexte['actes'] if a['code'] == 'Z12'][0]
        self.assertEqual(radio['quantite'], 3)
        self.assertEqual(radio['montant_ttc'], Decimal('900.00'))

    def test_entete_par_defaut_sans_branded_template(self):
        contexte = contexte_feuille_soins(self.facture)
        self.assertEqual(contexte['titre'], TITRE_DEFAUT)

    def test_branded_template_surcharge_l_entete(self):
        BrandedTemplate.objects.create(
            company=self.company, kind=BrandedTemplate.KIND_PDF,
            code=BRANDED_TEMPLATE_CODE, nom='Feuille de soins clinique',
            sujet='Feuille de soins — {{ patient }}',
            corps='Dossier {{ numero_dossier }} — convention {{ convention }}.',
            actif=True)
        contexte = contexte_feuille_soins(self.facture)
        self.assertEqual(contexte['titre'], 'Feuille de soins — Yasmine Bennani')
        self.assertIn('PAT00001', contexte['introduction'])
        self.assertIn('CNOPS', contexte['introduction'])

    def test_branded_template_inactif_ignore(self):
        BrandedTemplate.objects.create(
            company=self.company, kind=BrandedTemplate.KIND_PDF,
            code=BRANDED_TEMPLATE_CODE, nom='Brouillon',
            sujet='NE PAS UTILISER', corps='x', actif=False)
        self.assertEqual(
            contexte_feuille_soins(self.facture)['titre'], TITRE_DEFAUT)


class NTSAN14GabaritTests(FeuilleSoinsFixtureMixin, TestCase):
    def test_html_liste_chaque_acte_avec_code_et_montant(self):
        html = render_feuille_soins_html(contexte_feuille_soins(self.facture))
        self.assertIn('Feuille de soins', html)
        self.assertIn('Yasmine Bennani', html)
        self.assertIn('CNOPS', html)
        self.assertIn('>C<', html)
        self.assertIn('Z12', html)
        self.assertIn('Consultation', html)
        self.assertIn('Radiographie', html)
        self.assertIn('Dr. Naciri', html)

    def test_regle_4_le_renderer_ignore_totalement_le_quote_engine(self):
        """Règle #4 : la feuille de soins n'emprunte jamais le chemin devis."""
        source = (Path(__file__).resolve().parent.parent
                  / 'feuille_soins_pdf.py').read_text(encoding='utf-8')
        modules = set()
        for noeud in ast.walk(ast.parse(source)):
            if isinstance(noeud, ast.Import):
                modules.update(alias.name for alias in noeud.names)
            elif isinstance(noeud, ast.ImportFrom):
                modules.add(noeud.module or '')
        for module in modules:
            self.assertNotIn('quote_engine', module)
            self.assertNotIn('ventes', module)
            self.assertNotEqual(module, 'weasyprint')
        self.assertIn('core.pdf', modules)


class NTSAN14EndpointTests(FeuilleSoinsFixtureMixin, TestCase):
    def test_pdf_telechargeable_depuis_la_facture(self):
        with mock.patch(
                'apps.sante.feuille_soins_pdf.render_pdf',
                return_value=b'%PDF-1.4 fake') as rendu:
            resp = self.client.get(
                f'/api/django/sante/factures-sante/{self.facture.id}'
                '/feuille-soins/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn(
            f'feuille_soins_{self.facture.id}.pdf',
            resp['Content-Disposition'])
        html = rendu.call_args.kwargs['html']
        self.assertIn('Radiographie', html)

    def test_facture_d_une_autre_societe_invisible(self):
        autre, _ = Company.objects.get_or_create(
            slug='sante-feuille-soins-autre',
            defaults={'nom': 'Clinique Autre'})
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
        facture_autre = creer_facture_sante(
            admission=admission_autre, actes_realises=[acte_autre])

        resp = self.client.get(
            f'/api/django/sante/factures-sante/{facture_autre.id}'
            '/feuille-soins/')
        self.assertEqual(resp.status_code, 404)

    def test_service_scope_par_societe(self):
        autre, _ = Company.objects.get_or_create(
            slug='sante-feuille-soins-tierce',
            defaults={'nom': 'Clinique Tierce'})
        from apps.sante.models import FactureSante

        with self.assertRaises(FactureSante.DoesNotExist):
            imprimer_feuille_soins(self.facture.id, company=autre)
