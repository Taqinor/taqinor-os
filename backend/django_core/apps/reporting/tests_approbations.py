"""XKB1 — boîte d'approbations centralisée cross-app (tests + anti-fuite)."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.automation.models import AutomationApproval
from apps.contrats.models import Contrat, EtapeApprobation
from apps.ged.models import Cabinet, Document, Folder
from apps.installations.models_demande_achat import DemandeAchat
from apps.reporting.models import ApprobationSlaConfig
from authentication.models import Company
from core.models import WorkflowDefinition, WorkflowStepDefinition
from core import workflow as core_workflow

User = get_user_model()


class ApprobationsBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='xkb1-co', defaults={'nom': 'XKB1 Co'})[0]
        self.other_company = Company.objects.get_or_create(
            slug='xkb1-other', defaults={'nom': 'XKB1 Other'})[0]
        self.user = User.objects.create_user(
            username='xkb1_u', password='x', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _url(self):
        return '/api/django/reporting/approbations-en-attente/'


class TestApprobationsAggregation(ApprobationsBase):
    def test_automation_source_listed(self):
        AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING,
            description='Envoyer relance')
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        sources = {it['source'] for it in resp.data['items']}
        self.assertIn('automation', sources)

    def test_contrats_source_listed(self):
        contrat = Contrat.objects.create(
            company=self.company, objet='Contrat test', reference='C-1')
        EtapeApprobation.objects.create(
            company=self.company, contrat=contrat, niveau=1,
            statut=EtapeApprobation.Statut.EN_ATTENTE)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        sources = {it['source'] for it in resp.data['items']}
        self.assertIn('contrats', sources)

    def test_ged_source_listed(self):
        cab = Cabinet.objects.create(company=self.company, nom='Docs')
        folder = Folder.objects.create(
            company=self.company, cabinet=cab, nom='Entrants')
        doc = Document.objects.create(
            company=self.company, folder=folder, nom='Contrat.pdf')
        from apps.ged.models import APPROBATION_EN_ATTENTE
        from apps.ged.models import DemandeApprobation
        DemandeApprobation.objects.create(
            company=self.company, document=doc, statut=APPROBATION_EN_ATTENTE)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        sources = {it['source'] for it in resp.data['items']}
        self.assertIn('ged', sources)

    def test_installations_source_listed(self):
        DemandeAchat.objects.create(
            company=self.company, reference='DA-1', objet='Panneaux',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        sources = {it['source'] for it in resp.data['items']}
        self.assertIn('installations', sources)

    def test_workflow_source_listed(self):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='validation_x', nom='Validation X')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Étape 1')
        now = timezone.make_aware(datetime.datetime(2026, 1, 1, 8, 0, 0))
        core_workflow.demarrer_workflow(wf, self.company, self.company, now=now)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        sources = {it['source'] for it in resp.data['items']}
        self.assertIn('workflow', sources)

    def test_source_filter(self):
        AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-2', objet='Onduleurs',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = self.api.get(self._url() + '?source=automation')
        self.assertEqual(resp.status_code, 200)
        sources = {it['source'] for it in resp.data['items']}
        self.assertEqual(sources, {'automation'})

    def test_non_pending_items_excluded(self):
        DemandeAchat.objects.create(
            company=self.company, reference='DA-3', objet='Câbles',
            statut=DemandeAchat.Statut.BROUILLON)
        AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.APPROVED)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 0)


class TestApprobationsTenantIsolation(ApprobationsBase):
    def test_other_company_items_never_leak(self):
        DemandeAchat.objects.create(
            company=self.other_company, reference='DA-OTHER', objet='X',
            statut=DemandeAchat.Statut.SOUMISE)
        AutomationApproval.objects.create(
            company=self.other_company,
            status=AutomationApproval.Status.PENDING)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 0)


class TestApprobationsDecision(ApprobationsBase):
    def _decide_url(self):
        return self._url() + 'decider/'

    def test_approve_automation_via_source_service(self):
        approval = AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        resp = self.api.post(self._decide_url(), {
            'source': 'automation', 'id': approval.id, 'decision': 'approuver',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, AutomationApproval.Status.APPROVED)
        self.assertEqual(approval.decided_by_id, self.user.id)

    def test_reject_requires_motif(self):
        approval = AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        resp = self.api.post(self._decide_url(), {
            'source': 'automation', 'id': approval.id, 'decision': 'refuser',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_reject_with_motif_installations(self):
        da = DemandeAchat.objects.create(
            company=self.company, reference='DA-4', objet='Test',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = self.api.post(self._decide_url(), {
            'source': 'installations', 'id': da.id, 'decision': 'refuser',
            'motif': 'Budget dépassé',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.REFUSEE)
        self.assertEqual(da.motif_refus, 'Budget dépassé')

    def test_decide_other_company_item_404(self):
        da = DemandeAchat.objects.create(
            company=self.other_company, reference='DA-5', objet='Test',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = self.api.post(self._decide_url(), {
            'source': 'installations', 'id': da.id, 'decision': 'approuver',
        }, format='json')
        self.assertEqual(resp.status_code, 404)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)

    def test_bulk_decision(self):
        a1 = AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        a2 = AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        resp = self.api.post(
            self._url() + 'decider-en-masse/',
            {
                'items': [
                    {'source': 'automation', 'id': a1.id},
                    {'source': 'automation', 'id': a2.id},
                ],
                'decision': 'approuver',
            }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['resultats']), 2)
        a1.refresh_from_db()
        a2.refresh_from_db()
        self.assertEqual(a1.status, AutomationApproval.Status.APPROVED)
        self.assertEqual(a2.status, AutomationApproval.Status.APPROVED)


class TestZctr9Facettes(ApprobationsBase):
    """ZCTR9 — filtre/tri catégorie/priorité/urgence sur la boîte XKB1."""

    def _set_created(self, obj, when):
        # date_creation est auto_now_add=True : on force la valeur en base
        # via update() pour simuler une ancienneté réelle sans repasser par
        # save() (qui réécrirait auto_now_add).
        type(obj).objects.filter(pk=obj.pk).update(date_creation=when)
        obj.refresh_from_db()

    def test_categorie_filter_is_alias_for_source(self):
        AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-ZCTR9-1', objet='Test',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = self.api.get(self._url() + '?categorie=installations')
        self.assertEqual(resp.status_code, 200)
        sources = {it['source'] for it in resp.data['items']}
        self.assertEqual(sources, {'installations'})

    def test_priorite_filter(self):
        DemandeAchat.objects.create(
            company=self.company, reference='DA-ZCTR9-2', objet='Urgent',
            statut=DemandeAchat.Statut.SOUMISE,
            priorite=DemandeAchat.Priorite.HAUTE)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-ZCTR9-3', objet='Normal',
            statut=DemandeAchat.Statut.SOUMISE,
            priorite=DemandeAchat.Priorite.NORMALE)
        resp = self.api.get(self._url() + '?priorite=haute')
        self.assertEqual(resp.status_code, 200)
        refs = {it['libelle'] for it in resp.data['items']}
        self.assertEqual(len(resp.data['items']), 1)
        self.assertIn('DA-ZCTR9-2', next(iter(refs)))

    def test_anciennete_and_en_retard_flag(self):
        # SLA société explicite à 2 jours ouvrés pour un test déterministe.
        ApprobationSlaConfig.objects.create(
            company=self.company, sla_jours=2)
        old = DemandeAchat.objects.create(
            company=self.company, reference='DA-ZCTR9-OLD', objet='Vieux',
            statut=DemandeAchat.Statut.SOUMISE)
        # Un lundi loin dans le passé pour ne dépendre d'aucun jour férié.
        self._set_created(
            old, timezone.make_aware(datetime.datetime(2026, 6, 1, 8, 0, 0)))
        recent = DemandeAchat.objects.create(
            company=self.company, reference='DA-ZCTR9-NEW', objet='Récent',
            statut=DemandeAchat.Statut.SOUMISE)
        self._set_created(recent, timezone.now())

        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        by_ref = {it['libelle']: it for it in resp.data['items']}
        old_item = by_ref['Réquisition DA-ZCTR9-OLD']
        new_item = by_ref['Réquisition DA-ZCTR9-NEW']
        self.assertGreaterEqual(old_item['anciennete_jours'], 2)
        self.assertTrue(old_item['en_retard'])
        self.assertEqual(new_item['anciennete_jours'], 0)
        self.assertFalse(new_item['en_retard'])

    def test_default_sla_is_three_working_days_without_config(self):
        # Aucune ApprobationSlaConfig pour la société → défaut 3 j ouvrés.
        da = DemandeAchat.objects.create(
            company=self.company, reference='DA-ZCTR9-DEFAULT', objet='X',
            statut=DemandeAchat.Statut.SOUMISE)
        self._set_created(
            da, timezone.make_aware(datetime.datetime(2026, 6, 1, 8, 0, 0)))
        resp = self.api.get(self._url())
        item = next(
            it for it in resp.data['items']
            if it['libelle'] == 'Réquisition DA-ZCTR9-DEFAULT')
        self.assertGreaterEqual(item['anciennete_jours'], 3)
        self.assertTrue(item['en_retard'])

    def test_trier_urgence_puts_late_items_first(self):
        ApprobationSlaConfig.objects.create(
            company=self.company, sla_jours=2)
        late = DemandeAchat.objects.create(
            company=self.company, reference='DA-ZCTR9-LATE', objet='X',
            statut=DemandeAchat.Statut.SOUMISE)
        self._set_created(
            late, timezone.make_aware(datetime.datetime(2026, 6, 1, 8, 0, 0)))
        fresh = DemandeAchat.objects.create(
            company=self.company, reference='DA-ZCTR9-FRESH', objet='X',
            statut=DemandeAchat.Statut.SOUMISE)
        self._set_created(fresh, timezone.now())

        resp = self.api.get(self._url() + '?trier=urgence')
        self.assertEqual(resp.status_code, 200)
        libelles = [it['libelle'] for it in resp.data['items']]
        self.assertEqual(libelles[0], 'Réquisition DA-ZCTR9-LATE')

    def test_trier_anciennete_orders_oldest_first(self):
        old = DemandeAchat.objects.create(
            company=self.company, reference='DA-ZCTR9-OLDEST', objet='X',
            statut=DemandeAchat.Statut.SOUMISE)
        self._set_created(
            old, timezone.make_aware(datetime.datetime(2026, 5, 1, 8, 0, 0)))
        newer = DemandeAchat.objects.create(
            company=self.company, reference='DA-ZCTR9-NEWER', objet='X',
            statut=DemandeAchat.Statut.SOUMISE)
        self._set_created(
            newer, timezone.make_aware(datetime.datetime(2026, 6, 20, 8, 0, 0)))

        resp = self.api.get(self._url() + '?trier=anciennete')
        self.assertEqual(resp.status_code, 200)
        libelles = [it['libelle'] for it in resp.data['items']]
        self.assertEqual(libelles[0], 'Réquisition DA-ZCTR9-OLDEST')

    def test_tenant_scoping_preserved_with_new_params(self):
        DemandeAchat.objects.create(
            company=self.other_company, reference='DA-ZCTR9-OTHER',
            objet='X', statut=DemandeAchat.Statut.SOUMISE,
            priorite=DemandeAchat.Priorite.HAUTE)
        resp = self.api.get(
            self._url() + '?categorie=installations&priorite=haute'
            '&trier=urgence')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 0)
