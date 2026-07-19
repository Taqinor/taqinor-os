"""YSERV13 — contrôles d'intégrité inter-documents (états orphelins entre apps).

Chaque famille : un cas CONSTRUIT en fixture (détecté) + un cas SAIN (ignoré).
Multi-tenant : aucune fuite d'une société à l'autre."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention, StockReservation
from apps.reporting.integrity import controle_integrite, total_anomalies
from apps.sav.models import ContratMaintenance, Ticket
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture
from authentication.models import Company

User = get_user_model()


class IntegrityBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='yserv13-co', defaults={'nom': 'YSERV13 Co'})[0]
        self.other_company = Company.objects.get_or_create(
            slug='yserv13-other', defaults={'nom': 'YSERV13 Other'})[0]
        self.user = User.objects.create_user(
            username='yserv13_u', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ClientInt')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _installation(self, **kwargs):
        defaults = dict(
            company=self.company, reference=f'INST-{Installation.objects.count()+1}',
            client=self.client_obj, statut=Installation.Statut.CLOTURE)
        defaults.update(kwargs)
        return Installation.objects.create(**defaults)


class TestDevisAcceptesSansChantier(IntegrityBase):
    def test_detects_constructed_case(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-1', client=self.client_obj,
            statut=Devis.Statut.ACCEPTE)
        result = controle_integrite(self.company)
        self.assertIn(devis.id, result['devis_acceptes_sans_chantier']['ids'])

    def test_healthy_case_ignored(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-2', client=self.client_obj,
            statut=Devis.Statut.ACCEPTE)
        self._installation(devis=devis)
        result = controle_integrite(self.company)
        self.assertEqual(result['devis_acceptes_sans_chantier']['ids'], [])

    def test_non_accepted_devis_ignored(self):
        Devis.objects.create(
            company=self.company, reference='DEV-3', client=self.client_obj,
            statut=Devis.Statut.BROUILLON)
        result = controle_integrite(self.company)
        self.assertEqual(result['devis_acceptes_sans_chantier']['ids'], [])


class TestChantiersSansParc(IntegrityBase):
    def test_detects_constructed_case(self):
        inst = self._installation(statut=Installation.Statut.RECEPTIONNE)
        result = controle_integrite(self.company)
        self.assertIn(inst.id, result['chantiers_receptionnes_sans_parc']['ids'])

    def test_healthy_case_ignored(self):
        from apps.sav.models import Equipement
        inst = self._installation(statut=Installation.Statut.CLOTURE)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='YSERV13-1',
            prix_vente=Decimal('100'))
        Equipement.objects.create(
            company=self.company, produit=produit, installation=inst)
        result = controle_integrite(self.company)
        self.assertNotIn(
            inst.id, result['chantiers_receptionnes_sans_parc']['ids'])

    def test_early_stage_chantier_ignored(self):
        inst = self._installation(statut=Installation.Statut.EN_COURS)
        result = controle_integrite(self.company)
        self.assertNotIn(
            inst.id, result['chantiers_receptionnes_sans_parc']['ids'])


class TestReservationsNonLiberees(IntegrityBase):
    def test_detects_constructed_case(self):
        inst = self._installation(statut=Installation.Statut.CLOTURE)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='YSERV13-2',
            prix_vente=Decimal('500'))
        resa = StockReservation.objects.create(
            company=self.company, installation=inst, produit=produit,
            quantite=2, active=True, consomme=False)
        result = controle_integrite(self.company)
        self.assertIn(resa.id, result['reservations_non_liberees']['ids'])

    def test_healthy_case_ignored_when_released(self):
        inst = self._installation(statut=Installation.Statut.CLOTURE)
        produit = Produit.objects.create(
            company=self.company, nom='Batterie', sku='YSERV13-3',
            prix_vente=Decimal('700'))
        resa = StockReservation.objects.create(
            company=self.company, installation=inst, produit=produit,
            quantite=1, active=False, consomme=False)
        result = controle_integrite(self.company)
        self.assertNotIn(resa.id, result['reservations_non_liberees']['ids'])

    def test_ignored_for_open_chantier(self):
        inst = self._installation(statut=Installation.Statut.EN_COURS)
        produit = Produit.objects.create(
            company=self.company, nom='Cable', sku='YSERV13-4',
            prix_vente=Decimal('50'))
        resa = StockReservation.objects.create(
            company=self.company, installation=inst, produit=produit,
            quantite=1, active=True, consomme=False)
        result = controle_integrite(self.company)
        self.assertNotIn(resa.id, result['reservations_non_liberees']['ids'])


class TestInterventionsNonTermineesChantierClos(IntegrityBase):
    def test_detects_constructed_case(self):
        inst = self._installation(statut=Installation.Statut.CLOTURE)
        interv = Intervention.objects.create(
            company=self.company, installation=inst,
            statut=Intervention.Statut.A_PREPARER)
        result = controle_integrite(self.company)
        self.assertIn(
            interv.id,
            result['interventions_non_terminees_chantier_clos']['ids'])

    def test_healthy_case_terminee_ignored(self):
        inst = self._installation(statut=Installation.Statut.CLOTURE)
        interv = Intervention.objects.create(
            company=self.company, installation=inst,
            statut=Intervention.Statut.TERMINEE)
        result = controle_integrite(self.company)
        self.assertNotIn(
            interv.id,
            result['interventions_non_terminees_chantier_clos']['ids'])


class TestTicketsClosAvecInterventionOuverte(IntegrityBase):
    def test_detects_constructed_case(self):
        inst = self._installation(statut=Installation.Statut.EN_COURS)
        ticket = Ticket.objects.create(
            company=self.company, reference='TCK-1', client=self.client_obj,
            statut=Ticket.Statut.CLOTURE)
        Intervention.objects.create(
            company=self.company, installation=inst, ticket=ticket,
            statut=Intervention.Statut.A_PREPARER)
        result = controle_integrite(self.company)
        self.assertIn(
            ticket.id,
            result['tickets_clotures_intervention_ouverte']['ids'])

    def test_healthy_case_ignored(self):
        inst = self._installation(statut=Installation.Statut.EN_COURS)
        ticket = Ticket.objects.create(
            company=self.company, reference='TCK-2', client=self.client_obj,
            statut=Ticket.Statut.CLOTURE)
        Intervention.objects.create(
            company=self.company, installation=inst, ticket=ticket,
            statut=Intervention.Statut.VALIDEE)
        result = controle_integrite(self.company)
        self.assertNotIn(
            ticket.id,
            result['tickets_clotures_intervention_ouverte']['ids'])


class TestContratsMaintenanceExpires(IntegrityBase):
    def test_detects_constructed_case(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            date_debut=date.today() - timedelta(days=400), actif=True,
            date_renouvellement=date.today() - timedelta(days=5))
        result = controle_integrite(self.company)
        self.assertIn(
            contrat.id, result['contrats_maintenance_expires']['ids'])

    def test_healthy_case_future_renewal_ignored(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            date_debut=date.today(), actif=True,
            date_renouvellement=date.today() + timedelta(days=30))
        result = controle_integrite(self.company)
        self.assertNotIn(
            contrat.id, result['contrats_maintenance_expires']['ids'])

    def test_inactive_contrat_ignored(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            date_debut=date.today() - timedelta(days=400), actif=False,
            date_renouvellement=date.today() - timedelta(days=5))
        result = controle_integrite(self.company)
        self.assertNotIn(
            contrat.id, result['contrats_maintenance_expires']['ids'])


class TestFacturesPayeesAvecSolde(IntegrityBase):
    def test_healthy_case_zero_balance_ignored(self):
        facture = Facture.objects.create(
            company=self.company, reference='FAC-2', client=self.client_obj,
            statut=Facture.Statut.PAYEE)
        result = controle_integrite(self.company)
        self.assertNotIn(
            facture.id, result['factures_payees_avec_solde']['ids'])

    def test_detects_constructed_case_via_property(self):
        """Une facture `payee` dont `montant_du` (propriété calculée depuis
        les lignes/paiements) reste > 0 est détectée — on force la valeur de
        la propriété plutôt que de construire des lignes/paiements complets,
        ce qui isole le test de la logique de calcul du solde (déjà testée
        ailleurs) et vérifie uniquement la règle d'intégrité elle-même."""
        import unittest.mock as mock
        facture = Facture.objects.create(
            company=self.company, reference='FAC-1', client=self.client_obj,
            statut=Facture.Statut.PAYEE)
        with mock.patch(
                'apps.ventes.models.Facture.montant_du',
                new_callable=mock.PropertyMock, return_value=Decimal('500')):
            result = controle_integrite(self.company)
        self.assertIn(facture.id, result['factures_payees_avec_solde']['ids'])


