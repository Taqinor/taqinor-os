"""NTMKT14 — Nœud « attente jusqu'à » (date absolue / prochain jour ouvré).

Le calcul du prochain créneau ouvré passe par
``apps.notifications.selectors.est_hors_fenetre_silence`` (jours fériés +
jours ouvrés de la société) — jamais un import des modèles notifications.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services as compta_services
from apps.marketing import services as mkt_services
from apps.marketing.models import ArcJourney, NoeudJourney, SequenceRelance


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ProchaineEcheanceOuvreeTests(TestCase):
    def setUp(self):
        self.co = make_company('ntmkt14', 'NTMKT14')

    def _local(self, *args):
        return timezone.make_aware(
            datetime.datetime(*args), timezone.get_current_timezone())

    def test_prochain_lundi_9h(self):
        # Vendredi 12h -> lundi 9h (samedi/dimanche non ouvrés).
        vendredi = self._local(2026, 7, 10, 12, 0)
        self.assertEqual(vendredi.weekday(), 4)
        echeance = mkt_services.prochaine_echeance_ouvree(
            vendredi, self.co, heure=9, jour_semaine=0)
        self.assertEqual(echeance.weekday(), 0)
        self.assertEqual(echeance.hour, 9)
        self.assertGreater(echeance, vendredi)

    def test_prochain_jour_ouvre_saute_le_week_end(self):
        vendredi = self._local(2026, 7, 10, 15, 0)
        echeance = mkt_services.prochaine_echeance_ouvree(
            vendredi, self.co, heure=9)
        self.assertNotIn(echeance.weekday(), (5, 6))
        self.assertEqual(echeance.hour, 9)

    def test_meme_jour_si_heure_pas_encore_passee(self):
        mardi = self._local(2026, 7, 7, 7, 0)
        echeance = mkt_services.prochaine_echeance_ouvree(
            mardi, self.co, heure=9)
        self.assertEqual(echeance.date(), mardi.date())
        self.assertEqual(echeance.hour, 9)


class NoeudAttenteJusquATests(TestCase):
    def setUp(self):
        self.co = make_company('ntmkt14b', 'NTMKT14 B')
        self.seq = SequenceRelance.objects.create(company=self.co, nom='Jusque')
        self.attente = NoeudJourney.objects.create(
            company=self.co, sequence=self.seq,
            type_noeud=NoeudJourney.Type.ATTENTE_JUSQU_A,
            config={'mode': 'jour_ouvre', 'heure': 9, 'jour_semaine': 0})
        self.action = NoeudJourney.objects.create(
            company=self.co, sequence=self.seq,
            type_noeud=NoeudJourney.Type.ACTION, config={'canal': 'email'})
        ArcJourney.objects.create(
            company=self.co, source=self.attente, cible=self.action,
            condition=ArcJourney.Condition.TOUJOURS)

    def test_retarde_puis_libere_au_prochain_lundi(self):
        insc = compta_services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=31)
        maintenant = timezone.make_aware(
            datetime.datetime(2026, 7, 10, 12, 0),
            timezone.get_current_timezone())
        self.assertEqual(
            mkt_services.executer_journeys_dus(self.co, maintenant=maintenant),
            [])
        insc.refresh_from_db()
        echeance = mkt_services.echeance_noeud(insc, self.attente)
        self.assertEqual(echeance.weekday(), 0)
        traces = mkt_services.executer_journeys_dus(
            self.co, maintenant=echeance + datetime.timedelta(minutes=1))
        self.assertEqual([t.noeud_id for t in traces], [self.action.id])

    def test_mode_date_absolue(self):
        cible = timezone.now() + datetime.timedelta(days=2)
        self.attente.config = {'mode': 'date', 'date': cible.isoformat()}
        self.attente.save(update_fields=['config'])
        insc = compta_services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=32)
        self.assertEqual(mkt_services.executer_journeys_dus(self.co), [])
        traces = mkt_services.executer_journeys_dus(
            self.co, maintenant=cible + datetime.timedelta(minutes=1))
        self.assertEqual([t.noeud_id for t in traces], [self.action.id])
        insc.refresh_from_db()
        self.assertIsNone(insc.noeud_courant_id)

    def test_date_illisible_ne_bloque_jamais_le_parcours(self):
        self.attente.config = {'mode': 'date', 'date': 'pas-une-date'}
        self.attente.save(update_fields=['config'])
        compta_services.inscrire_lead_sequence(self.co, self.seq, lead_id=33)
        traces = mkt_services.executer_journeys_dus(self.co)
        self.assertEqual([t.noeud_id for t in traces], [self.action.id])
