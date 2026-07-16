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
from apps.installations.models import Installation
from apps.installations.models_demande_achat import DemandeAchat, DemandeAchatLigne
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
        # VX101 — utilisateur Responsable, requis pour DÉCIDER une source
        # installations/contrats depuis cet agrégateur (`self.user` ci-dessus
        # reste un rôle normal, réutilisé par le test de régression AUTH).
        self.resp_user = User.objects.create_user(
            username='xkb1_resp', password='x', company=self.company,
            role_legacy='responsable')
        self.resp_api = APIClient()
        self.resp_api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.resp_user)}')

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
        # VX101 — décider une source `installations` exige le tier
        # Responsable/Admin : utilise `resp_api` (rôle normal → voir
        # TestVx101RoleGate ci-dessous pour le 403).
        da = DemandeAchat.objects.create(
            company=self.company, reference='DA-4', objet='Test',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = self.resp_api.post(self._decide_url(), {
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
        resp = self.resp_api.post(self._decide_url(), {
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


class TestVx101RoleGate(ApprobationsBase):
    """VX101 — [BUG AUTH] seul le tier Responsable/Admin peut DÉCIDER une
    source `installations`/`contrats` depuis l'agrégateur cross-app ; avant ce
    fix `decider_demande_achat`/l'étape de contrat n'étaient gardés par AUCUN
    rôle ici (un commercial ou technicien pouvait approuver). La LECTURE reste
    ouverte à tout rôle (non-régression)."""

    def _decide_url(self):
        return self._url() + 'decider/'

    def test_normal_role_forbidden_to_decide_installations(self):
        da = DemandeAchat.objects.create(
            company=self.company, reference='DA-VX101-1', objet='Test',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = self.api.post(self._decide_url(), {
            'source': 'installations', 'id': da.id, 'decision': 'approuver',
        }, format='json')
        self.assertEqual(resp.status_code, 403)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)

    def test_normal_role_forbidden_to_decide_contrats(self):
        contrat = Contrat.objects.create(
            company=self.company, objet='Contrat VX101', reference='C-VX101')
        etape = EtapeApprobation.objects.create(
            company=self.company, contrat=contrat, niveau=1,
            statut=EtapeApprobation.Statut.EN_ATTENTE)
        resp = self.api.post(self._decide_url(), {
            'source': 'contrats', 'id': etape.id, 'decision': 'approuver',
        }, format='json')
        self.assertEqual(resp.status_code, 403)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, EtapeApprobation.Statut.EN_ATTENTE)

    def test_responsable_can_decide_installations_and_contrats(self):
        da = DemandeAchat.objects.create(
            company=self.company, reference='DA-VX101-2', objet='Test',
            statut=DemandeAchat.Statut.SOUMISE)
        contrat = Contrat.objects.create(
            company=self.company, objet='Contrat VX101-2', reference='C-VX101-2')
        etape = EtapeApprobation.objects.create(
            company=self.company, contrat=contrat, niveau=1,
            statut=EtapeApprobation.Statut.EN_ATTENTE)
        r1 = self.resp_api.post(self._decide_url(), {
            'source': 'installations', 'id': da.id, 'decision': 'approuver',
        }, format='json')
        self.assertEqual(r1.status_code, 200, r1.data)
        r2 = self.resp_api.post(self._decide_url(), {
            'source': 'contrats', 'id': etape.id, 'decision': 'approuver',
        }, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)

    def test_reading_stays_open_to_normal_role(self):
        # La LECTURE de la boîte d'approbations n'est jamais gardée par ce
        # fix — seule la DÉCISION (POST decider/) l'est.
        DemandeAchat.objects.create(
            company=self.company, reference='DA-VX101-3', objet='Test',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        sources = {it['source'] for it in resp.data['items']}
        self.assertIn('installations', sources)

    def test_normal_role_can_still_decide_automation_ged_workflow(self):
        # Non-régression — le gate ne touche QUE installations/contrats.
        approval = AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        resp = self.api.post(self._decide_url(), {
            'source': 'automation', 'id': approval.id, 'decision': 'approuver',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


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


class TestVx100MontantEtLien(ApprobationsBase):
    """VX100 — montant réel + lien cliquable dans l'agrégateur d'approbations."""

    def test_installations_item_exposes_real_montant(self):
        da = DemandeAchat.objects.create(
            company=self.company, reference='DA-VX100-1', objet='Panneaux',
            statut=DemandeAchat.Statut.SOUMISE)
        DemandeAchatLigne.objects.create(
            demande=da, designation='Panneau 500W', quantite=10,
            prix_estime=1000)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        item = next(
            it for it in resp.data['items']
            if it['libelle'] == 'Réquisition DA-VX100-1')
        self.assertEqual(float(item['montant']), 10000.0)

    def test_installations_item_lien_points_to_chantier(self):
        chantier = Installation.objects.create(
            company=self.company, reference='CHT-VX100-1')
        DemandeAchat.objects.create(
            company=self.company, reference='DA-VX100-2', objet='Onduleurs',
            statut=DemandeAchat.Statut.SOUMISE, chantier=chantier)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        item = next(
            it for it in resp.data['items']
            if it['libelle'] == 'Réquisition DA-VX100-2')
        self.assertEqual(item['lien'], f'/chantiers?id={chantier.id}')

    def test_installations_item_lien_none_without_chantier(self):
        DemandeAchat.objects.create(
            company=self.company, reference='DA-VX100-3', objet='Câbles',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        item = next(
            it for it in resp.data['items']
            if it['libelle'] == 'Réquisition DA-VX100-3')
        self.assertIsNone(item['lien'])

    def test_other_sources_expose_montant_and_lien_keys_without_fabricating(self):
        AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        resp = self.api.get(self._url() + '?source=automation')
        self.assertEqual(resp.status_code, 200)
        item = resp.data['items'][0]
        self.assertIn('montant', item)
        self.assertIn('lien', item)
        self.assertIsNone(item['montant'])
        self.assertIsNone(item['lien'])

    def test_contrats_item_lien_points_to_contrat_detail(self):
        contrat = Contrat.objects.create(
            company=self.company, objet='Contrat VX100', reference='C-VX100')
        EtapeApprobation.objects.create(
            company=self.company, contrat=contrat, niveau=1,
            statut=EtapeApprobation.Statut.EN_ATTENTE)
        resp = self.api.get(self._url() + '?source=contrats')
        self.assertEqual(resp.status_code, 200)
        item = resp.data['items'][0]
        self.assertEqual(item['lien'], f'/contrats/{contrat.id}')

    def test_trier_montant_orders_amounts_descending(self):
        small = DemandeAchat.objects.create(
            company=self.company, reference='DA-VX100-SMALL', objet='X',
            statut=DemandeAchat.Statut.SOUMISE)
        DemandeAchatLigne.objects.create(
            demande=small, designation='Petit', quantite=1, prix_estime=100)
        big = DemandeAchat.objects.create(
            company=self.company, reference='DA-VX100-BIG', objet='X',
            statut=DemandeAchat.Statut.SOUMISE)
        DemandeAchatLigne.objects.create(
            demande=big, designation='Gros', quantite=1, prix_estime=999999)

        resp = self.api.get(
            self._url() + '?source=installations&trier=montant')
        self.assertEqual(resp.status_code, 200)
        libelles = [it['libelle'] for it in resp.data['items']]
        self.assertEqual(libelles[0], 'Réquisition DA-VX100-BIG')


class TestVx218NiveauEscalade(ApprobationsBase):
    """VX218 — l'agrégateur expose l'état de relance/escalade YEVNT9 côté
    demandeur (source `automation`, seule balayée par le sweep aujourd'hui;
    les autres sources renvoient les deux champs à None sans fabrication)."""

    def _make_pending_approval(self, days_old):
        from apps.automation.models import (
            ActionType, AutomationApproval, AutomationRule, TriggerType,
        )
        rule = AutomationRule.objects.create(
            company=self.company, nom='Règle VX218',
            trigger_type=TriggerType.DEVIS_ACCEPTED,
            action_type=ActionType.SEND_EMAIL, requires_approval=True)
        approval = AutomationApproval.objects.create(
            company=self.company, rule=rule, description='Action VX218',
            requested_by=self.user)
        approval.date_creation = timezone.now() - datetime.timedelta(
            days=days_old)
        approval.save(update_fields=['date_creation'])
        return approval

    def test_niveau_escalade_absent_by_default(self):
        AutomationApproval.objects.create(
            company=self.company, status=AutomationApproval.Status.PENDING)
        resp = self.api.get(self._url() + '?source=automation')
        self.assertEqual(resp.status_code, 200)
        item = resp.data['items'][0]
        self.assertIn('niveau_escalade', item)
        self.assertIsNone(item['niveau_escalade'])
        self.assertIsNone(item['derniere_relance_le'])

    def test_niveau_escalade_relance_after_sweep(self):
        from apps.notifications.services import sweep_approval_reminders
        approval = self._make_pending_approval(days_old=5)
        sweep_approval_reminders(self.company)
        resp = self.api.get(self._url() + '?source=automation')
        self.assertEqual(resp.status_code, 200)
        item = next(
            it for it in resp.data['items'] if it['id'] == approval.id)
        self.assertEqual(item['niveau_escalade'], 'relance')
        self.assertIsNotNone(item['derniere_relance_le'])

    def test_niveau_escalade_escalade_after_sweep(self):
        from apps.notifications.services import sweep_approval_reminders
        approval = self._make_pending_approval(days_old=10)
        sweep_approval_reminders(self.company)
        resp = self.api.get(self._url() + '?source=automation')
        self.assertEqual(resp.status_code, 200)
        item = next(
            it for it in resp.data['items'] if it['id'] == approval.id)
        self.assertEqual(item['niveau_escalade'], 'escalade')

    def test_other_sources_never_fabricate_niveau_escalade(self):
        DemandeAchat.objects.create(
            company=self.company, reference='DA-VX218-1', objet='X',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = self.api.get(self._url() + '?source=installations')
        self.assertEqual(resp.status_code, 200)
        item = resp.data['items'][0]
        self.assertIn('niveau_escalade', item)
        self.assertIsNone(item['niveau_escalade'])
        self.assertIsNone(item['derniere_relance_le'])
