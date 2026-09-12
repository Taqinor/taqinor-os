"""NTNRG27 — Registre des certificats carbone émis (traçabilité / anti-double-comptage).

Couvre :
  * un certificat émis se retrouve dans le registre, avec une référence
    race-safe posée côté serveur ;
  * un doublon EXACT (même cible + même période) est refusé ;
  * une période différente ou une cible différente n'est PAS un doublon ;
  * ni site ni client (ou les deux) est rejeté (XOR) ;
  * société isolée (jamais de fuite cross-tenant).

Run :
    python manage.py test apps.monitoring.test_ntnrg27_registre_certificats -v 2
"""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company
from apps.monitoring.models import CertificatCarbone
from apps.monitoring.services import emettre_certificat_carbone


class TestEmettreCertificatCarbone(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg27-co', defaults={'nom': 'NTNRG27 Co'})

    def test_emission_cree_le_registre_avec_reference(self):
        certif = emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        self.assertTrue(certif.reference.startswith('CERT-CO2-'))
        self.assertEqual(CertificatCarbone.objects.count(), 1)

    def test_doublon_exact_refuse(self):
        emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        with self.assertRaises(ValueError):
            emettre_certificat_carbone(
                self.company, installation_id=1,
                periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
                tco2_evitees=Decimal('12.500'))
        self.assertEqual(CertificatCarbone.objects.count(), 1)

    def test_periode_differente_nest_pas_un_doublon(self):
        emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        certif2 = emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 7, 1), periode_fin=date(2026, 12, 31),
            tco2_evitees=Decimal('13.000'))
        self.assertEqual(CertificatCarbone.objects.count(), 2)
        self.assertNotEqual(
            certif2.reference,
            CertificatCarbone.objects.exclude(pk=certif2.pk).first().reference)

    def test_client_consolide_meme_periode_que_site_nest_pas_un_doublon(self):
        # Un certificat SITE (installation_id=1) et un certificat CLIENT
        # (client_id=1) sur la même période sont des cibles DIFFÉRENTES —
        # jamais confondus par la contrainte d'unicité (branches XOR séparées).
        emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        certif_client = emettre_certificat_carbone(
            self.company, client_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('20.000'))
        self.assertEqual(CertificatCarbone.objects.count(), 2)
        self.assertEqual(certif_client.client_id, 1)

    def test_ni_site_ni_client_est_rejete(self):
        with self.assertRaises(ValueError):
            emettre_certificat_carbone(
                self.company,
                periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
                tco2_evitees=Decimal('1'))

    def test_site_et_client_a_la_fois_est_rejete(self):
        with self.assertRaises(ValueError):
            emettre_certificat_carbone(
                self.company, installation_id=1, client_id=2,
                periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
                tco2_evitees=Decimal('1'))

    def test_periode_fin_avant_debut_est_rejetee(self):
        with self.assertRaises(ValueError):
            emettre_certificat_carbone(
                self.company, installation_id=1,
                periode_debut=date(2026, 6, 30), periode_fin=date(2026, 1, 1),
                tco2_evitees=Decimal('1'))

    def test_isolation_societe(self):
        autre_co, _ = Company.objects.get_or_create(
            slug='ntnrg27-autre-co', defaults={'nom': 'NTNRG27 Autre Co'})
        emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        # Même cible/période, société DIFFÉRENTE → pas un doublon.
        certif = emettre_certificat_carbone(
            autre_co, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        self.assertEqual(certif.company_id, autre_co.id)
        self.assertEqual(
            CertificatCarbone.objects.filter(company=self.company).count(), 1)
        self.assertEqual(
            CertificatCarbone.objects.filter(company=autre_co).count(), 1)

    def test_db_constraint_backstop_on_direct_create(self):
        # Contrainte DB en dernier recours si on contourne le service
        # (création directe du modèle) : même défense-en-profondeur que le
        # contrôle applicatif ci-dessus.
        CertificatCarbone.objects.create(
            company=self.company, installation_id=5,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 3, 31),
            tco2_evitees=Decimal('1'), reference='CERT-CO2-TEST-0001')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CertificatCarbone.objects.create(
                    company=self.company, installation_id=5,
                    periode_debut=date(2026, 1, 1), periode_fin=date(2026, 3, 31),
                    tco2_evitees=Decimal('1'), reference='CERT-CO2-TEST-0002')
