"""CAD120 → N1 — le réglage des heures de travail des notifications, visible
et testé.

CAD120 (audit L3 du 21/09/2026) avait rendu visible dans `.env.example` le
drapeau `NOTIFICATIONS_QUIET_HOURS_ENABLED` (VX209), éteint par défaut et qui,
allumé, SUPPRIMAIT les canaux hors-app la nuit en laissant passer les
événements critiques. Décision fondateur du 25/09/2026 (N1) : « les
notifications ne doivent pas être à minuit ni 23 h — garde toutes les
notifications importantes mais place-les aux heures de travail ». Le drapeau
est désormais ALLUMÉ par défaut et REPORTE au prochain créneau ouvré au lieu
de supprimer ; la sévérité n'exempte plus rien.

Ce fichier couvre LES DEUX valeurs au niveau de la décision
(`services._report_hors_fenetre`) ; le parcours complet (création différée,
cloche, balayage) est dans `tests_n1_report_heures_ouvrees.py`.
"""
import datetime
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings

from authentication.models import Company

from apps.notifications import services
from apps.notifications.models import EventType
from apps.parametres.models import CompanyProfile

#: Racine du dépôt : …/backend/django_core/apps/notifications/<ce fichier>.
RACINE_DEPOT = Path(__file__).resolve().parents[4]

#: Mardi 15 septembre 2026 — jour ouvré (heures UTC : ce jour-là le Maroc
#: était encore à UTC+1, 23:00 UTC = minuit local, 12:00 UTC = 13:00 local).
NUIT = datetime.datetime(2026, 9, 15, 23, 0, tzinfo=datetime.timezone.utc)
JOURNEE = datetime.datetime(2026, 9, 15, 12, 0, tzinfo=datetime.timezone.utc)
#: Samedi 3 octobre 2026, 17:49 UTC — l'arrivée réelle du lead « Chance »,
#: annoncée seulement le lundi 08:30 avant l'exception du 04/10/2026.
SAMEDI = datetime.datetime(2026, 10, 3, 17, 49, tzinfo=datetime.timezone.utc)


class EnvExempleTests(SimpleTestCase):
    """« Le réglage figure dans `.env.example` avec son commentaire. »"""

    def setUp(self):
        self.texte = (RACINE_DEPOT / '.env.example').read_text(
            encoding='utf-8')

    def test_le_reglage_est_present_allume(self):
        self.assertIn('NOTIFICATIONS_QUIET_HOURS_ENABLED=1', self.texte)

    def test_les_deux_valeurs_sont_expliquees(self):
        """Un réglage sans son commentaire ne se décide pas : il se subit."""
        bloc = self.texte.split('NOTIFICATIONS_QUIET_HOURS_ENABLED=1')[0]
        bloc = bloc[bloc.rindex('# N1'):]
        for attendu in ('REPORTEE AU PROCHAIN CRENEAU OUVRE', '24 h/24',
                        'cloche in-app', 'CRITIQUE', 'FONDATEUR', 'SECURITE'):
            self.assertIn(attendu, bloc, attendu)

    def test_lexception_des_leads_est_documentee(self):
        self.assertIn(
            '# NOTIFICATIONS_TOUJOURS_IMMEDIATES=lead_new,lead_assigned,'
            'lead_callback_requested', self.texte)


class DecisionDeReportTests(TestCase):
    def setUp(self):
        # Import local : `freezegun` n'est pas installé sur tous les postes,
        # et les tests de `.env.example` ci-dessus doivent rester exécutables
        # sans lui.
        from testkit.time import frozen
        self.frozen = frozen
        self.company, _ = Company.objects.get_or_create(
            slug='cad120', defaults={'nom': 'cad120'})
        CompanyProfile.objects.get_or_create(company=self.company)

    def _report(self, moment, event_type=EventType.DEVIS_OPENED,
                respect=True):
        gel = self.frozen(moment)
        gel.start()
        try:
            return services._report_hors_fenetre(
                event_type, self.company, respect)
        finally:
            gel.stop()

    # ── Valeur 0 : 24 h/24 (urgence / débogage) ───────────────────────────
    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False)
    def test_reglage_a_zero_rien_nest_reporte_meme_la_nuit(self):
        self.assertIsNone(self._report(NUIT))

    # ── Valeur 1 : report au prochain créneau ouvré (défaut) ──────────────
    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
    def test_reglage_a_un_la_nuit_est_reportee_au_lendemain(self):
        report = self._report(NUIT)
        self.assertIsNotNone(report)
        self.assertGreater(report, NUIT)

    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
    def test_reglage_a_un_en_pleine_journee_ouvree_rien_ne_change(self):
        self.assertIsNone(self._report(JOURNEE))

    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
    def test_un_evenement_critique_est_reporte_lui_aussi(self):
        """N1 — « aux heures de travail » : la sévérité n'exempte plus."""
        self.assertIsNotNone(
            self._report(NUIT, event_type=EventType.INCIDENT_CRITICAL))

    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
    def test_un_appelant_qui_refuse_le_report_est_respecte(self):
        self.assertIsNone(self._report(NUIT, respect=False))

    # ── Exception fondateur du 04/10/2026 : les alertes de lead partent ──
    # ── tout de suite, nuit et week-end compris.                        ──
    def test_les_alertes_de_lead_sont_immediates_par_defaut(self):
        from django.conf import settings
        for cle in (EventType.LEAD_NEW, EventType.LEAD_ASSIGNED,
                    EventType.LEAD_CALLBACK_REQUESTED):
            self.assertIn(cle, settings.NOTIFICATIONS_TOUJOURS_IMMEDIATES)

    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
    def test_un_lead_du_samedi_soir_est_annonce_tout_de_suite(self):
        self.assertIsNotNone(self._report(SAMEDI))  # le reste attend lundi
        for cle in (EventType.LEAD_NEW, EventType.LEAD_ASSIGNED):
            self.assertIsNone(self._report(SAMEDI, event_type=cle), cle)
            self.assertIsNone(self._report(NUIT, event_type=cle), cle)
