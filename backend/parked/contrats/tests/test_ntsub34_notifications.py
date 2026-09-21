"""Tests NTSUB34 — Notifications au responsable sur les événements clés.

Vérifie que le responsable est notifié UNE fois sur : conversion d'essai,
changement de plan, entrée en séquence de dunning ; et que l'absence de
responsable ne lève jamais (skip silencieux).
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    Contrat,
    EcheancierContrat,
    EtapeDunning,
    LigneEcheance,
    PlanAbonnement,
    PlanRecurrent,
    SequenceDunning,
)
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()

NOTIF = 'apps.contrats.services._notifier_responsable_contrat'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_contrat(company, resp=None, **kw):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal("500"),
        type_contrat="om", statut=Contrat.Statut.ACTIF, responsable=resp,
        date_debut=datetime.date(2026, 1, 1), **kw)


def make_plan(company, code, prix):
    return PlanAbonnement.objects.create(
        company=company, code=code, nom=f"Plan {code}",
        plan_recurrent=PlanRecurrent.objects.create(
            company=company, nom=f"C{code}",
            unite=PlanRecurrent.Unite.MENSUEL, intervalle=1),
        prix_base=Decimal(prix))


class NotificationsResponsableTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub34", "Ntsub34")
        self.resp = User.objects.create_user(
            username="ntsub34-resp", password="x", company=self.co,
            role_legacy="responsable")

    def test_conversion_essai_notifie(self):
        contrat = make_contrat(self.co, resp=self.resp)
        EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True, statut=EcheancierContrat.Statut.ACTIF)
        services.demarrer_essai_contrat(
            contrat, date_fin_essai=datetime.date(2026, 3, 1))
        with mock.patch(NOTIF) as notif:
            services.convertir_essais_expires(
                self.co, today=datetime.date(2026, 3, 1))
        self.assertTrue(notif.called)

    def test_changement_plan_notifie(self):
        contrat = make_contrat(self.co, resp=self.resp)
        plan = make_plan(self.co, "PRO", "800")
        with mock.patch(NOTIF) as notif:
            services.changer_plan_contrat(contrat, plan)
        self.assertTrue(notif.called)

    def test_entree_dunning_notifie_une_fois(self):
        seq = SequenceDunning.objects.create(company=self.co, nom="Seq")
        EtapeDunning.objects.create(
            company=self.co, sequence=seq, jour_offset=1,
            canal=EtapeDunning.Canal.EMAIL, ordre=0)
        EtapeDunning.objects.create(
            company=self.co, sequence=seq, jour_offset=7,
            canal=EtapeDunning.Canal.WHATSAPP, ordre=1)
        contrat = make_contrat(self.co, resp=self.resp, sequence_dunning=seq)
        client = Client.objects.create(company=self.co, nom="C")
        facture = Facture.objects.create(
            company=self.co, client=client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal("20"), montant_ttc=Decimal("1000"),
            date_echeance=timezone.localdate() - datetime.timedelta(days=10))
        ech = EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True, statut=EcheancierContrat.Statut.ACTIF)
        LigneEcheance.objects.create(
            company=self.co, echeancier=ech, numero=1,
            date_echeance=timezone.localdate() - datetime.timedelta(days=10),
            montant=Decimal("1000"), facture_id=facture.id)
        with mock.patch(NOTIF) as notif:
            services.executer_dunning_contrat(contrat)
        # 2 étapes jouées mais UNE seule notification d'entrée.
        self.assertEqual(notif.call_count, 1)

    def test_sans_responsable_ne_leve_pas(self):
        contrat = make_contrat(self.co, resp=None)
        plan = make_plan(self.co, "PRO", "800")
        # Aucun mock : le vrai helper skippe silencieusement sans responsable.
        services.changer_plan_contrat(contrat, plan)  # ne lève pas
