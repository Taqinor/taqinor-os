"""ZMKT5 — Traces d'activité de séquence (planifié / traité / rejeté) +
compteurs Succès/Rejeté par étape.

Couvre : chaque exécution d'étape écrit une trace avec statut+motif,
l'endpoint traces filtre par étape/statut company-scoped, les compteurs par
étape somment correctement, tests (rejet consentement, rejet fenêtre,
agrégats).
"""
from django.test import TestCase

from authentication.models import Company
from core.models import ConsentRecord

from apps.compta import services
from apps.marketing.models import (
    EtapeSequence, ExecutionEtapeSequence, SequenceRelance, SuppressionMarketing,
)
from apps.crm.models import Lead


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TracesSequenceTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt5', 'ZMKT5')
        self.seq = SequenceRelance.objects.create(company=self.co, nom='Seq')

    def test_execution_normale_trace_traite(self):
        lead = Lead.objects.create(
            company=self.co, nom='Lead1', email='lead1@x.ma')
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            canal=EtapeSequence.Canal.EMAIL)
        insc = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=lead.id)
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(
            execution.statut_trace, ExecutionEtapeSequence.StatutTrace.TRAITE)

    def test_rejet_consentement_refuse(self):
        lead = Lead.objects.create(
            company=self.co, nom='Lead2', email='lead2@x.ma')
        ConsentRecord.objects.create(
            company=self.co, subject_identifier='lead2@x.ma',
            purpose='email', granted=False)
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            canal=EtapeSequence.Canal.EMAIL)
        insc = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=lead.id)
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(
            execution.statut_trace, ExecutionEtapeSequence.StatutTrace.REJETE)
        self.assertEqual(
            execution.motif_rejet,
            ExecutionEtapeSequence.MotifRejet.SANS_CONSENTEMENT)

    def test_rejet_supprime(self):
        lead = Lead.objects.create(
            company=self.co, nom='Lead3', email='lead3@x.ma')
        SuppressionMarketing.objects.create(
            company=self.co, destinataire='lead3@x.ma')
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            canal=EtapeSequence.Canal.EMAIL)
        insc = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=lead.id)
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(
            execution.motif_rejet, ExecutionEtapeSequence.MotifRejet.SUPPRIME)

    def test_rejet_hors_fenetre_whatsapp(self):
        from apps.notifications.models import Holiday
        from django.utils import timezone
        lead = Lead.objects.create(
            company=self.co, nom='Lead4', whatsapp='0612345678')
        Holiday.objects.create(
            company=self.co, date=timezone.now().date(), nom='Test férié',
            recurrent_annuel=False)
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            canal=EtapeSequence.Canal.WHATSAPP)
        insc = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=lead.id)
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(
            execution.motif_rejet, ExecutionEtapeSequence.MotifRejet.HORS_FENETRE)

    def test_compteurs_par_etape(self):
        lead1 = Lead.objects.create(
            company=self.co, nom='L1', email='l1@x.ma')
        lead2 = Lead.objects.create(
            company=self.co, nom='L2', email='l2@x.ma')
        SuppressionMarketing.objects.create(
            company=self.co, destinataire='l2@x.ma')
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            canal=EtapeSequence.Canal.EMAIL)
        insc1 = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=lead1.id)
        insc2 = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=lead2.id)
        services._executer_une_etape(insc1, etape)
        services._executer_une_etape(insc2, etape)
        compteurs = services.compteurs_par_etape(self.seq)
        self.assertEqual(compteurs[0]['succes'], 1)
        self.assertEqual(compteurs[0]['rejete'], 1)

    def test_traces_filtre_par_statut(self):
        lead = Lead.objects.create(
            company=self.co, nom='L3', email='l3@x.ma')
        SuppressionMarketing.objects.create(
            company=self.co, destinataire='l3@x.ma')
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            canal=EtapeSequence.Canal.EMAIL)
        insc = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=lead.id)
        services._executer_une_etape(insc, etape)
        traces = services.traces_sequence(
            self.seq, statut_trace=ExecutionEtapeSequence.StatutTrace.REJETE)
        self.assertEqual(len(traces), 1)

    def test_traces_filtre_par_etape(self):
        lead = Lead.objects.create(
            company=self.co, nom='L4', email='l4@x.ma')
        etape1 = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            canal=EtapeSequence.Canal.EMAIL)
        etape2 = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=2, delai_jours=1,
            canal=EtapeSequence.Canal.APPEL)
        insc = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=lead.id)
        services._executer_une_etape(insc, etape1)
        services._executer_une_etape(insc, etape2)
        traces = services.traces_sequence(self.seq, etape_id=etape1.id)
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0]['etape_id'], etape1.id)
