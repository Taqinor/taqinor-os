"""ZSAL2 — Plans d'activité (séquences de tâches pré-définies applicables en
un clic à un lead, style Odoo « Activity Plans »).

Covers:
  - Application d'un plan crée toutes les activités aux bonnes échéances
    relatives (delai_jours depuis aujourd'hui).
  - Ré-appliquer le même plan ne duplique pas (idempotence par lead+plan).
  - Un plan archivé (actif=False) n'est pas applicable (ValueError / 400).
  - Assignation : assigne_par_defaut > owner du lead > acteur.
  - Scoping multi-tenant : plan d'une autre société → 404 via l'API.
"""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import EtapePlanActivite, Lead, PlanActivite
from apps.crm.services import appliquer_plan_activite
from apps.records.models import Activity, ActivityType

User = get_user_model()


def make_company(slug='zsal2-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


def make_plan(company, etapes):
    """etapes: liste de (delai_jours, resume, assigne)."""
    plan = PlanActivite.objects.create(company=company, nom='Nouveau lead solaire')
    atype, _ = ActivityType.objects.get_or_create(
        company=company, nom='Appel', defaults={'ordre': 1})
    for i, (delai, resume, assigne) in enumerate(etapes):
        EtapePlanActivite.objects.create(
            plan=plan, ordre=i, activity_type=atype,
            delai_jours=delai, resume_defaut=resume,
            assigne_par_defaut=assigne)
    return plan


class TestAppliquerPlanActivite(TestCase):
    def setUp(self):
        self.company = make_company()
        self.owner = User.objects.create_user(
            username='zsal2owner', password='x', company=self.company)
        self.acteur = User.objects.create_user(
            username='zsal2acteur', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.owner)

    def test_applique_toutes_les_etapes_aux_bonnes_echeances(self):
        plan = make_plan(self.company, [
            (0, 'Appeler', None),
            (1, 'Email étude', None),
            (3, 'Visite technique', None),
            (7, 'Relance devis', None),
        ])
        activites = appliquer_plan_activite(
            lead=self.lead, plan=plan, user=self.acteur)
        self.assertEqual(len(activites), 4)
        today = datetime.date.today()
        due_dates = sorted(a.due_date for a in activites)
        self.assertEqual(due_dates, [
            today, today + datetime.timedelta(days=1),
            today + datetime.timedelta(days=3),
            today + datetime.timedelta(days=7),
        ])
        ct = ContentType.objects.get_for_model(Lead)
        self.assertEqual(
            Activity.objects.filter(
                company=self.company, content_type=ct,
                object_id=self.lead.id).count(),
            4)

    def test_reappliquer_le_meme_plan_ne_duplique_pas(self):
        plan = make_plan(self.company, [(0, 'Appeler', None)])
        appliquer_plan_activite(lead=self.lead, plan=plan, user=self.acteur)
        appliquer_plan_activite(lead=self.lead, plan=plan, user=self.acteur)
        ct = ContentType.objects.get_for_model(Lead)
        self.assertEqual(
            Activity.objects.filter(
                company=self.company, content_type=ct,
                object_id=self.lead.id).count(),
            1)

    def test_plan_archive_non_applicable(self):
        plan = make_plan(self.company, [(0, 'Appeler', None)])
        plan.actif = False
        plan.save(update_fields=['actif'])
        with self.assertRaises(ValueError):
            appliquer_plan_activite(lead=self.lead, plan=plan, user=self.acteur)

    def test_assignation_par_defaut_priorite(self):
        fixe = User.objects.create_user(
            username='zsal2fixe', password='x', company=self.company)
        plan = make_plan(self.company, [
            (0, 'Assigné fixe', fixe),
            (0, 'Sans assigné fixe -> owner', None),
        ])
        activites = appliquer_plan_activite(
            lead=self.lead, plan=plan, user=self.acteur)
        par_resume = {a.summary: a for a in activites}
        self.assertEqual(par_resume['Assigné fixe'].assigned_to, fixe)
        self.assertEqual(
            par_resume['Sans assigné fixe -> owner'].assigned_to, self.owner)

    def test_sans_owner_ni_assigne_fixe_retombe_sur_acteur(self):
        lead_sans_owner = Lead.objects.create(company=self.company, nom='Sans owner')
        plan = make_plan(self.company, [(0, 'Appeler', None)])
        activites = appliquer_plan_activite(
            lead=lead_sans_owner, plan=plan, user=self.acteur)
        self.assertEqual(activites[0].assigned_to, self.acteur)


class TestAppliquerPlanAPIScoping(TestCase):
    def setUp(self):
        self.company = make_company('zsal2-co-a')
        self.other_company = make_company('zsal2-co-b')
        self.user = User.objects.create_user(
            username='zsal2apiuser', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Lead A')
        self.api = APIClient()
        token = AccessToken.for_user(self.user)
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_appliquer_plan_endpoint_happy_path(self):
        plan = make_plan(self.company, [(0, 'Appeler', None)])
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/appliquer-plan/',
            {'plan_id': plan.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)

    def test_plan_autre_societe_404(self):
        plan_autre = make_plan(self.other_company, [(0, 'Appeler', None)])
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/appliquer-plan/',
            {'plan_id': plan_autre.id}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_plan_archive_endpoint_400(self):
        plan = make_plan(self.company, [(0, 'Appeler', None)])
        plan.actif = False
        plan.save(update_fields=['actif'])
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/appliquer-plan/',
            {'plan_id': plan.id}, format='json')
        self.assertEqual(resp.status_code, 400)
