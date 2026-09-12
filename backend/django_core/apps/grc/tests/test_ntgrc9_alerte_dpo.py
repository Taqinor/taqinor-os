"""NTGRC9 — alerte DPO sur traitement d'une personne au consentement retiré.

Garanties : créer un lead pour un email au consentement retiré notifie le DPO
SANS bloquer la création ; un consentement re-accordé ne rouvre pas d'alerte ;
tout reste scopé société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead
from apps.grc.receivers import retraits_de_consentement
from apps.notifications.models import EventType, Notification
from authentication.models import Company
from core.models import ConsentRecord

User = get_user_model()
EMAIL = 'retire@exemple.ma'


class AlerteDpoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC9 SA', slug='ntgrc9')
        cls.autre = Company.objects.create(nom='NTGRC9 B', slug='ntgrc9-b')
        cls.dpo = User.objects.create_user(
            username='ntgrc9_dpo', password='x', role_legacy='admin',
            company=cls.company)

    def _retrait(self, company=None, purpose='marketing'):
        return ConsentRecord.objects.create(
            company=company or self.company, subject_identifier=EMAIL,
            purpose=purpose, granted=False)

    def _notifs(self):
        return Notification.objects.filter(
            event_type=EventType.CONSENTEMENT_RETIRE_TRAITE)

    def test_creer_un_lead_au_consentement_retire_alerte_le_dpo(self):
        self._retrait()
        lead = Lead.objects.create(
            company=self.company, nom='X', email=EMAIL)
        self.assertIsNotNone(lead.pk)  # la création n'est JAMAIS bloquée
        notifs = self._notifs()
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().user, self.dpo)
        self.assertIn('marketing', notifs.first().body)

    def test_sans_retrait_aucune_alerte(self):
        ConsentRecord.objects.create(
            company=self.company, subject_identifier=EMAIL,
            purpose='marketing', granted=True)
        Lead.objects.create(company=self.company, nom='X', email=EMAIL)
        self.assertEqual(self._notifs().count(), 0)

    def test_un_consentement_re_accorde_ne_rouvre_pas_dalerte(self):
        """Le registre est append-only : seule la ligne la PLUS RÉCENTE fait foi."""
        self._retrait()
        ConsentRecord.objects.create(
            company=self.company, subject_identifier=EMAIL,
            purpose='marketing', granted=True)
        Lead.objects.create(company=self.company, nom='X', email=EMAIL)
        self.assertEqual(self._notifs().count(), 0)

    def test_le_retrait_dune_autre_societe_nalerte_pas(self):
        self._retrait(company=self.autre)
        Lead.objects.create(company=self.company, nom='X', email=EMAIL)
        self.assertEqual(self._notifs().count(), 0)

    def test_modifier_un_lead_existant_ne_realerte_pas(self):
        self._retrait()
        lead = Lead.objects.create(
            company=self.company, nom='X', email=EMAIL)
        self.assertEqual(self._notifs().count(), 1)
        lead.nom = 'Y'
        lead.save()
        self.assertEqual(self._notifs().count(), 1)


class SelectionDesFinalitesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC9 F', slug='ntgrc9-f')

    def test_seule_la_ligne_la_plus_recente_par_finalite_fait_foi(self):
        for purpose, granted in (('marketing', True), ('marketing', False),
                                 ('whatsapp', False), ('whatsapp', True)):
            ConsentRecord.objects.create(
                company=self.company, subject_identifier=EMAIL,
                purpose=purpose, granted=granted)
        self.assertEqual(
            retraits_de_consentement(self.company, [EMAIL]), ['marketing'])

    def test_sans_identifiant_aucune_lecture(self):
        self.assertEqual(retraits_de_consentement(self.company, []), [])
        self.assertEqual(retraits_de_consentement(None, [EMAIL]), [])
