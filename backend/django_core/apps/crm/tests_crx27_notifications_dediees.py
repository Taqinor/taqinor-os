"""CRX27 — la dormance des comptes et l'escalade SLA ont leur PROPRE type de
notification.

CE QUI ÉTAIT FAUX. Les deux commandes ``detecter_comptes_dormants`` et
``recycler_leads_non_travailles`` réutilisaient la clé ``lead_assigned``.
Conséquence invisible pour l'utilisateur : couper « Nouveau lead assigné »
dans ses préférences coupait AUSSI la détection des comptes à réactiver et
l'escalade des leads non contactés — deux alertes d'un tout autre propos, et
aucune surface ne le disait.

LA RÈGLE. Deux ``EventType`` dédiés (``compte_a_reactiver`` et
``lead_non_contacte``), libellés en français, préférences par défaut ACTIVÉES,
migration purement additive. Le test central est celui du bas : muter
``lead_assigned`` ne coupe plus la dormance.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_crx27_notifications_dediees -v 2
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm import stages
from apps.crm.management.commands.detecter_comptes_dormants import (
    detecter_comptes_dormants)
from apps.crm.management.commands.recycler_leads_non_travailles import (
    recycler_leads_non_travailles)
from apps.crm.models import Client, Lead
from apps.notifications.models import (
    EventType, Notification, NotificationPreference)
from apps.notifications.services import default_prefs_for
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


class LesDeuxTypesSontDedies(TestCase):
    """Ils EXISTENT, portent un libellé FR, et leurs préférences sont ON."""

    def test_les_deux_types_existent_avec_un_libelle_francais(self):
        self.assertEqual(EventType.COMPTE_A_REACTIVER, 'compte_a_reactiver')
        self.assertEqual(EventType.LEAD_NON_CONTACTE, 'lead_non_contacte')
        self.assertEqual(
            EventType.COMPTE_A_REACTIVER.label, 'Compte à réactiver')
        self.assertEqual(
            EventType.LEAD_NON_CONTACTE.label, 'Lead non contacté (SLA)')

    def test_ils_ne_sont_plus_la_meme_cle_que_lead_assigned(self):
        self.assertNotEqual(
            EventType.COMPTE_A_REACTIVER, EventType.LEAD_ASSIGNED)
        self.assertNotEqual(
            EventType.LEAD_NON_CONTACTE, EventType.LEAD_ASSIGNED)

    def test_les_preferences_par_defaut_sont_activees(self):
        for event_type in (EventType.COMPTE_A_REACTIVER,
                           EventType.LEAD_NON_CONTACTE):
            with self.subTest(event_type=event_type):
                prefs = default_prefs_for(event_type)
                self.assertTrue(
                    prefs['in_app'],
                    'un type dédié muet par défaut ne servirait à rien.')


class MuterLeadAssignedNeCoupePlusLaDormance(TestCase):
    """LE TEST CENTRAL du `Done =`."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX27', slug='taqinor-crx27')
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'crm_creer'])
        self.owner = User.objects.create_user(
            username='owner_crx27', password='x',
            company=self.company, role=role)
        # L'utilisateur a coupé « Nouveau lead assigné » — et RIEN D'AUTRE.
        NotificationPreference.objects.create(
            company=self.company, user=self.owner,
            event_type=EventType.LEAD_ASSIGNED,
            in_app=False, whatsapp=False, email=False, push=False)

    def _client_dormant(self):
        client = Client.objects.create(
            company=self.company, nom='Dormant', prenom='CRX27')
        devis = Devis.objects.create(
            company=self.company, client=client,
            reference=f'DV-CRX27-{client.pk}', statut=Devis.Statut.ENVOYE)
        Devis.objects.filter(pk=devis.pk).update(
            date_creation=timezone.now() - datetime.timedelta(days=120))
        Lead.objects.create(
            company=self.company, client=client, nom='Lead CRX27',
            owner=self.owner)
        return client

    def test_la_dormance_notifie_malgre_lead_assigned_coupe(self):
        self._client_dormant()
        Notification.objects.all().delete()  # ignore le bruit de fixture

        self.assertEqual(detecter_comptes_dormants(seuil_jours=90), 1)

        notifs = Notification.objects.filter(
            recipient=self.owner,
            event_type=EventType.COMPTE_A_REACTIVER)
        self.assertEqual(
            notifs.count(), 1,
            "couper « Nouveau lead assigné » a coupé la dormance : les deux "
            'alertes partagent encore la même clé.')
        self.assertIn('Compte à réactiver', notifs.first().title)
        self.assertEqual(notifs.first().company_id, self.company.pk)

    def test_la_dormance_n_emet_plus_aucun_lead_assigned(self):
        self._client_dormant()
        Notification.objects.all().delete()
        detecter_comptes_dormants(seuil_jours=90)
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.LEAD_ASSIGNED).count(), 0,
            "la dormance ne doit plus emprunter la clé d'un autre événement.")


class MuterLeadAssignedNeCoupePlusLEscaladeSla(TestCase):
    """Le jumeau — même défaut, même correction."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX27 SLA', slug='taqinor-crx27-sla')
        CompanyProfile.objects.create(
            company=self.company, lead_sla_hours=24)
        role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.owner = User.objects.create_user(
            username='owner_crx27_sla', password='x',
            company=self.company, role=role)
        NotificationPreference.objects.create(
            company=self.company, user=self.owner,
            event_type=EventType.LEAD_ASSIGNED,
            in_app=False, whatsapp=False, email=False, push=False)

    def _lead_hors_sla(self):
        lead = Lead.objects.create(
            company=self.company, nom='Prospect ancien', stage=stages.NEW)
        # owner posé par .update() : passer owner= à create() déclencherait le
        # signal LEAD_ASSIGNED et polluerait les comptages (cf. YLEAD14).
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.now() - datetime.timedelta(hours=48),
            owner=self.owner)
        lead.refresh_from_db()
        return lead

    def test_l_escalade_notifie_malgre_lead_assigned_coupe(self):
        self._lead_hors_sla()
        Notification.objects.all().delete()

        escalades, _ = recycler_leads_non_travailles(now=timezone.now())
        self.assertEqual(escalades, 1)

        notifs = Notification.objects.filter(
            recipient=self.owner, event_type=EventType.LEAD_NON_CONTACTE)
        self.assertEqual(
            notifs.count(), 1,
            "couper « Nouveau lead assigné » a coupé l'escalade SLA.")
        self.assertIn('Lead non contacté', notifs.first().title)

    def test_l_escalade_n_emet_plus_aucun_lead_assigned(self):
        self._lead_hors_sla()
        Notification.objects.all().delete()
        recycler_leads_non_travailles(now=timezone.now())
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.LEAD_ASSIGNED).count(), 0)
