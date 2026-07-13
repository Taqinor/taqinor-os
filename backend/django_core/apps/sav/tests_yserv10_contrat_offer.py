"""YSERV10 — réception d'un chantier sans contrat de maintenance actif ->
offre automatique (activité + notification), idempotente ; client déjà sous
contrat -> aucun effet ; KPI taux d'attache exact sur fixtures.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.notifications.models import EventType, Notification
from apps.records.models import Activity
from apps.sav.models import ContratMaintenance
from apps.sav.selectors import client_a_contrat_actif, taux_attache
from apps.ventes.models import Devis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class Yserv10ContratOfferTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='YSERV10 Co', slug='yserv10-co')
        self.commercial = User.objects.create_user(
            username='yserv10_commercial', password='x',
            role_legacy='commercial', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YSERV10',
            telephone='+212600000077')

    def _devis(self):
        return Devis.objects.create(
            company=self.company,
            reference=f'DEV-{MONTH}-{Devis.objects.count():04d}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), created_by=self.commercial)

    def _installation(self, **extra):
        defaults = dict(
            company=self.company, reference=f'CHT-{Installation.objects.count()}',
            client=self.client_obj,
            statut=Installation.Statut.RECEPTIONNE,
            date_reception=timezone.localdate(),
        )
        defaults.update(extra)
        return Installation.objects.create(**defaults)

    def _fire_reception(self, installation):
        from core.events import chantier_receptionne
        chantier_receptionne.send(
            sender=Installation, installation=installation,
            user=self.commercial,
            ancien_statut=Installation.Statut.INSTALLE)

    def test_client_sans_contrat_recoit_une_activite_et_une_notification(self):
        devis = self._devis()
        inst = self._installation(devis=devis)
        self._fire_reception(inst)

        activities = Activity.objects.filter(
            company=self.company, note__contains=f'[yserv10:{inst.id}]')
        self.assertEqual(activities.count(), 1)
        activity = activities.get()
        self.assertEqual(activity.assigned_to_id, self.commercial.id)
        self.assertEqual(
            activity.due_date, timezone.localdate() + timezone.timedelta(days=14))

        # YSERV10 promet UNE notification d'offre (SAV_ACTIVITE_DUE) au
        # commercial — sans y coupler la notification distincte que reçoit
        # aussi le créateur d'un devis passé à ACCEPTE (devis_accepted).
        self.assertEqual(
            Notification.objects.filter(
                company=self.company, recipient=self.commercial,
                event_type=EventType.SAV_ACTIVITE_DUE).count(), 1)

    def test_without_resolvable_assignee_creates_no_orphan_activity(self):
        """Sans devis/lead lié, aucun destinataire n'est résolvable — le
        récepteur ne doit RIEN créer plutôt qu'une activité orpheline."""
        inst = self._installation()
        self._fire_reception(inst)

        activities = Activity.objects.filter(
            company=self.company, note__contains=f'[yserv10:{inst.id}]')
        self.assertEqual(activities.count(), 0)

    def test_client_deja_sous_contrat_ne_declenche_rien(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            date_debut=date(2026, 1, 1), actif=True)
        self.assertTrue(client_a_contrat_actif(self.client_obj, self.company))

        inst = self._installation()
        self._fire_reception(inst)

        self.assertEqual(
            Activity.objects.filter(
                company=self.company,
                note__contains=f'[yserv10:{inst.id}]').count(), 0)
        self.assertEqual(
            Notification.objects.filter(company=self.company).count(), 0)

    def test_reemission_du_signal_ne_duplique_jamais_lactivite(self):
        """Ré-émettre le signal (double sauvegarde, retry) ne doit jamais
        produire une 2e activité pour le même chantier (marqueur
        `[yserv10:<id>]` dans `note`)."""
        devis = self._devis()
        inst = self._installation(devis=devis)
        self._fire_reception(inst)
        self._fire_reception(inst)
        self.assertEqual(
            Activity.objects.filter(
                company=self.company,
                note__contains=f'[yserv10:{inst.id}]').count(), 1)

    def test_taux_attache_kpi_exact_sur_fixtures(self):
        # 2 chantiers réceptionnés : 1 avec contrat actif dans les 90j, 1 sans.
        inst_avec = self._installation()
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            date_debut=inst_avec.date_reception, actif=True)

        client2 = Client.objects.create(
            company=self.company, nom='Client2', prenom='YSERV10',
            telephone='+212600000078')
        self._installation(client=client2, reference='CHT-sans-contrat')

        result = taux_attache(self.company)
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['avec_contrat'], 1)
        self.assertEqual(result['taux_pct'], 50.0)

    def test_taux_attache_zero_division_safe(self):
        result = taux_attache(self.company)
        self.assertEqual(result, {'total': 0, 'avec_contrat': 0, 'taux_pct': 0.0})
