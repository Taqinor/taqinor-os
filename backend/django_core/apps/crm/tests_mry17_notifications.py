"""MRY17 — Le digest du matin et l'escalade du premier contact.

Deux surfaces existaient sans jamais prévenir personne : le panneau
« Relances du jour » (qu'il faut penser à ouvrir) et la promesse « rappelé en
moins de cinq minutes » (que rien ne surveillait). Ce fichier verrouille les
trois propriétés qui séparent une alerte utile du bruit :

  * IDEMPOTENCE — le digest part une fois par jour et par personne, l'escalade
    une fois par lead. Avec `acks_late`, une tâche PEUT être rejouée après un
    crash worker : sans ces gardes, Meryem recevrait la même alerte en boucle.
  * MINUTES OUVRÉES — un lead arrivé à 23 h n'est pas « en retard » à 23 h 05.
  * GATING — module CRM désactivé ⇒ `notify` renvoie None, aucune ligne.
"""
import datetime

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm import horaires
from apps.crm.stages import NEW
from apps.crm.management.commands.escalader_premier_contact import (
    MARQUEUR, escalader_premier_contact)
from apps.crm.management.commands.notifier_relances_dues import (
    notifier_relances_dues)
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.notifications.models import EventType, Notification
from apps.parametres.models import CompanyProfile

User = get_user_model()

CASA = horaires.CASABLANCA


def _company(slug, objectif=5):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    profil, _ = CompanyProfile.objects.get_or_create(company=company)
    profil.premier_contact_objectif_min = objectif
    profil.save(update_fields=['premier_contact_objectif_min'])
    return company


class BeatEtRoutesTests(SimpleTestCase):
    """Une tâche du beat non routée retombe sur `default` et partage la file
    des tâches interactives (garde `core/tests/test_celery_task_routes.py`)."""

    def test_les_deux_taches_sont_planifiees_et_routees(self):
        from erp_agentique.celery import app
        noms = {e['task'] for e in app.conf.beat_schedule.values()}
        for nom in ('crm.notifier_relances_dues',
                    'crm.escalader_premier_contact'):
            with self.subTest(tache=nom):
                self.assertIn(nom, noms)
                self.assertEqual(
                    settings.CELERY_TASK_ROUTES[nom]['queue'], 'scheduled')


class DigestRelancesTests(TestCase):
    def setUp(self):
        self.company = _company('mry17-digest')
        self.meryem = User.objects.create_user(
            username='mry17-meryem', password='x', role_legacy='responsable',
            company=self.company)
        self.sami = User.objects.create_user(
            username='mry17-sami', password='x', role_legacy='responsable',
            company=self.company)
        self.aujourdhui = timezone.localdate()

    def _touche(self, owner, jours=0):
        lead = Lead.objects.create(
            company=self.company, nom=f'Prospect {owner.username}',
            owner=owner)
        RelanceEtape.objects.create(
            company=self.company, lead=lead, ordre=1, canal='appel',
            due_date=self.aujourdhui - datetime.timedelta(days=jours))
        return lead

    def test_un_digest_par_commercial(self):
        self._touche(self.meryem)
        self._touche(self.sami)
        digests, destinataires = notifier_relances_dues(
            today=self.aujourdhui)
        self.assertEqual(digests, 2)
        self.assertEqual(destinataires, 2)
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.RELANCE_DUE).count(), 2)

    def test_idempotent_dans_la_meme_journee(self):
        self._touche(self.meryem)
        notifier_relances_dues(today=self.aujourdhui)
        digests, _ = notifier_relances_dues(today=self.aujourdhui)
        self.assertEqual(digests, 0)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.meryem,
                event_type=EventType.RELANCE_DUE).count(), 1)

    def test_le_retard_compte_dans_le_digest(self):
        """`scope='all'` : le compte inclut les touches EN SOUFFRANCE, pas
        seulement celles du jour — sinon le digest ment par omission."""
        self._touche(self.meryem, jours=4)
        digests, _ = notifier_relances_dues(today=self.aujourdhui)
        self.assertEqual(digests, 1)
        # `_touche` pose `owner` à la création du Lead : le signal PRÉEXISTANT
        # `apps.notifications.signals.lead_post_save` (ERR50) émet DÉJÀ un
        # LEAD_ASSIGNED pour ce même destinataire — filtrer sur l'event_type
        # du digest est donc la seule requête univoque, jamais « la seule
        # notification du destinataire ».
        notif = Notification.objects.get(
            recipient=self.meryem, event_type=EventType.RELANCE_DUE)
        self.assertIn('1 relance', notif.title)

    def test_aucun_digest_sans_touche_due(self):
        Lead.objects.create(
            company=self.company, nom='Sans plan', owner=self.meryem)
        digests, destinataires = notifier_relances_dues(
            today=self.aujourdhui)
        self.assertEqual((digests, destinataires), (0, 0))

    def test_dry_run_ne_notifie_pas(self):
        self._touche(self.meryem)
        digests, _ = notifier_relances_dues(
            dry_run=True, today=self.aujourdhui)
        self.assertEqual(digests, 1)
        # `_touche` pose `owner` à la création : le LEAD_ASSIGNED préexistant
        # (ERR50) part quoi qu'il arrive — seul RELANCE_DUE dépend du dry-run.
        self.assertFalse(
            Notification.objects.filter(
                event_type=EventType.RELANCE_DUE).exists())

    def test_module_crm_desactive_coupe_le_digest(self):
        from core.models import ModuleToggle
        self._touche(self.meryem)
        ModuleToggle.objects.update_or_create(
            company=self.company, module='crm', defaults={'actif': False})
        notifier_relances_dues(today=self.aujourdhui)
        self.assertFalse(
            Notification.objects.filter(
                event_type=EventType.RELANCE_DUE).exists())


