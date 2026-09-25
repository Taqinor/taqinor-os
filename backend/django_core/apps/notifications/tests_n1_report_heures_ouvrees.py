"""N1 — les notifications partent aux heures de travail, jamais la nuit.

Décision fondateur du 25/09/2026 : « Les notifications ne doivent pas être à
minuit ni 23 h. Garde toutes les notifications importantes mais place-les aux
heures de travail. »

Avant N1, la garde VX209 était ÉTEINTE par défaut et, allumée, elle
SUPPRIMAIT les canaux hors-app d'une notification de nuit au lieu de les
reporter (et exemptait les événements « critiques »). Ce module verrouille le
nouveau contrat :

  * hors de la fenêtre de MESSAGES de la société (`crm.horaires` : jours
    ouvrés, fériés, Ramadan), la notification est CRÉÉE mais DIFFÉRÉE au
    prochain créneau ouvré — ni cloche, ni compteur, ni e-mail avant ;
  * dans la fenêtre, elle part tout de suite ;
  * le balayage `notifications.livrer_differees` livre EXACTEMENT ce qui est
    échu, une seule fois ;
  * le drapeau à 0 rend l'envoi immédiat, à toute heure.

Horloge gelée partout : ces tests parlent d'heures précises.
"""
import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company
from testkit.time import frozen

from apps.notifications import selectors, services
from apps.notifications.models import (
    EventType, Holiday, Notification, NotificationPreference,
)
from apps.parametres.models import CompanyProfile

User = get_user_model()

CASA = ZoneInfo('Africa/Casablanca')


def _t(annee, mois, jour, heure, minute=0):
    return datetime.datetime(annee, mois, jour, heure, minute, tzinfo=CASA)


#: Mardi 29 septembre 2026 — jour ouvré ordinaire.
MARDI_23H10 = _t(2026, 9, 29, 23, 10)
MARDI_10H = _t(2026, 9, 29, 10, 0)
MARDI_16H = _t(2026, 9, 29, 16, 0)
MERCREDI_08H30 = _t(2026, 9, 30, 8, 30)
MERCREDI_08H35 = _t(2026, 9, 30, 8, 35)
MERCREDI_09H = _t(2026, 9, 30, 9, 0)
JEUDI_08H30 = _t(2026, 10, 1, 8, 30)
#: Dimanche 4 octobre 2026 → lundi 5 octobre.
DIMANCHE_11H = _t(2026, 10, 4, 11, 0)
LUNDI_08H30 = _t(2026, 10, 5, 8, 30)

URL_LISTE = '/api/django/notifications/notifications/'
URL_COMPTEUR = '/api/django/notifications/notifications/unread-count/'


class _Base(TestCase):
    slug = 'n1-report'

    def setUp(self):
        self.company = Company.objects.create(
            nom='N1 Solaire', slug=self.slug)
        self.profil, _ = CompanyProfile.objects.get_or_create(
            company=self.company)
        self.meryem = User.objects.create_user(
            username=f'{self.slug}-meryem', password='x',
            email='meryem@example.com', role_legacy='responsable',
            company=self.company)

    def _notifier(self, moment, event_type=EventType.RELANCE_DUE, **kw):
        """Émet à `moment` (horloge gelée) ; renvoie (notification, mock
        e-mail). `relance_due` a l'e-mail activé par défaut (MRY17)."""
        with frozen(moment):
            with mock.patch.object(
                    services, '_dispatch_email', return_value=True) as email:
                n = services.notify(
                    self.meryem, event_type, 'Relances du jour',
                    body='3 relances', link='/crm/cockpit',
                    company=self.company, **kw)
        return n, email

    def _api(self):
        client = APIClient()
        client.force_authenticate(self.meryem)
        return client


