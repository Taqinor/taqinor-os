"""APAR20 — les destinataires « toute la société / par rôle / managers » des
notifications sont les seuls comptes INTERNES (C-APAR-027) : un compte de
portail client n'est ni ciblé par une annonce, ni compté manquant au rapport
de conformité, ni visé par une règle de routage par rôle, ni relancé.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from . import digests, sweeps
from .models import Annonce, Notification, NotificationRoutingRule
from .selectors import utilisateurs_internes_actifs
from .services import (
    acknowledge_annonce, annonce_compliance_report, annonce_recipients,
    publish_annonce, resolve_recipients, sweep_annonce_reminders,
)
from .types_evenements import EventType

User = get_user_model()


class DestinatairesInternesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR20')
        self.admin = User.objects.create_user(
            username='apar20_admin', password='pw', company=self.company,
            role_legacy='admin')
        self.resp = User.objects.create_user(
            username='apar20_resp', password='pw', company=self.company,
            role_legacy='responsable')
        self.portail = User.objects.create_user(
            username='apar20_client40', password='pw', company=self.company,
            role_legacy='normal', portee=User.PORTEE_PORTAIL_CLIENT,
            portail_client_id=40)

    def test_selecteur_unique(self):
        self.assertEqual(
            set(utilisateurs_internes_actifs(self.company)),
            {self.admin, self.resp})

    def test_annonce_toute_la_societe_rapport_100(self):
        annonce = Annonce.objects.create(
            company=self.company, titre='Note', corps='Lire',
            cible_type=Annonce.Cible.TOUS, lecture_obligatoire=True)
        self.assertEqual(set(annonce_recipients(annonce)),
                         {self.admin, self.resp})
        with self.captureOnCommitCallbacks(execute=True):
            publish_annonce(annonce)
        annonce.refresh_from_db()
        acknowledge_annonce(annonce, self.admin)
        acknowledge_annonce(annonce, self.resp)
        rapport = annonce_compliance_report(annonce)
        self.assertEqual(rapport['manquants'], [])
        self.assertEqual(rapport['total_cibles'], 2)
        self.assertFalse(Notification.objects.filter(
            recipient=self.portail).exists())

    def test_relance_jamais_au_portail(self):
        annonce = Annonce.objects.create(
            company=self.company, titre='Note', corps='Lire',
            cible_type=Annonce.Cible.TOUS, lecture_obligatoire=True)
        with self.captureOnCommitCallbacks(execute=True):
            publish_annonce(annonce)
        Annonce.objects.filter(pk=annonce.pk).update(
            date_publication_effective=timezone.now()
            - timezone.timedelta(days=30))
        with self.captureOnCommitCallbacks(execute=True):
            sweep_annonce_reminders(self.company, delay_days=1)
        self.assertFalse(Notification.objects.filter(
            recipient=self.portail).exists())

    def test_routage_par_role_exclut_le_portail(self):
        NotificationRoutingRule.objects.create(
            company=self.company, event_type=EventType.LEAD_ASSIGNED,
            target_role='normal', enabled=True)
        self.assertNotIn(
            self.portail,
            list(resolve_recipients(self.company, EventType.LEAD_ASSIGNED)))

    def test_managers_et_digest_internes(self):
        self.admin.is_active = False
        self.admin.save()
        self.resp.role_legacy = 'normal'
        self.resp.save()
        # Aucun manager actif : le repli « toute la société » reste interne.
        self.assertNotIn(self.portail, sweeps._managers(self.company))
        self.assertNotIn(self.portail, digests._recipients(self.company))