class EscaladePremierContactTests(TestCase):
    def setUp(self):
        self.company = _company('mry17-escalade')
        self.meryem = User.objects.create_user(
            username='mry17-esc', password='x', role_legacy='responsable',
            company=self.company)

    def _lead(self, cree_le, **kw):
        champs = {'company': self.company, 'nom': 'Prospect',
                  'owner': self.meryem, 'source': Lead.Source.OS_NATIVE,
                  'stage': NEW}
        champs.update(kw)
        lead = Lead.objects.create(**champs)
        Lead.objects.filter(pk=lead.pk).update(date_creation=cree_le)
        lead.refresh_from_db(fields=['date_creation'])
        return lead

    def test_escalade_apres_lobjectif(self):
        # Mercredi 09:00 → contrôle à 09:30 : 30 minutes OUVRÉES écoulées.
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA))
        nb = escalader_premier_contact(
            now=datetime.datetime(2026, 9, 2, 9, 30, tzinfo=CASA))
        self.assertEqual(nb, 1)
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.PREMIER_CONTACT_DEPASSE).count(), 1)

    def test_pas_descalade_sous_lobjectif(self):
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA))
        nb = escalader_premier_contact(
            now=datetime.datetime(2026, 9, 2, 9, 3, tzinfo=CASA))
        self.assertEqual(nb, 0)

    def test_un_lead_de_nuit_nest_pas_escalade_avant_louverture(self):
        """LE cas qui rendrait l'alerte inutilisable : un lead arrivé à 23 h
        déclencherait une escalade à 23 h 05 en minutes calendaires."""
        self._lead(datetime.datetime(2026, 9, 2, 23, 0, tzinfo=CASA))
        nb = escalader_premier_contact(
            now=datetime.datetime(2026, 9, 3, 6, 0, tzinfo=CASA))
        self.assertEqual(nb, 0)

    def test_escalade_une_seule_fois_par_lead(self):
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA))
        maintenant = datetime.datetime(2026, 9, 2, 11, 0, tzinfo=CASA)
        escalader_premier_contact(now=maintenant)
        nb = escalader_premier_contact(now=maintenant)
        self.assertEqual(nb, 0)
        self.assertEqual(
            LeadActivity.objects.filter(
                body__startswith=MARQUEUR).count(), 1)

    def test_un_lead_deja_contacte_est_ignore(self):
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA),
                   first_contacted_at=datetime.datetime(
                       2026, 9, 2, 9, 2, tzinfo=CASA))
        self.assertEqual(escalader_premier_contact(
            now=datetime.datetime(2026, 9, 2, 11, 0, tzinfo=CASA)), 0)

    def test_un_lead_du_miroir_odoo_nest_jamais_escalade(self):
        """Les 930 leads miroir ne sont pas des demandes à rappeler."""
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA),
                   source=Lead.Source.ODOO_IMPORT_TEST)
        self.assertEqual(escalader_premier_contact(
            now=datetime.datetime(2026, 9, 2, 11, 0, tzinfo=CASA)), 0)

    def test_un_lead_perdu_ou_archive_est_ignore(self):
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA),
                   perdu=True, motif_perte='Prix')
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA),
                   is_archived=True)
        self.assertEqual(escalader_premier_contact(
            now=datetime.datetime(2026, 9, 2, 11, 0, tzinfo=CASA)), 0)

    def test_objectif_a_zero_desactive_la_surveillance(self):
        profil = CompanyProfile.objects.get(company=self.company)
        profil.premier_contact_objectif_min = 0
        profil.save(update_fields=['premier_contact_objectif_min'])
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA))
        self.assertEqual(escalader_premier_contact(
            now=datetime.datetime(2026, 9, 2, 11, 0, tzinfo=CASA)), 0)

    def test_dry_run_necrit_rien(self):
        self._lead(datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA))
        nb = escalader_premier_contact(
            dry_run=True,
            now=datetime.datetime(2026, 9, 2, 11, 0, tzinfo=CASA))
        self.assertEqual(nb, 1)
        self.assertFalse(
            LeadActivity.objects.filter(body__startswith=MARQUEUR).exists())
        # `_lead` pose `owner` à la création : le LEAD_ASSIGNED préexistant
        # (ERR50) part quoi qu'il arrive — seul PREMIER_CONTACT_DEPASSE
        # dépend du dry-run de CETTE commande.
        self.assertFalse(
            Notification.objects.filter(
                event_type=EventType.PREMIER_CONTACT_DEPASSE).exists())


class SeveriteEtPreferencesTests(TestCase):
    def test_premier_contact_depasse_est_critique(self):
        """Critique = passe les heures calmes : un lead qui refroidit ne peut
        pas attendre 08:00."""
        from apps.notifications.severity import CRITIQUE, EVENT_SEVERITY
        self.assertEqual(
            EVENT_SEVERITY.get(EventType.PREMIER_CONTACT_DEPASSE), CRITIQUE)

    def test_relance_due_reste_normale(self):
        from apps.notifications.severity import EVENT_SEVERITY
        self.assertNotIn(EventType.RELANCE_DUE, EVENT_SEVERITY)

    def test_les_deux_evenements_sont_gates_sur_le_crm(self):
        from apps.notifications.module_gating import EVENT_MODULE
        self.assertEqual(EVENT_MODULE[EventType.RELANCE_DUE], 'crm')
        self.assertEqual(
            EVENT_MODULE[EventType.PREMIER_CONTACT_DEPASSE], 'crm')

    def test_email_actif_par_defaut_sur_les_deux(self):
        from apps.notifications.services import default_prefs_for
        for cle in ('relance_due', 'premier_contact_depasse'):
            with self.subTest(evenement=cle):
                self.assertTrue(default_prefs_for(cle)['email'])