@override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
class ReportHorsFenetreTests(_Base):

    def test_emise_a_23h10_creee_mais_differee_au_lendemain_08h30(self):
        n, email = self._notifier(MARDI_23H10)
        self.assertIsNotNone(n)
        n.refresh_from_db()
        self.assertEqual(n.programmee_pour, MERCREDI_08H30)
        email.assert_not_called()

    def test_une_notification_differee_est_invisible_dans_la_cloche(self):
        self._notifier(MARDI_23H10)
        with frozen(MARDI_23H10):
            client = self._api()
            compteur = client.get(URL_COMPTEUR)
            liste = client.get(URL_LISTE)
        self.assertEqual(compteur.status_code, 200)
        self.assertEqual(compteur.data['unread'], 0)
        resultats = (liste.data['results'] if 'results' in liste.data
                     else liste.data)
        self.assertEqual(len(resultats), 0)

    def test_emise_a_10h_part_immediatement(self):
        n, email = self._notifier(MARDI_10H)
        n.refresh_from_db()
        self.assertIsNone(n.programmee_pour)
        email.assert_called_once()

    def test_emise_un_dimanche_part_le_lundi_a_louverture(self):
        n, email = self._notifier(DIMANCHE_11H)
        n.refresh_from_db()
        self.assertEqual(n.programmee_pour, LUNDI_08H30)
        email.assert_not_called()

    def test_un_jour_ferie_est_saute(self):
        Holiday.objects.create(
            company=self.company, date=datetime.date(2026, 9, 30),
            nom='Férié de test')
        n, _email = self._notifier(MARDI_23H10)
        n.refresh_from_db()
        self.assertEqual(n.programmee_pour, JEUDI_08H30)

    def test_pendant_le_ramadan_louverture_du_ramadan_fait_foi(self):
        """Fenêtre du Ramadan (défaut 09:00-15:00, CAD38/CAD39) : commune
        aux messages et aux appels."""
        self.profil.ramadan_debut = datetime.date(2026, 9, 28)
        self.profil.ramadan_fin = datetime.date(2026, 10, 10)
        self.profil.save(update_fields=['ramadan_debut', 'ramadan_fin'])
        for moment in (MARDI_23H10, MARDI_16H):
            with self.subTest(emise=moment):
                n, email = self._notifier(moment)
                n.refresh_from_db()
                self.assertEqual(n.programmee_pour, MERCREDI_09H)
                email.assert_not_called()

    def test_un_evenement_critique_attend_lui_aussi_louverture(self):
        """Décision fondateur : « aux heures de travail », sans exemption de
        sévérité (VX209 laissait passer les critiques à 3 h du matin)."""
        n, email = self._notifier(
            MARDI_23H10, event_type=EventType.PREMIER_CONTACT_DEPASSE)
        n.refresh_from_db()
        self.assertEqual(n.programmee_pour, MERCREDI_08H30)
        email.assert_not_called()

    def test_une_alerte_de_securite_part_a_toute_heure(self):
        n, email = self._notifier(MARDI_23H10, respect_quiet_hours=False)
        n.refresh_from_db()
        self.assertIsNone(n.programmee_pour)
        email.assert_called_once()

    @override_settings(NOTIFICATIONS_TOUJOURS_IMMEDIATES=('relance_due',))
    def test_la_liste_des_exceptions_part_immediatement(self):
        n, email = self._notifier(MARDI_23H10)
        n.refresh_from_db()
        self.assertIsNone(n.programmee_pour)
        email.assert_called_once()

    def test_in_app_coupe_la_ligne_ne_sert_que_de_support(self):
        """In-app coupé, e-mail actif : `notify` renvoie None (contrat
        historique) mais l'e-mail n'est pas perdu — il part au réveil, puis
        la ligne support disparaît."""
        NotificationPreference.objects.create(
            company=self.company, user=self.meryem,
            event_type=EventType.RELANCE_DUE, in_app=False, email=True)
        n, email = self._notifier(MARDI_23H10)
        self.assertIsNone(n)
        email.assert_not_called()
        self.assertEqual(Notification.objects.filter(
            recipient=self.meryem, event_type=EventType.RELANCE_DUE,
            programmee_pour__isnull=False).count(), 1)
        with mock.patch.object(
                services, '_dispatch_email', return_value=True) as email:
            livrees = services.livrer_notifications_differees(
                now=MERCREDI_08H35)
        self.assertEqual(livrees, 1)
        email.assert_called_once()
        self.assertFalse(Notification.objects.filter(
            recipient=self.meryem,
            event_type=EventType.RELANCE_DUE).exists())


class DrapeauAZeroTests(_Base):
    slug = 'n1-drapeau'

    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False)
    def test_drapeau_a_zero_tout_part_immediatement_meme_a_23h(self):
        n, email = self._notifier(MARDI_23H10)
        n.refresh_from_db()
        self.assertIsNone(n.programmee_pour)
        email.assert_called_once()

    def test_sous_le_test_runner_le_report_est_coupe_par_defaut(self):
        """Un `.env` local ne doit jamais rendre la suite dépendante de
        l'heure : le défaut de production (ALLUMÉ) ne vaut pas ici."""
        self.assertFalse(settings.NOTIFICATIONS_QUIET_HOURS_ENABLED)


