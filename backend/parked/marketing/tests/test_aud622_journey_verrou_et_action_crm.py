"""AUD622 — moteur de journeys : verrou de tick + nœud ACTION réellement
câblé au CRM.

Deux constats :

1. ``executer_journeys_dus`` lisait les ``InscriptionSequence`` ACTIVES sans
   aucun verrou, et ``avancer_journey``/``_positionner`` sauvegardaient sans
   verrou non plus : deux ticks beat qui se chevauchent pouvaient avancer la
   MÊME inscription deux fois (deux ``ExecutionEtapeSequence`` pour le même
   nœud). Même schéma non corrigé côté moteur linéaire historique
   ``executer_etapes_dues`` — risque partagé, corrigé des deux côtés par
   cohérence.
2. ``NoeudJourney.Type.ACTION`` est libellé « Action (message / CRM) » et sa
   config documente ``action_crm``, mais la branche ne lisait QUE
   ``config['canal']`` pour tracer : aucune action CRM ne se produisait
   jamais, silencieusement — alors que le moteur linéaire (XMKT19) interprète
   ce même JSON depuis toujours.

Tests ROUGES d'abord : ``test_le_noeud_action_execute_reellement_action_crm``
ne changeait AUCUN stage de lead ; les deux tests de verrou ne voyaient ni
``FOR UPDATE`` ni ``SKIP LOCKED`` dans le SQL du tick.
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from authentication.models import Company

from apps.compta import services as compta_services
from apps.crm import stages
from apps.crm.models import Lead
from apps.marketing import services as mkt_services
from apps.marketing.models import (
    ArcJourney, EtapeSequence, ExecutionEtapeSequence, NoeudJourney,
    SequenceRelance,
)


class _BaseJourney(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud622', nom='AUD622')
        self.seq = SequenceRelance.objects.create(company=self.co, nom='J')
        self.lead = Lead.objects.create(
            company=self.co, nom='Lead', stage=stages.CONTACTED)

    def _noeud(self, type_noeud, **kwargs):
        return NoeudJourney.objects.create(
            company=self.co, sequence=self.seq, type_noeud=type_noeud,
            **kwargs)

    def _inscrire(self):
        return compta_services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=self.lead.id)


class NoeudActionCrmTests(_BaseJourney):
    def test_le_noeud_action_execute_reellement_action_crm(self):
        """ROUGE avant correctif : le stage du lead ne bougeait jamais."""
        depart = self._noeud(
            NoeudJourney.Type.ACTION, libelle='Qualifier',
            config={'action_crm': {
                'action': 'avancer_stage',
                'params': {'stage': stages.QUOTE_SENT}}})
        sortie = self._noeud(NoeudJourney.Type.SORTIE)
        ArcJourney.objects.create(company=self.co, source=depart,
                                  cible=sortie, ordre=1)

        mkt_services.avancer_journey(self._inscrire())

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

    def test_le_resultat_de_laction_est_trace(self):
        self._noeud(
            NoeudJourney.Type.ACTION, libelle='Taguer',
            config={'action_crm': {
                'action': 'tag', 'params': {'tag': 'chaud'}}})
        traces = mkt_services.avancer_journey(self._inscrire())
        self.lead.refresh_from_db()
        self.assertIn('chaud', self.lead.tags)
        self.assertEqual([t.resultat for t in traces], ['execute'])

    def test_action_inconnue_tracee_sans_planter_le_tick(self):
        self._noeud(
            NoeudJourney.Type.ACTION,
            config={'action_crm': {'action': 'nimporte_quoi'}})
        traces = mkt_services.avancer_journey(self._inscrire())
        self.assertEqual([t.resultat for t in traces], ['action_inconnue'])

    def test_lead_introuvable_tracee_sans_planter_le_tick(self):
        self._noeud(
            NoeudJourney.Type.ACTION,
            config={'action_crm': {
                'action': 'tag', 'params': {'tag': 'x'}}})
        inscription = self._inscrire()
        self.lead.delete()
        traces = mkt_services.avancer_journey(inscription)
        self.assertEqual([t.resultat for t in traces], ['lead_introuvable'])

    def test_noeud_action_sans_action_crm_inchange(self):
        """Non-régression : un nœud ACTION « message » garde exactement son
        comportement d'avant (trace planifiée portant le canal)."""
        self._noeud(NoeudJourney.Type.ACTION, config={'canal': 'email'})
        traces = mkt_services.avancer_journey(self._inscrire())
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].resultat, 'planifie')
        self.assertEqual(traces[0].canal, 'email')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_laction_crm_est_journalisee_au_chatter_du_lead(self):
        from apps.crm.models import LeadActivity

        self._noeud(
            NoeudJourney.Type.ACTION, libelle='Taguer',
            config={'action_crm': {
                'action': 'tag', 'params': {'tag': 'chaud'}}})
        mkt_services.avancer_journey(self._inscrire())
        self.assertTrue(
            LeadActivity.objects.filter(lead=self.lead).exists())


class VerrouDeTickTests(_BaseJourney):
    """Le verrou est prouvé sur le SQL RÉELLEMENT émis : c'est déterministe,
    là où deux threads concurrents seraient flaky."""

    def _sql_du_tick(self, appel):
        with CaptureQueriesContext(connection) as captures:
            appel()
        return [q['sql'] for q in captures.captured_queries]

    def test_le_tick_graphe_verrouille_les_inscriptions(self):
        """ROUGE avant correctif : aucun FOR UPDATE dans le tick graphe."""
        self._noeud(NoeudJourney.Type.ACTION, config={'canal': 'email'})
        self._inscrire()
        sqls = self._sql_du_tick(
            lambda: mkt_services.executer_journeys_dus(self.co))
        verrous = [
            s for s in sqls
            if 'inscriptionsequence' in s.lower()
            and 'FOR UPDATE' in s and 'SKIP LOCKED' in s
        ]
        self.assertTrue(verrous, f'aucun SELECT verrouillé parmi : {sqls}')

    def test_le_tick_lineaire_verrouille_aussi(self):
        """Le moteur historique portait le MÊME risque."""
        EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0)
        self._inscrire()
        sqls = self._sql_du_tick(
            lambda: compta_services.executer_etapes_dues(self.co))
        verrous = [
            s for s in sqls
            if 'inscriptionsequence' in s.lower()
            and 'FOR UPDATE' in s and 'SKIP LOCKED' in s
        ]
        self.assertTrue(verrous, f'aucun SELECT verrouillé parmi : {sqls}')

    def test_le_tick_graphe_reste_fonctionnel_sous_verrou(self):
        """Le verrou ne doit rien casser : une trace est bien produite."""
        self._noeud(NoeudJourney.Type.ACTION, config={'canal': 'email'})
        self._inscrire()
        traces = mkt_services.executer_journeys_dus(self.co)
        self.assertEqual(len(traces), 1)
        self.assertEqual(
            ExecutionEtapeSequence.objects.filter(company=self.co).count(), 1)
