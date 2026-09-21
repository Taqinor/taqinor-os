"""NTMKT12 — Journey en graphe (nœuds + arcs), extension additive de
``SequenceRelance``.

Couvre :
  * le FALLBACK linéaire : une séquence SANS nœud graphe s'exécute exactement
    comme avant (moteur XMKT1 ``executer_etapes_dues``), et le tick graphe est
    un no-op strict pour elle ;
  * le MULTI-EMBRANCHEMENT : 3 nœuds / 2 arcs conditionnels routent selon la
    condition évaluée sur les traces XMKT2 (``EnvoiCampagne``) ;
  * le SCOPING multi-société : le tick d'une société ne touche jamais le
    graphe d'une autre.
"""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services as compta_services
from apps.marketing import services as mkt_services
from apps.marketing.models import (
    ArcJourney, Campagne, EnvoiCampagne, EtapeSequence,
    ExecutionEtapeSequence, InscriptionSequence, NoeudJourney,
    SequenceRelance,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FallbackLineaireTests(TestCase):
    """Une séquence sans graphe garde le comportement XMKT1 à l'identique."""

    def setUp(self):
        self.co = make_company('ntmkt12a', 'NTMKT12 A')
        self.seq = SequenceRelance.objects.create(company=self.co, nom='Linéaire')
        self.etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=0,
            canal=EtapeSequence.Canal.APPEL)

    def test_moteur_lineaire_inchange(self):
        insc = compta_services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=1)
        self.assertEqual(insc.etape_courante_id, self.etape.id)
        executions = compta_services.executer_etapes_dues(self.co)
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0].etape_id, self.etape.id)
        self.assertIsNone(executions[0].noeud_id)

    def test_tick_graphe_est_un_noop_sans_noeud(self):
        compta_services.inscrire_lead_sequence(self.co, self.seq, lead_id=2)
        self.assertFalse(mkt_services.sequence_a_graphe(self.seq))
        self.assertEqual(mkt_services.executer_journeys_dus(self.co), [])
        self.assertEqual(ExecutionEtapeSequence.objects.filter(
            noeud__isnull=False).count(), 0)


