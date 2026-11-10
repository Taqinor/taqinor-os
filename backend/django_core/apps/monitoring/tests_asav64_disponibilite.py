"""ASAV64 — la disponibilité se calcule sur l'UNION des intervalles couverts
`[date, date + period_days)`, pas sur le nombre de lignes.

Run :
    python manage.py test apps.monitoring.tests_asav64_disponibilite -v2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring import analytics
from apps.monitoring import tests as _base
from apps.monitoring.models import MonitoringConfig, ProductionReading
from authentication.models import Company

TODAY = date(2026, 10, 8)


class DisponibiliteTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav64-co', defaults={'nom': 'ASAV64 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV64')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV64', client=client,
            puissance_installee_kwc=Decimal('7.00'))
        MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))
        self.since = TODAY - timedelta(days=365)

    def _releve(self, jour, periode=1):
        ProductionReading.objects.create(
            company=self.company, installation=self.inst, date=jour,
            energy_kwh=Decimal('10'), period_days=periode)

    def _dispo(self):
        return analytics.om_metrics(
            self.inst, today=TODAY)['availability_pct']

    def test_releves_mensuels(self):
        for i in range(12):
            self._releve(self.since + timedelta(days=30 * i), periode=30)
        self.assertAlmostEqual(float(self._dispo()), 98.63, delta=0.05)

    def test_releves_journaliers(self):
        for i in range(366):
            self._releve(self.since + timedelta(days=i))
        self.assertEqual(self._dispo(), Decimal('100.00'))

    def test_trou_compte(self):
        for i in range(366):
            if 100 <= i < 130:  # trou de 30 jours
                continue
            self._releve(self.since + timedelta(days=i))
        self.assertAlmostEqual(float(self._dispo()), 92.05, delta=0.05)

    def test_chevauchement_non_double_compte(self):
        self._releve(self.since, periode=30)
        self._releve(self.since + timedelta(days=15), periode=30)
        # Union = 45 jours.
        self.assertAlmostEqual(float(self._dispo()), 45 / 365 * 100, delta=0.05)

    def test_systeme_neuf_fenetre_bornee_et_sans_releve_none(self):
        """AMON21 — fenêtre bornée au début de couverture : un système neuf
        bien relevé tient la garantie ; sans relevé, indicateurs ``None`` ;
        relevé à cheval sur le début de fenêtre compté au prorata."""
        from apps.monitoring.models import SlaDisponibilite
        from apps.monitoring.report import build_om_report_data
        from apps.monitoring.selectors import disponibilite_vs_garantie

        # (N) mis en service J−60, 60 relevés journaliers sains.
        Installation.objects.filter(pk=self.inst.pk).update(
            date_mise_en_service=TODAY - timedelta(days=60))
        self.inst.refresh_from_db()
        for i in range(60):
            self._releve(TODAY - timedelta(days=i))
        SlaDisponibilite.objects.create(
            company=self.company, installation=self.inst,
            disponibilite_garantie_pct=Decimal('98'))
        ecart = disponibilite_vs_garantie(self.inst, today=TODAY)
        self.assertGreaterEqual(ecart['disponibilite_mesuree_pct'], 98)
        self.assertFalse(ecart['sous_garantie'])
        rapport = build_om_report_data(
            self.inst, period='monthly', today=TODAY)
        self.assertEqual(rapport['availability_pct'], Decimal('100.00'))

        # (V) aucun relevé : None partout, jamais 0 %.
        vide = Installation.objects.create(
            company=self.company, reference='CHT-AMON21-V',
            client=self.inst.client, puissance_installee_kwc=Decimal('5'))
        MonitoringConfig.objects.create(
            company=self.company, installation=vide,
            expected_annual_kwh=Decimal('9000'))
        SlaDisponibilite.objects.create(
            company=self.company, installation=vide,
            disponibilite_garantie_pct=Decimal('98'))
        ecart = disponibilite_vs_garantie(vide, today=TODAY)
        self.assertIsNone(ecart['disponibilite_mesuree_pct'])
        self.assertIsNone(ecart['ecart_pct'])
        self.assertIsNone(ecart['penalite_mad'])
        rapport = build_om_report_data(vide, period='monthly', today=TODAY)
        self.assertIsNone(rapport['availability_pct'])
        self.assertIsNone(rapport['pr_pct'])

    def test_treize_mensuels_contigus_cent_pour_cent(self):
        """AMON21 — témoin : 13 mensuels contigus jusqu'à aujourd'hui, le
        premier à cheval sur le début de fenêtre ⇒ 100 %."""
        premier = TODAY - timedelta(days=30 * 13 - 1)
        for i in range(13):
            self._releve(premier + timedelta(days=30 * i), periode=30)
        self.assertEqual(self._dispo(), Decimal('100.00'))

    def test_rapport_client_libelle_indice_de_suivi(self):
        """AMON108 — le rapport O&M client (données servies à l'écran, HTML
        du PDF) titre l'indicateur de jours avec relevé « indice de suivi
        (jours avec relevé) », jamais « Disponibilité » — onduleur immobilisé
        du 01 au 16/10 et alarme escaladée compris ; valeur inchangée."""
        from datetime import datetime

        from django.utils import timezone

        from apps.monitoring.report import (
            build_om_report_data, build_om_report_html, render_om_report_pdf,
        )
        from apps.monitoring.selectors import LIBELLE_INDICE_SUIVI
        from apps.sav.models import (
            AlarmeOnduleur, Equipement, EquipementDowntime,
        )
        from apps.stock.models import Produit
        fin_octobre = date(2026, 10, 31)
        for i in range(31):
            self._releve(date(2026, 10, 1) + timedelta(days=i))
        onduleur = Equipement.objects.create(
            company=self.company, installation=self.inst,
            produit=Produit.objects.create(
                company=self.company, nom='Onduleur', sku='OND-AMON108',
                prix_achat=1, prix_vente=2))
        EquipementDowntime.objects.create(
            company=self.company, equipement=onduleur,
            debut=timezone.make_aware(datetime(2026, 10, 1)),
            fin=timezone.make_aware(datetime(2026, 10, 16)))
        AlarmeOnduleur.objects.create(
            company=self.company, equipement=onduleur, code='F01',
            statut=AlarmeOnduleur.Statut.ESCALADEE)
        data = build_om_report_data(self.inst, today=fin_octobre)
        self.assertEqual(data['libelle_indicateur'], LIBELLE_INDICE_SUIVI)
        self.assertEqual(data['availability_pct'], Decimal('100.00'))
        html = build_om_report_html(data)
        self.assertIn('indice de suivi (jours avec relevé)', html)
        self.assertNotIn('Disponibilité', html)
        self.assertTrue(bytes(render_om_report_pdf(
            self.inst, today=fin_octobre)).startswith(b'%PDF'))


class RapportOmPdfTests(TestCase):
    """ERR-AMON-PDF-RAPPORT-404 — ``?format=pdf`` est le paramètre réservé de DRF :
    sans renderer « pdf » déclaré, le bouton « Télécharger le PDF » rendait 404."""

    # Même fixture que tests.TestOmReport (référence par module : la classe
    # n'est pas réimportée, le chargeur ne la rejoue donc pas ici).
    setUp = _base.TestOmReport.setUp

    def test_report_pdf_endpoint_format_pdf(self):
        from unittest import mock
        with mock.patch('apps.monitoring.report.render_om_report_pdf',
                        return_value=b'%PDF-1.4 test'):
            r = self.api.get(
                f'/api/django/monitoring/configs/{self.config.id}/om-report/'
                '?period=monthly&format=pdf')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
