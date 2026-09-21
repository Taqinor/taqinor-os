"""CAD120 — les heures calmes des notifications, enfin visibles et testées.

Audit L3 du 21/09/2026, section CAD-K. La cadence de suivi client est réglée
au quart d'heure près (message 08:30, appel 09:00, dimanche 16-19 h) mais les
notifications partent à n'importe quelle heure : un client qui lit sa
proposition à 23 h déclenche un push immédiat sur le téléphone du
responsable. La garde existe depuis VX209
(``services._in_quiet_hours_non_critique``) et retombe à False sans le
réglage, dont le défaut est ``'0'`` et qui n'apparaissait dans AUCUN fichier
d'exemple : personne ne savait qu'elle existait.

Ce fichier couvre LES DEUX valeurs, et les deux choses qui ne changent
jamais : la cloche in-app reste alimentée, et un événement CRITIQUE passe
même à 3 h du matin.
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

#: Mardi 15 septembre 2026 — jour ouvré.
NUIT = datetime.datetime(2026, 9, 15, 23, 0, tzinfo=datetime.timezone.utc)
JOURNEE = datetime.datetime(2026, 9, 15, 12, 0, tzinfo=datetime.timezone.utc)


class EnvExempleTests(SimpleTestCase):
    """« Le réglage figure dans `.env.example` avec son commentaire. »"""

    def setUp(self):
        self.texte = (RACINE_DEPOT / '.env.example').read_text(
            encoding='utf-8')

    def test_le_reglage_est_present_avec_le_defaut_daujourdhui(self):
        self.assertIn('NOTIFICATIONS_QUIET_HOURS_ENABLED=0', self.texte)

    def test_les_deux_valeurs_sont_expliquees(self):
        """Un réglage sans son commentaire ne se décide pas : il se subit."""
        bloc = self.texte.split('NOTIFICATIONS_QUIET_HOURS_ENABLED=0')[0]
        bloc = bloc[bloc.rindex('# CAD120'):]
        for attendu in ('24 h/24', 'heures calmes', 'cloche in-app',
                        'CRITIQUE', 'FONDATEUR'):
            self.assertIn(attendu, bloc, attendu)


class HeuresCalmesTests(TestCase):
    def setUp(self):
        # Import local : `freezegun` n'est pas installé sur tous les postes,
        # et les tests de `.env.example` ci-dessus doivent rester exécutables
        # sans lui.
        from testkit.time import frozen
        self.frozen = frozen
        self.company, _ = Company.objects.get_or_create(
            slug='cad120', defaults={'nom': 'cad120'})
        CompanyProfile.objects.get_or_create(company=self.company)

    def _silencieux(self, moment, event_type=EventType.DEVIS_OPENED):
        gel = self.frozen(moment)
        gel.start()
        try:
            return services._in_quiet_hours_non_critique(
                event_type, self.company, True)
        finally:
            gel.stop()

    # ── Valeur 0 : 24 h/24 assumé (le comportement d'aujourd'hui) ──────────
    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False)
    def test_reglage_a_zero_rien_nest_mis_en_sourdine_meme_a_23h(self):
        self.assertFalse(self._silencieux(NUIT))

    # ── Valeur 1 : heures calmes en production ────────────────────────────
    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
    def test_reglage_a_un_les_canaux_hors_app_se_taisent_la_nuit(self):
        self.assertTrue(self._silencieux(NUIT))

    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
    def test_reglage_a_un_en_pleine_journee_ouvree_rien_ne_change(self):
        self.assertFalse(self._silencieux(JOURNEE))

    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
    def test_un_evenement_critique_passe_meme_la_nuit(self):
        """Une urgence réelle ne se met jamais en sourdine."""
        self.assertFalse(
            self._silencieux(NUIT, event_type=EventType.INCIDENT_CRITICAL))

    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
    def test_un_appelant_qui_refuse_les_heures_calmes_est_respecte(self):
        gel = self.frozen(NUIT)
        gel.start()
        try:
            self.assertFalse(services._in_quiet_hours_non_critique(
                EventType.DEVIS_OPENED, self.company, False))
        finally:
            gel.stop()
