"""VTA5 — le feu vert redescend sur le lead par ÉVÉNEMENT, plus par un appel.

Ce que le test prouve :

* ``visite_validee`` est DÉCLARÉ au bus et CATALOGUÉ, avec une parité EXACTE
  entre les clés du catalogue et les kwargs réellement envoyés (WIR139) ;
* valider une visite émet l'événement une fois, avec l'utilisateur AGISSANT,
  un ``lead_id`` ENTIER et un récap pré-calculé ;
* le CRM, abonné dans son propre ``receivers.py``, pose bien
  ``Lead.visite_effectuee`` + le récap dans ``visite_notes`` et UNE note de
  chatter — et une RE-validation ne duplique pas le récap (idempotence
  « recap not in existantes » reconduite) ;
* ``apps/visites/services.py`` ne contient plus AUCUN écrit vers ``crm.Lead``
  (lu sur le fichier, pas sur une intention) ;
* les notifications de validation et de renvoi pointent ``/visites/<id>`` ;
* la data migration des liens déjà persistés est ciblée, idempotente et
  réversible.
"""
from importlib import import_module

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead, LeadActivity
from apps.roles.models import Role
from apps.visites.models import VisiteTerrain
from authentication.models import Company
from core import event_catalog, event_coverage
from core.events import visite_validee

User = get_user_model()

PERMS_BUREAU = ['visites_voir', 'visites_creer', 'visites_modifier',
                'visites_valider']


class ContratDEvenementTests(TestCase):
    """Le bus et le catalogue ne peuvent pas diverger."""

    def test_signal_declare_et_catalogue(self):
        self.assertIn('visite_validee', event_coverage.declared_signals())
        self.assertIn('visite_validee', event_catalog.catalog_names())

    def test_parite_exacte_des_cles_de_payload(self):
        """WIR139 — clés du catalogue == kwargs réellement envoyés."""
        self.assertEqual(
            set(event_catalog.entry('visite_validee')['payload']),
            {'visite', 'lead_id', 'user', 'recap'})
        self.assertNotIn(
            'visite_validee', event_coverage.catalog_payload_mismatches())

    def test_le_signal_a_un_abonne(self):
        """Un signal sans abonné est un orphelin (garde YEVNT7)."""
        self.assertNotIn('visite_validee', event_coverage.orphan_signals())


class EmissionEtRetourLeadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='VTA5 Solaire',
                                             slug='vta5-a')
        # Tenant-distinctness : une SECONDE société RÉELLE, avec ses données.
        cls.autre = Company.objects.create(nom='VTA5 Concurrent',
                                           slug='vta5-b')
        cls.bureau = cls._user(cls.company, 'vta5-bureau')
        cls.bureau_autre = cls._user(cls.autre, 'vta5-bureau-autre')
        cls.lead = Lead.objects.create(
            company=cls.company, nom='Bennani', ville='Bouskoura')
        cls.lead_autre = Lead.objects.create(
            company=cls.autre, nom='Client concurrent', ville='Rabat')

    @staticmethod
    def _user(company, username):
        role = Role.objects.create(company=company, nom=f'role-{username}',
                                   permissions=list(PERMS_BUREAU))
        return User.objects.create_user(
            username=username, password='x', company=company,
            role_legacy='normal', role=role)

    def _visite(self, company=None, lead=None):
        return VisiteTerrain.objects.create(
            company=company or self.company, lead=lead or self.lead,
            mesures={'toiture': {'longueur_m': 12, 'largeur_m': 8}})

    def test_valider_emet_l_evenement_une_fois(self):
        from apps.visites import services

        recu = []

        def _espion(sender, **kwargs):
            recu.append(kwargs)

        visite_validee.connect(_espion, dispatch_uid='vta5-espion')
        try:
            visite = self._visite()
            services.valider_visite(visite, self.bureau)
        finally:
            visite_validee.disconnect(dispatch_uid='vta5-espion')

        self.assertEqual(len(recu), 1)
        charge = recu[0]
        self.assertEqual(charge['visite'], visite)
        self.assertEqual(charge['lead_id'], self.lead.id)
        self.assertIsInstance(charge['lead_id'], int)
        self.assertEqual(charge['user'], self.bureau)
        self.assertIn('Visite technique validée', charge['recap'])

    def test_le_crm_pose_visite_effectuee_et_le_recap(self):
        from apps.visites import services

        services.valider_visite(self._visite(), self.bureau)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.visite_effectuee)
        self.assertIn('zone utile 12 × 8 m', self.lead.visite_notes)

    def test_le_crm_pose_une_note_de_chatter_avec_l_utilisateur_agissant(self):
        from apps.visites import services

        services.valider_visite(self._visite(), self.bureau)
        notes = LeadActivity.objects.filter(lead=self.lead)
        self.assertEqual(notes.count(), 1)
        note = notes.first()
        self.assertIn('feu vert', note.body)
        self.assertEqual(note.user_id, self.bureau.id)

    def test_une_re_validation_ne_duplique_pas_le_recap(self):
        from apps.visites import services

        visite = self._visite()
        services.valider_visite(visite, self.bureau)
        self.lead.refresh_from_db()
        premier = self.lead.visite_notes
        services.valider_visite(visite, self.bureau)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.visite_notes, premier)

    def test_une_note_ecrite_a_la_main_n_est_jamais_ecrasee(self):
        from apps.visites import services

        self.lead.visite_notes = 'Le client a un chien méchant.'
        self.lead.save(update_fields=['visite_notes'])
        services.valider_visite(self._visite(), self.bureau)
        self.lead.refresh_from_db()
        self.assertIn('chien méchant', self.lead.visite_notes)
        self.assertIn('Visite technique validée', self.lead.visite_notes)

    def test_le_lead_d_une_autre_societe_n_est_pas_touche(self):
        from apps.visites import services

        services.valider_visite(
            self._visite(company=self.autre, lead=self.lead_autre),
            self.bureau_autre)
        self.lead.refresh_from_db()
        self.lead_autre.refresh_from_db()
        self.assertFalse(self.lead.visite_effectuee)
        self.assertTrue(self.lead_autre.visite_effectuee)


