"""Tests NTSUB8 — Séquence de dunning multi-étapes configurable.

Couvre : une séquence à N étapes envoie aux bons jours d'impayé (dates
injectées via jours_retard des factures) ; re-run le même jour = 0 doublon
(idempotence EtapeDunningLog) ; absence de séquence = comportement ZCTR2
inchangé ; la dernière étape déclenche la suspension ZCTR2 ; multi-tenant.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    Contrat,
    EcheancierContrat,
    EtapeDunning,
    EtapeDunningLog,
    LigneEcheance,
    SequenceDunning,
)
from apps.crm.models import Client
from apps.ventes.models import Facture


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_contrat(company, *, sequence=None):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal("12000"),
        type_contrat="om", statut=Contrat.Statut.ACTIF,
        sequence_dunning=sequence,
        date_debut=timezone.localdate() - timedelta(days=90))


def make_impaye(company, contrat, *, jours_retard=20):
    client = Client.objects.create(
        company=company, nom="Client", prenom="Impaye",
        telephone=f"+21260{company.id:07d}")
    facture = Facture.objects.create(
        company=company, client=client, statut=Facture.Statut.EMISE,
        taux_tva=Decimal("20"), montant_ttc=Decimal("1000"),
        date_echeance=timezone.localdate() - timedelta(days=jours_retard))
    echeancier = EcheancierContrat.objects.create(
        company=company, contrat=contrat,
        periodicite=EcheancierContrat.Periodicite.MENSUELLE,
        facturation_active=True, statut=EcheancierContrat.Statut.ACTIF)
    LigneEcheance.objects.create(
        company=company, echeancier=echeancier, numero=1,
        date_echeance=timezone.localdate() - timedelta(days=jours_retard),
        montant=Decimal("1000"), facture_id=facture.id)
    return facture


def make_sequence(company, *, etapes):
    """etapes: list of (jour_offset, canal, declenche_suspension)."""
    seq = SequenceDunning.objects.create(company=company, nom="Séquence std")
    for i, (offset, canal, suspend) in enumerate(etapes):
        EtapeDunning.objects.create(
            company=company, sequence=seq, jour_offset=offset, canal=canal,
            ordre=i, declenche_suspension=suspend)
    return seq


class DunningExecutionTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub8-co", "Ntsub8Co")

    def test_etapes_dues_jouees_selon_jours_impaye(self):
        seq = make_sequence(self.co, etapes=[
            (1, EtapeDunning.Canal.EMAIL, False),
            (7, EtapeDunning.Canal.WHATSAPP, False),
            (30, EtapeDunning.Canal.NOTIFICATION_INTERNE, True),
        ])
        contrat = make_contrat(self.co, sequence=seq)
        make_impaye(self.co, contrat, jours_retard=10)  # J+1 et J+7 dus, pas J+30

        res = services.executer_dunning_contrat(contrat)

        self.assertEqual(res['etapes_jouees'], 2)
        self.assertFalse(res['suspendu'])
        self.assertEqual(
            EtapeDunningLog.objects.filter(contrat=contrat).count(), 2)

    def test_rerun_meme_jour_zero_doublon(self):
        seq = make_sequence(self.co, etapes=[
            (1, EtapeDunning.Canal.EMAIL, False),
        ])
        contrat = make_contrat(self.co, sequence=seq)
        make_impaye(self.co, contrat, jours_retard=10)

        services.executer_dunning_contrat(contrat)
        res2 = services.executer_dunning_contrat(contrat)

        self.assertEqual(res2['etapes_jouees'], 0)
        self.assertEqual(
            EtapeDunningLog.objects.filter(contrat=contrat).count(), 1)

    def test_derniere_etape_suspend_le_contrat(self):
        seq = make_sequence(self.co, etapes=[
            (5, EtapeDunning.Canal.NOTIFICATION_INTERNE, True),
        ])
        contrat = make_contrat(self.co, sequence=seq)
        make_impaye(self.co, contrat, jours_retard=20)  # >= 5 → étape due

        res = services.executer_dunning_contrat(contrat)

        self.assertTrue(res['suspendu'])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.SUSPENDU)

    def test_sans_sequence_comportement_inchange(self):
        contrat = make_contrat(self.co, sequence=None)
        make_impaye(self.co, contrat, jours_retard=99)

        res = services.executer_dunning_contrat(contrat)

        self.assertEqual(res['etapes_jouees'], 0)
        self.assertFalse(res['suspendu'])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_sequence_inactive_ne_joue_rien(self):
        seq = make_sequence(self.co, etapes=[
            (1, EtapeDunning.Canal.EMAIL, False),
        ])
        seq.actif = False
        seq.save(update_fields=['actif'])
        contrat = make_contrat(self.co, sequence=seq)
        make_impaye(self.co, contrat, jours_retard=10)

        res = services.executer_dunning_contrat(contrat)
        self.assertEqual(res['etapes_jouees'], 0)

    def test_contrat_a_jour_ne_joue_rien(self):
        seq = make_sequence(self.co, etapes=[
            (1, EtapeDunning.Canal.EMAIL, False),
        ])
        contrat = make_contrat(self.co, sequence=seq)
        # facture payée → jours_impaye = 0
        facture = make_impaye(self.co, contrat, jours_retard=10)
        facture.statut = Facture.Statut.PAYEE
        facture.save(update_fields=['statut'])

        res = services.executer_dunning_contrat(contrat)
        self.assertEqual(res['etapes_jouees'], 0)


class DunningCompanyTests(TestCase):
    def test_scope_societe(self):
        co1 = make_company("ntsub8-t1", "Ntsub8T1")
        co2 = make_company("ntsub8-t2", "Ntsub8T2")
        seq1 = make_sequence(co1, etapes=[(1, EtapeDunning.Canal.EMAIL, False)])
        c1 = make_contrat(co1, sequence=seq1)
        make_impaye(co1, c1, jours_retard=10)
        seq2 = make_sequence(co2, etapes=[(1, EtapeDunning.Canal.EMAIL, False)])
        c2 = make_contrat(co2, sequence=seq2)
        make_impaye(co2, c2, jours_retard=10)

        total = services.executer_dunning_company(co1)
        self.assertEqual(total['etapes_jouees'], 1)
        self.assertEqual(
            EtapeDunningLog.objects.filter(company=co2).count(), 0)
