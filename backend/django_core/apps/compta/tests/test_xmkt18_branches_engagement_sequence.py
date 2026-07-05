"""XMKT18 — Branches d'engagement dans les séquences.

Couvre : une étape conditionnelle ne s'exécute que si la condition est vraie
au moment dû, le cas « non ouvert → renvoi » et « cliqué → tâche
commerciale » fonctionnent, la trace par participant montre la branche
prise.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    Campagne, EnvoiCampagne, EtapeSequence, ExecutionEtapeSequence,
    SequenceRelance,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class BranchesEngagementSequenceTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt18', 'XMKT18')
        self.seq = SequenceRelance.objects.create(company=self.co, nom='Seq')

    def _inscrire(self):
        insc = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=42, lead_reference='Lead 42')
        return insc

    def test_condition_toujours_execute(self):
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            condition=EtapeSequence.Condition.TOUJOURS)
        insc = self._inscrire()
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(execution.branche_prise, 'condition')
        self.assertNotEqual(execution.resultat, 'condition_fausse')

    def test_non_ouvert_apres_delai_renvoi(self):
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=3,
            condition=EtapeSequence.Condition.N_A_PAS_OUVERT,
            action_alternative='renvoyer:Nouvel objet')
        insc = self._inscrire()
        # Aucun EnvoiCampagne ouvert pour ce lead → condition vraie
        # (n'a pas ouvert).
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(execution.branche_prise, 'condition')

    def test_ouvert_bloque_n_a_pas_ouvert_bascule_alternative(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        insc = self._inscrire()
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='a@x.ma',
            contact_ref=f'lead:{insc.lead_id}',
            ouvert_le=timezone.now())
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            condition=EtapeSequence.Condition.N_A_PAS_OUVERT,
            action_alternative='renvoyer:Nouvel objet')
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(execution.branche_prise, 'alternative')
        self.assertEqual(execution.resultat, 'condition_fausse')

    def test_clique_cree_tache_commerciale(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL)
        insc = self._inscrire()
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='a@x.ma',
            contact_ref=f'lead:{insc.lead_id}',
            clique_le=timezone.now())
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            condition=EtapeSequence.Condition.A_CLIQUE)
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(execution.branche_prise, 'condition')

    def test_condition_a_clique_fausse_sans_trace(self):
        insc = self._inscrire()
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            condition=EtapeSequence.Condition.A_CLIQUE,
            action_alternative='tache_commerciale')
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(execution.branche_prise, 'alternative')

    def test_trace_visible_via_executions(self):
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0)
        insc = self._inscrire()
        services._executer_une_etape(insc, etape)
        self.assertEqual(
            ExecutionEtapeSequence.objects.filter(inscription=insc).count(), 1)

    def test_condition_evaluee_au_moment_du(self):
        insc = self._inscrire()
        insc.declenchee_le = timezone.now() - datetime.timedelta(days=5)
        insc.save(update_fields=['declenchee_le'])
        camp = Campagne.objects.create(
            company=self.co, nom='C3', canal=Campagne.Canal.EMAIL)
        # Ouverture ANTÉRIEURE au déclenchement — ne doit pas compter.
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='a@x.ma',
            contact_ref=f'lead:{insc.lead_id}',
            ouvert_le=timezone.now() - datetime.timedelta(days=10))
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            condition=EtapeSequence.Condition.A_OUVERT)
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(execution.branche_prise, 'alternative')