class PlusAucunEcritDirectTests(TestCase):
    """Lu sur le FICHIER, jamais sur un commentaire d'intention."""

    def test_services_visites_n_ecrit_plus_sur_le_lead(self):
        import inspect

        from apps.visites import services

        source = inspect.getsource(services)
        self.assertNotIn('ecrire_retour_lead_visite', source)
        self.assertNotIn('lead.save(', source)
        self.assertIn('visite_validee.send(', source)

    def test_les_deux_notifications_pointent_la_nouvelle_route(self):
        import inspect

        from apps.visites import services

        source = inspect.getsource(services)
        self.assertIn("link=f'/visites/{visite.pk}'", source)
        self.assertNotIn('/crm/visites/', source)


class MigrationDesLiensTests(TestCase):
    """La data migration des notifications déjà persistées."""

    def test_ciblee_idempotente_et_reversible(self):
        module = import_module(
            'apps.notifications.migrations.0053_vta5_liens_visites')
        operation = module.Migration.operations[0]
        self.assertIsNotNone(operation.reverse_code)
        self.assertEqual(module.ANCIEN, '/crm/visites/')
        self.assertEqual(module.NOUVEAU, '/visites/')

    def test_reecriture_du_prefixe_sur_une_notification_reelle(self):
        """Le lien d'un feu vert déjà notifié mène au NOUVEL écran."""
        from django.apps import apps as registre

        from apps.notifications.models import Notification

        module = import_module(
            'apps.notifications.migrations.0053_vta5_liens_visites')
        company = Company.objects.create(nom='VTA5 Liens', slug='vta5-liens')
        user = User.objects.create_user(
            username='vta5-liens', password='x', company=company,
            role_legacy='normal')
        ancienne = Notification.objects.create(
            company=company, recipient=user,
            event_type='visite_terrain_validee', title='Visite validée',
            link='/crm/visites/7')
        intacte = Notification.objects.create(
            company=company, recipient=user,
            event_type='visite_terrain_validee', title='Autre écran',
            link='/crm/leads/42')

        module.vers_app_visites(registre, None)
        ancienne.refresh_from_db()
        intacte.refresh_from_db()
        self.assertEqual(ancienne.link, '/visites/7')
        self.assertEqual(intacte.link, '/crm/leads/42')

        # Idempotente : un second passage ne change plus rien.
        module.vers_app_visites(registre, None)
        ancienne.refresh_from_db()
        self.assertEqual(ancienne.link, '/visites/7')

        # Réversible.
        module.retour_vers_crm(registre, None)
        ancienne.refresh_from_db()
        self.assertEqual(ancienne.link, '/crm/visites/7')
