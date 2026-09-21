"""Tests NTSUB5 — Période d'essai (trial) sur abonnement + conversion planifiée.

Couvre : un contrat en essai ne génère aucune échéance avant la fin d'essai ;
il devient facturable automatiquement le jour dit (date injectée) ; une
annulation (contrat résilié) avant terme empêche la conversion ; la
notification J-3 part une seule fois (idempotence) ; multi-tenant.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    Contrat,
    EcheancierContrat,
    EssaiAbonnement,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_contrat(company, statut=Contrat.Statut.ACTIF):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal("1000"),
        type_contrat="om", statut=statut,
        date_debut=datetime.date(2026, 1, 1))


def make_echeancier(company, contrat, active=True):
    return EcheancierContrat.objects.create(
        company=company, contrat=contrat,
        periodicite=EcheancierContrat.Periodicite.MENSUELLE,
        facturation_active=active,
        statut=EcheancierContrat.Statut.ACTIF)


class DemarrerEssaiTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub5-start", "Ntsub5Start")

    def test_demarrage_gele_la_facturation(self):
        contrat = make_contrat(self.co)
        ech = make_echeancier(self.co, contrat, active=True)
        essai = services.demarrer_essai_contrat(
            contrat, date_fin_essai=datetime.date(2026, 3, 1))
        ech.refresh_from_db()
        self.assertFalse(ech.facturation_active)
        self.assertFalse(essai.converti)

    def test_double_demarrage_refuse(self):
        contrat = make_contrat(self.co)
        services.demarrer_essai_contrat(
            contrat, date_fin_essai=datetime.date(2026, 3, 1))
        with self.assertRaises(services.EssaiAbonnementError):
            services.demarrer_essai_contrat(
                contrat, date_fin_essai=datetime.date(2026, 4, 1))


class ConversionEssaiTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub5-conv", "Ntsub5Conv")

    def test_essai_non_echu_ne_convertit_pas(self):
        contrat = make_contrat(self.co)
        make_echeancier(self.co, contrat)
        services.demarrer_essai_contrat(
            contrat, date_fin_essai=datetime.date(2026, 3, 1))
        res = services.convertir_essais_expires(
            self.co, today=datetime.date(2026, 2, 1))
        self.assertEqual(res['convertis'], 0)
        essai = EssaiAbonnement.objects.get(company=self.co, cible_id=contrat.id)
        self.assertFalse(essai.converti)

    def test_essai_echu_devient_facturable(self):
        contrat = make_contrat(self.co)
        ech = make_echeancier(self.co, contrat)
        services.demarrer_essai_contrat(
            contrat, date_fin_essai=datetime.date(2026, 3, 1))
        res = services.convertir_essais_expires(
            self.co, today=datetime.date(2026, 3, 1))
        self.assertEqual(res['convertis'], 1)
        ech.refresh_from_db()
        self.assertTrue(ech.facturation_active)
        essai = EssaiAbonnement.objects.get(company=self.co, cible_id=contrat.id)
        self.assertTrue(essai.converti)
        self.assertEqual(essai.date_conversion, datetime.date(2026, 3, 1))

    def test_contrat_resilie_avant_terme_ne_convertit_pas(self):
        contrat = make_contrat(self.co)
        ech = make_echeancier(self.co, contrat)
        services.demarrer_essai_contrat(
            contrat, date_fin_essai=datetime.date(2026, 3, 1))
        contrat.statut = Contrat.Statut.RESILIE
        contrat.save(update_fields=['statut'])
        res = services.convertir_essais_expires(
            self.co, today=datetime.date(2026, 3, 1))
        self.assertEqual(res['convertis'], 0)
        ech.refresh_from_db()
        self.assertFalse(ech.facturation_active)  # reste gelé

    def test_conversion_idempotente(self):
        contrat = make_contrat(self.co)
        make_echeancier(self.co, contrat)
        services.demarrer_essai_contrat(
            contrat, date_fin_essai=datetime.date(2026, 3, 1))
        services.convertir_essais_expires(
            self.co, today=datetime.date(2026, 3, 1))
        res2 = services.convertir_essais_expires(
            self.co, today=datetime.date(2026, 3, 2))
        self.assertEqual(res2['convertis'], 0)  # déjà converti

    def test_alerte_j3_une_seule_fois(self):
        contrat = make_contrat(self.co)
        make_echeancier(self.co, contrat)
        services.demarrer_essai_contrat(
            contrat, date_fin_essai=datetime.date(2026, 3, 4))
        # today = fin - 3 → alerte J-3
        res = services.convertir_essais_expires(
            self.co, today=datetime.date(2026, 3, 1))
        self.assertEqual(res['alertes_j3'], 1)
        res2 = services.convertir_essais_expires(
            self.co, today=datetime.date(2026, 3, 1))
        self.assertEqual(res2['alertes_j3'], 0)  # idempotent


class EssaiMultiTenantTests(TestCase):
    def test_scope_societe(self):
        co1 = make_company("ntsub5-t1", "Ntsub5T1")
        co2 = make_company("ntsub5-t2", "Ntsub5T2")
        c1 = make_contrat(co1)
        make_echeancier(co1, c1)
        c2 = make_contrat(co2)
        make_echeancier(co2, c2)
        services.demarrer_essai_contrat(
            c1, date_fin_essai=datetime.date(2026, 3, 1))
        services.demarrer_essai_contrat(
            c2, date_fin_essai=datetime.date(2026, 3, 1))
        # Convertir seulement co1.
        res = services.convertir_essais_expires(
            co1, today=datetime.date(2026, 3, 1))
        self.assertEqual(res['convertis'], 1)
        essai2 = EssaiAbonnement.objects.get(company=co2, cible_id=c2.id)
        self.assertFalse(essai2.converti)  # co2 intact
