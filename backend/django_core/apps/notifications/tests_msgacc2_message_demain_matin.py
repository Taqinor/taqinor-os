"""MSGACC2 — la data migration « LE MESSAGE DE DEMAIN MATIN » (0059).

Le harnais maison n'a pas d'équivalent `MigratorTestCase` (aucune migration de
CE dépôt n'est testée via un exécuteur de migrations dédié — vérifié). Suivant
le patron déjà utilisé par `apps/frais/tests/test_odx15_frais_split.py`, le
MODULE de migration est importé par son chemin pointé (``importlib``) et ses
fonctions sont appelées directement contre le registre RÉEL des modèles
(``django.apps.apps`` — les modèles réels portent, à ce jour, exactement les
mêmes champs que l'état historique visé par cette migration, donc l'appel est
fidèle). Résolution des modèles PAR CHAÎNE (jamais un import direct de
`apps.crm.models`) — même patron que `core/tests/test_rls_cross_tenant_denial.py`
documenté dans `.importlinter` (AUD422) : invisible à `lint-imports`, aucun
couplage introduit.

Couverture :
  - audience : admins ET owners de leads non archivés inclus, un compte
    inactif ou d'une autre société exclu, un owner d'un lead ARCHIVÉ SEUL
    exclu ;
  - société démo jamais semée ;
  - idempotence (deux passages ne dupliquent rien) ;
  - corps exact + `visible_a_partir_de` = demain 07:00 Africa/Casablanca ;
  - retour arrière : supprime exactement les lignes semées, jamais un
    message d'accueil créé par ailleurs (auteur posé, ou corps différent).
"""
from datetime import datetime
from importlib import import_module
from zoneinfo import ZoneInfo

from django.apps import apps as real_apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from .models import MessageAccueil

MIGRATION = import_module(
    'apps.notifications.migrations.0059_message_accueil_demain_matin')
User = get_user_model()
Lead = real_apps.get_model('crm', 'Lead')


def _company(nom='MsgAcc2Co', est_demo=False):
    return Company.objects.create(nom=nom, est_demo=est_demo)


def _user(company, username, role_legacy='normal', is_active=True):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy, is_active=is_active)


def _lead(company, owner, is_archived=False, nom='Lead'):
    return Lead.objects.create(
        company=company, nom=nom, owner=owner, is_archived=is_archived)


class DemainSeptHeuresCasablancaTests(TestCase):
    def test_calcule_demain_7h_heure_marocaine(self):
        # 20:00 UTC = 21:00 à Casablanca (UTC+1) — on est encore le 15 LOCAL.
        reference = datetime(2026, 9, 15, 20, 0, tzinfo=ZoneInfo('UTC'))
        resultat = MIGRATION._demain_7h_casablanca(reference)
        local = resultat.astimezone(ZoneInfo('Africa/Casablanca'))
        self.assertEqual(local.date().isoformat(), '2026-09-16')
        self.assertEqual(local.hour, 7)
        self.assertEqual(local.minute, 0)

    def test_apres_minuit_local_demain_est_bien_le_jour_local_suivant(self):
        # 23:00 UTC le 15 = 00:00 à Casablanca le 16 : « demain » vaut le 17.
        # C'est le calendrier LOCAL qui décide, jamais le jour UTC.
        reference = datetime(2026, 9, 15, 23, 0, tzinfo=ZoneInfo('UTC'))
        resultat = MIGRATION._demain_7h_casablanca(reference)
        local = resultat.astimezone(ZoneInfo('Africa/Casablanca'))
        self.assertEqual(local.date().isoformat(), '2026-09-17')
        self.assertEqual(local.hour, 7)


class AudienceRelanceCrmTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, 'a2_admin', role_legacy='admin')
        self.owner = _user(self.company, 'a2_owner')
        self.terrain = _user(self.company, 'a2_terrain')  # ni admin, ni owner
        _lead(self.company, owner=self.owner)

    def _pks(self):
        return set(
            MIGRATION._audience_relance_crm(real_apps, self.company)
            .values_list('pk', flat=True))

    def test_admin_inclus(self):
        self.assertIn(self.admin.pk, self._pks())

    def test_owner_de_lead_non_archive_inclus(self):
        self.assertIn(self.owner.pk, self._pks())

    def test_ni_admin_ni_owner_exclu(self):
        """C'est exactement le profil « Commercial terrain » (VTA4) : aucun
        droit CRM, jamais owner d'un lead."""
        self.assertNotIn(self.terrain.pk, self._pks())

    def test_owner_de_lead_archive_seul_exclu(self):
        archive_owner = _user(self.company, 'a2_archive_owner')
        _lead(self.company, owner=archive_owner, is_archived=True)
        self.assertNotIn(archive_owner.pk, self._pks())

    def test_compte_inactif_exclu_meme_admin(self):
        inactif = _user(
            self.company, 'a2_inactif', role_legacy='admin', is_active=False)
        self.assertNotIn(inactif.pk, self._pks())

    def test_owner_d_une_autre_societe_exclu(self):
        autre = _company('AutreSociete2')
        owner_autre = _user(autre, 'a2_owner_autre')
        _lead(autre, owner=owner_autre)
        self.assertNotIn(owner_autre.pk, self._pks())

    def test_pas_de_doublon_si_admin_et_owner(self):
        _lead(self.company, owner=self.admin)
        pks = list(
            MIGRATION._audience_relance_crm(real_apps, self.company)
            .values_list('pk', flat=True))
        self.assertEqual(pks.count(self.admin.pk), 1)


class SemerMessageDemainMatinTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, 'a2s_admin', role_legacy='admin')
        self.demo = _company('DemoCo2', est_demo=True)
        self.demo_admin = _user(self.demo, 'a2s_demo_admin', role_legacy='admin')

    def test_seme_pour_societe_non_demo(self):
        MIGRATION.semer_message_demain_matin(real_apps, None)
        msg = MessageAccueil.objects.get(
            company=self.company, destinataire=self.admin)
        self.assertIsNone(msg.auteur)
        self.assertEqual(msg.corps, MIGRATION.CORPS)
        local = msg.visible_a_partir_de.astimezone(
            ZoneInfo('Africa/Casablanca'))
        self.assertEqual(local.hour, 7)

    def test_jamais_pour_societe_demo(self):
        MIGRATION.semer_message_demain_matin(real_apps, None)
        self.assertFalse(
            MessageAccueil.objects.filter(
                company=self.demo, destinataire=self.demo_admin).exists())

    def test_idempotent_deux_passages(self):
        MIGRATION.semer_message_demain_matin(real_apps, None)
        MIGRATION.semer_message_demain_matin(real_apps, None)
        self.assertEqual(
            MessageAccueil.objects.filter(
                company=self.company, destinataire=self.admin).count(), 1)

    def test_ce_n_est_pas_une_notification(self):
        from .models import Notification
        MIGRATION.semer_message_demain_matin(real_apps, None)
        self.assertEqual(Notification.objects.count(), 0)


class RetirerMessageDemainMatinTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, 'a2r_admin', role_legacy='admin')

    def test_retrait_supprime_les_lignes_semees(self):
        MIGRATION.semer_message_demain_matin(real_apps, None)
        self.assertTrue(
            MessageAccueil.objects.filter(
                company=self.company, destinataire=self.admin).exists())
        MIGRATION.retirer_message_demain_matin(real_apps, None)
        self.assertFalse(
            MessageAccueil.objects.filter(
                company=self.company, destinataire=self.admin).exists())

    def test_retrait_epargne_un_message_a_auteur_pose(self):
        """Marqueur `auteur IS NULL` : un message d'accueil ENVOYÉ à la main
        (auteur posé) n'est jamais touché par le retour arrière, même avec un
        corps identique par accident."""
        manuel = MessageAccueil.objects.create(
            company=self.company, destinataire=self.admin, auteur=self.admin,
            visible_a_partir_de=MIGRATION._demain_7h_casablanca(),
            corps=MIGRATION.CORPS)
        MIGRATION.semer_message_demain_matin(real_apps, None)
        MIGRATION.retirer_message_demain_matin(real_apps, None)
        self.assertTrue(MessageAccueil.objects.filter(id=manuel.id).exists())

    def test_retrait_epargne_un_corps_different(self):
        autre = MessageAccueil.objects.create(
            company=self.company, destinataire=self.admin, auteur=None,
            visible_a_partir_de=MIGRATION._demain_7h_casablanca(),
            corps='Un tout autre message, rien à voir.')
        MIGRATION.semer_message_demain_matin(real_apps, None)
        MIGRATION.retirer_message_demain_matin(real_apps, None)
        self.assertTrue(MessageAccueil.objects.filter(id=autre.id).exists())
