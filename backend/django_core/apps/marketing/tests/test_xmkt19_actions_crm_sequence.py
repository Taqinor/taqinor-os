"""XMKT19 — Actions CRM dans les étapes de séquence.

Couvre : une séquence peut poser un tag à J3 et créer une tâche à J7, aucune
liste d'étapes hardcodée (import STAGES.py), chaque action journalisée dans
la trace du participant + le chatter.
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import EtapeSequence, ExecutionEtapeSequence, SequenceRelance
from apps.crm import stages
from apps.crm.models import Lead, LeadActivity


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ActionsCrmSequenceTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt19', 'XMKT19')
        self.seq = SequenceRelance.objects.create(company=self.co, nom='Seq')
        self.lead = Lead.objects.create(
            company=self.co, nom='Lead', stage=stages.CONTACTED)

    def _inscrire(self):
        return services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=self.lead.id)

    def test_action_tag_pose_tag_sur_lead(self):
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=3,
            type_etape=EtapeSequence.TypeEtape.ACTION_CRM,
            action_crm={'action': 'tag', 'params': {'tag': 'chaud'}})
        insc = self._inscrire()
        execution = services._executer_une_etape(insc, etape)
        self.lead.refresh_from_db()
        self.assertIn('chaud', self.lead.tags)
        self.assertEqual(execution.resultat, 'execute')

    def test_action_tache_cree_relance(self):
        date_relance = datetime.date.today() + datetime.timedelta(days=7)
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=7,
            type_etape=EtapeSequence.TypeEtape.ACTION_CRM,
            action_crm={
                'action': 'tache',
                'params': {'relance_date': date_relance.isoformat(),
                           'note': 'Relancer'}})
        insc = self._inscrire()
        services._executer_une_etape(insc, etape)
        self.lead.refresh_from_db()
        self.assertEqual(str(self.lead.relance_date), date_relance.isoformat())

    def test_action_avancer_stage_utilise_stages_py(self):
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            type_etape=EtapeSequence.TypeEtape.ACTION_CRM,
            action_crm={'action': 'avancer_stage',
                        'params': {'stage': stages.QUOTE_SENT}})
        insc = self._inscrire()
        services._executer_une_etape(insc, etape)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

    def test_action_score_ajuste_borne(self):
        self.lead.score = 95
        self.lead.save(update_fields=['score'])
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            type_etape=EtapeSequence.TypeEtape.ACTION_CRM,
            action_crm={'action': 'score', 'params': {'delta': 20}})
        insc = self._inscrire()
        services._executer_une_etape(insc, etape)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.score, 100)

    def test_action_inconnue_tracee(self):
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            type_etape=EtapeSequence.TypeEtape.ACTION_CRM,
            action_crm={'action': 'inexistante'})
        insc = self._inscrire()
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(execution.resultat, 'action_inconnue')

    def test_action_journalisee_dans_chatter_et_trace(self):
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            type_etape=EtapeSequence.TypeEtape.ACTION_CRM,
            action_crm={'action': 'tag', 'params': {'tag': 'test-trace'}})
        insc = self._inscrire()
        services._executer_une_etape(insc, etape)
        self.assertEqual(
            ExecutionEtapeSequence.objects.filter(inscription=insc).count(), 1)
        self.assertTrue(
            LeadActivity.objects.filter(lead=self.lead).exists())

    def test_lead_introuvable_ne_leve_pas(self):
        etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            type_etape=EtapeSequence.TypeEtape.ACTION_CRM,
            action_crm={'action': 'tag', 'params': {'tag': 'x'}})
        insc = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=999999)
        execution = services._executer_une_etape(insc, etape)
        self.assertEqual(execution.resultat, 'lead_introuvable')