class MultiEmbranchementTests(TestCase):
    """3 nœuds + 2 arcs conditionnels : le routage suit la trace XMKT2."""

    def setUp(self):
        self.co = make_company('ntmkt12b', 'NTMKT12 B')
        self.seq = SequenceRelance.objects.create(company=self.co, nom='Graphe')
        self.declencheur = NoeudJourney.objects.create(
            company=self.co, sequence=self.seq,
            type_noeud=NoeudJourney.Type.DECLENCHEUR, libelle='Départ')
        self.si_ouvert = NoeudJourney.objects.create(
            company=self.co, sequence=self.seq,
            type_noeud=NoeudJourney.Type.ACTION, libelle='Merci',
            config={'canal': 'email'})
        self.sinon = NoeudJourney.objects.create(
            company=self.co, sequence=self.seq,
            type_noeud=NoeudJourney.Type.ACTION, libelle='Relance',
            config={'canal': 'whatsapp'})
        ArcJourney.objects.create(
            company=self.co, source=self.declencheur, cible=self.si_ouvert,
            condition=ArcJourney.Condition.A_OUVERT, ordre=1)
        ArcJourney.objects.create(
            company=self.co, source=self.declencheur, cible=self.sinon,
            condition=ArcJourney.Condition.TOUJOURS, ordre=2)

    def _inscrire(self, lead_id=7):
        return compta_services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=lead_id)

    def _tracer_ouverture(self, lead_id, inscription):
        campagne = Campagne.objects.create(company=self.co, nom='C')
        EnvoiCampagne.objects.create(
            company=self.co, campagne=campagne,
            contact_ref=f'lead:{lead_id}', destinataire='a@b.ma',
            ouvert_le=inscription.declenchee_le + timezone.timedelta(hours=1))

    def test_inscription_graphe_ignoree_par_le_moteur_lineaire(self):
        insc = self._inscrire()
        # Pas d'EtapeSequence → etape_courante NULL → le tick XMKT1 l'ignore.
        self.assertIsNone(insc.etape_courante_id)
        self.assertEqual(compta_services.executer_etapes_dues(self.co), [])

    def test_branche_a_ouvert(self):
        insc = self._inscrire(lead_id=11)
        self._tracer_ouverture(11, insc)
        traces = mkt_services.executer_journeys_dus(self.co)
        self.assertEqual([t.noeud_id for t in traces], [self.si_ouvert.id])
        self.assertEqual(traces[0].canal, 'email')

    def test_branche_par_defaut_sans_ouverture(self):
        self._inscrire(lead_id=12)
        traces = mkt_services.executer_journeys_dus(self.co)
        self.assertEqual([t.noeud_id for t in traces], [self.sinon.id])
        self.assertEqual(traces[0].canal, 'whatsapp')

    def test_parcours_se_termine_en_bout_de_graphe(self):
        insc = self._inscrire(lead_id=13)
        mkt_services.executer_journeys_dus(self.co)
        insc.refresh_from_db()
        self.assertEqual(insc.statut, InscriptionSequence.Statut.TERMINE)
        self.assertIsNone(insc.noeud_courant_id)
        # Deuxième tick : plus rien à faire (idempotent).
        self.assertEqual(mkt_services.executer_journeys_dus(self.co), [])

    def test_noeud_attente_bloque_puis_libere(self):
        seq = SequenceRelance.objects.create(company=self.co, nom='Attente')
        depart = NoeudJourney.objects.create(
            company=self.co, sequence=seq,
            type_noeud=NoeudJourney.Type.ATTENTE,
            config={'delai_jours': 3})
        action = NoeudJourney.objects.create(
            company=self.co, sequence=seq,
            type_noeud=NoeudJourney.Type.ACTION, config={'canal': 'email'})
        ArcJourney.objects.create(
            company=self.co, source=depart, cible=action,
            condition=ArcJourney.Condition.TOUJOURS)
        compta_services.inscrire_lead_sequence(self.co, seq, lead_id=14)
        maintenant = timezone.now()
        self.assertEqual(
            mkt_services.executer_journeys_dus(self.co, maintenant=maintenant),
            [])
        plus_tard = maintenant + timezone.timedelta(days=4)
        traces = mkt_services.executer_journeys_dus(
            self.co, maintenant=plus_tard)
        self.assertEqual([t.noeud_id for t in traces], [action.id])

    def test_noeud_sortie_termine_sans_trace(self):
        seq = SequenceRelance.objects.create(company=self.co, nom='Sortie')
        depart = NoeudJourney.objects.create(
            company=self.co, sequence=seq,
            type_noeud=NoeudJourney.Type.DECLENCHEUR)
        sortie = NoeudJourney.objects.create(
            company=self.co, sequence=seq,
            type_noeud=NoeudJourney.Type.SORTIE)
        ArcJourney.objects.create(
            company=self.co, source=depart, cible=sortie,
            condition=ArcJourney.Condition.TOUJOURS)
        insc = compta_services.inscrire_lead_sequence(
            self.co, seq, lead_id=15)
        self.assertEqual(mkt_services.executer_journeys_dus(self.co), [])
        insc.refresh_from_db()
        self.assertEqual(insc.statut, InscriptionSequence.Statut.TERMINE)


class ScopingSocieteTests(TestCase):
    def test_le_tick_ne_traverse_jamais_les_societes(self):
        co_a = make_company('ntmkt12c', 'NTMKT12 C')
        co_b = make_company('ntmkt12d', 'NTMKT12 D')
        seq_b = SequenceRelance.objects.create(company=co_b, nom='B')
        depart = NoeudJourney.objects.create(
            company=co_b, sequence=seq_b,
            type_noeud=NoeudJourney.Type.ACTION, config={'canal': 'email'})
        ArcJourney.objects.create(
            company=co_b, source=depart, cible=depart,
            condition=ArcJourney.Condition.TAG_PRESENT, valeur='inexistant')
        compta_services.inscrire_lead_sequence(co_b, seq_b, lead_id=21)
        # Le tick de la société A ne voit rien du graphe de B.
        self.assertEqual(mkt_services.executer_journeys_dus(co_a), [])
        traces = mkt_services.executer_journeys_dus(co_b)
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].company_id, co_b.id)