@override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
class LivraisonDiffereeTests(_Base):
    slug = 'n1-livraison'

    def test_le_balayage_livre_exactement_ce_qui_est_echu(self):
        echue, _ = self._notifier(MARDI_23H10)         # → mercredi 08:30
        plus_tard, _ = self._notifier(_t(2026, 9, 30, 21, 0))  # → jeudi
        with mock.patch.object(
                services, '_dispatch_email', return_value=True) as email:
            livrees = services.livrer_notifications_differees(
                now=MERCREDI_08H35)
        self.assertEqual(livrees, 1)
        email.assert_called_once()
        echue.refresh_from_db()
        plus_tard.refresh_from_db()
        self.assertIsNone(echue.programmee_pour)
        # Reçue à 08:35, elle ne s'affiche pas « 23:10 » dans la cloche.
        self.assertEqual(echue.created_at, MERCREDI_08H35)
        self.assertEqual(plus_tard.programmee_pour, JEUDI_08H30)

    def test_le_balayage_est_idempotent(self):
        self._notifier(MARDI_23H10)
        with mock.patch.object(
                services, '_dispatch_email', return_value=True) as email:
            premier = services.livrer_notifications_differees(
                now=MERCREDI_08H35)
            second = services.livrer_notifications_differees(
                now=MERCREDI_08H35)
        self.assertEqual((premier, second), (1, 0))
        email.assert_called_once()

    def test_rien_nest_livre_avant_lecheance(self):
        self._notifier(MARDI_23H10)
        with mock.patch.object(
                services, '_dispatch_email', return_value=True) as email:
            livrees = services.livrer_notifications_differees(
                now=_t(2026, 9, 30, 8, 29))
        self.assertEqual(livrees, 0)
        email.assert_not_called()

    def test_une_fois_livree_elle_apparait_dans_la_cloche(self):
        self._notifier(MARDI_23H10)
        with mock.patch.object(services, '_dispatch_email', return_value=True):
            services.livrer_notifications_differees(now=MERCREDI_08H35)
        with frozen(MERCREDI_08H35):
            compteur = self._api().get(URL_COMPTEUR)
        self.assertEqual(compteur.data['unread'], 1)

    def test_la_tache_beat_delegue_au_service(self):
        from apps.notifications.sweeps import livrer_differees
        self._notifier(MARDI_23H10)
        with mock.patch.object(services, '_dispatch_email', return_value=True):
            self.assertEqual(livrer_differees(now=MERCREDI_08H35), 1)

    def test_une_mention_differee_nentre_pas_dans_ma_file(self):
        with frozen(MARDI_23H10):
            services.notify(self.meryem, EventType.CHAT_MENTION,
                            'Vous avez été mentionné', company=self.company)
        self.assertFalse(
            selectors.mentions_non_lues(self.meryem, self.company).exists())


class FenetreNotificationsTests(_Base):
    slug = 'n1-fenetre'

    def test_ouverte_en_journee(self):
        fenetre = selectors.fenetre_notifications(self.company, MARDI_10H)
        self.assertTrue(fenetre.ouverte)
        self.assertEqual(fenetre.prochaine_ouverture, MARDI_10H)

    def test_fermee_la_nuit_avec_la_prochaine_ouverture(self):
        fenetre = selectors.fenetre_notifications(self.company, MARDI_23H10)
        self.assertFalse(fenetre.ouverte)
        self.assertEqual(fenetre.prochaine_ouverture, MERCREDI_08H30)

    def test_repli_08h30_19h_si_les_horaires_sont_illisibles(self):
        with mock.patch('apps.crm.horaires.prochain_creneau_appel',
                        side_effect=RuntimeError('horaires illisibles')):
            nuit = selectors.fenetre_notifications(self.company, MARDI_23H10)
            soir = selectors.fenetre_notifications(
                self.company, _t(2026, 9, 29, 19, 30))
            jour = selectors.fenetre_notifications(self.company, MARDI_10H)
        self.assertEqual(nuit, (False, MERCREDI_08H30))
        self.assertEqual(soir, (False, MERCREDI_08H30))
        self.assertTrue(jour.ouverte)


class BeatTests(SimpleTestCase):
    """Incident du 14/09/2026 : une tâche planifiée mais jamais enregistrée
    ne tourne jamais (garde générale : core/tests/test_celery_task_routes)."""

    def test_livrer_differees_est_planifiee_routee_et_enregistree(self):
        from erp_agentique.celery import app
        entrees = [e for e in app.conf.beat_schedule.values()
                   if e['task'] == 'notifications.livrer_differees']
        self.assertEqual(len(entrees), 1)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES['notifications.livrer_differees'][
                'queue'], 'scheduled')
        app.loader.import_default_modules()
        self.assertIn('notifications.livrer_differees', app.tasks)