class TestEndpointAndNotification(IntegrityBase):
    def test_endpoint_gated_to_responsable_or_admin(self):
        limited = User.objects.create_user(
            username='limited_int', password='x', company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(limited)}')
        resp = api.get('/api/django/reporting/insights/integrite/')
        self.assertEqual(resp.status_code, 403)

    def test_endpoint_returns_structure(self):
        resp = self.api.get('/api/django/reporting/insights/integrite/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('familles', resp.data)
        self.assertIn('total_anomalies', resp.data)
        self.assertIn('devis_acceptes_sans_chantier', resp.data['familles'])

    def test_tenant_isolation(self):
        other_client = Client.objects.create(
            company=self.other_company, nom='AutreClient')
        Devis.objects.create(
            company=self.other_company, reference='DEV-OTHER',
            client=other_client, statut=Devis.Statut.ACCEPTE)
        result = controle_integrite(self.company)
        self.assertEqual(result['devis_acceptes_sans_chantier']['ids'], [])

    def test_command_notifies_only_when_anomalies_found(self):
        from io import StringIO
        from django.core.management import call_command
        import unittest.mock as mock

        # Société saine -> aucune notification.
        healthy_co = Company.objects.get_or_create(
            slug='yserv13-healthy', defaults={'nom': 'Healthy Co'})[0]
        out = StringIO()
        with mock.patch(
                'apps.reporting.management.commands.controle_integrite'
                '._notify_anomalies') as mock_notify:
            call_command('controle_integrite', '--company', healthy_co.slug,
                         stdout=out)
        mock_notify.assert_not_called()

        # Société avec anomalie construite -> notifie.
        Devis.objects.create(
            company=self.company, reference='DEV-CMD', client=self.client_obj,
            statut=Devis.Statut.ACCEPTE)
        out2 = StringIO()
        with mock.patch(
                'apps.reporting.management.commands.controle_integrite'
                '._notify_anomalies') as mock_notify2:
            call_command('controle_integrite', '--company', self.company.slug,
                         stdout=out2)
        mock_notify2.assert_called_once()

    def test_total_anomalies_helper(self):
        Devis.objects.create(
            company=self.company, reference='DEV-TOT', client=self.client_obj,
            statut=Devis.Statut.ACCEPTE)
        result = controle_integrite(self.company)
        self.assertGreaterEqual(total_anomalies(result), 1)


class TestControleIntegriteBeatTask(IntegrityBase):
    """WIR22 — la tâche Beat `reporting.controle_integrite` (planifiée dans
    `erp_agentique/celery.py`, entrée `reporting-controle-integrite-hebdo`)
    ne correspondait à AUCUNE tâche Celery enregistrée : Beat échouait
    silencieusement chaque semaine et `total_anomalies` n'était jamais
    consulté par personne. `apps/reporting/tasks.py` ajoute la tâche
    manquante ; elle relaie vers la commande de gestion déjà éprouvée."""

    def test_task_registered_with_expected_beat_name(self):
        from apps.reporting.tasks import controle_integrite_task
        self.assertEqual(
            controle_integrite_task.name, 'reporting.controle_integrite')

    def test_beat_task_notifies_admin_in_app_when_anomaly_detected(self):
        """Done = une anomalie détectée génère une notification in-app
        visible par un admin, sans lire les logs serveur."""
        from apps.notifications.models import Notification
        from apps.reporting.tasks import run_controle_integrite_beat

        Devis.objects.create(
            company=self.company, reference='DEV-BEAT', client=self.client_obj,
            statut=Devis.Statut.ACCEPTE)

        run_controle_integrite_beat()

        notif = Notification.objects.filter(
            recipient=self.user, company=self.company,
            title__icontains="Contrôle d'intégrité").first()
        self.assertIsNotNone(notif)
        self.assertIn('Devis acceptés sans chantier créé', notif.body)

    def test_beat_task_does_not_notify_when_no_anomaly(self):
        from apps.notifications.models import Notification
        from apps.reporting.tasks import run_controle_integrite_beat

        run_controle_integrite_beat()

        self.assertFalse(
            Notification.objects.filter(
                recipient=self.user,
                title__icontains="Contrôle d'intégrité").exists())
