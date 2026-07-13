"""Tests VX243(b) — lecture record-scopée du Journal (« l'historique de MON
dossier »).

Deux bornes de confiance vérifiées :
* un commercial SANS la permission Journal (`journal_activite_voir`) voit
  l'historique d'un lead DONT IL EST le propriétaire — et rien d'autre ;
* le Journal GLOBAL (gaté `can_view_activity_log`) reste tout-ou-rien : le
  même commercial y reste interdit.

Company-scoping strict : l'historique d'un objet d'une autre société est un
404, jamais une fuite.
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.roles.models import (
    Role, DIRECTEUR_PERMISSIONS, COMMERCIAL_PERMISSIONS,
)
from apps.crm.models import Lead
from apps.audit.models import AuditLog


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestObjectHistoryScoped(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VX243 Co', slug='vx243-co')
        self.dir_role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=DIRECTEUR_PERMISSIONS, est_systeme=True)
        self.com_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=COMMERCIAL_PERMISSIONS, est_systeme=True)
        self.directeur = CustomUser.objects.create_user(
            username='vx243dir', password='Secret@2026', company=self.company,
            role=self.dir_role, role_legacy='admin')
        self.owner = CustomUser.objects.create_user(
            username='vx243owner', password='Secret@2026', company=self.company,
            role=self.com_role)
        self.other_com = CustomUser.objects.create_user(
            username='vx243other', password='Secret@2026', company=self.company,
            role=self.com_role)

        self.lead = Lead.objects.create(
            company=self.company, nom='Dossier', owner=self.owner)
        self.ct = ContentType.objects.get_for_model(Lead)
        AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.UPDATE,
            content_type=self.ct, object_id=str(self.lead.pk),
            changes=[{'field': 'stage', 'old': 'NEW', 'new': 'CONTACTED'}],
        )

    def _url(self, lead=None):
        lead = lead or self.lead
        return reverse('audit-object-history', kwargs={
            'content_type': 'crm.lead', 'object_id': str(lead.pk)})

    # ── Borne 1 : le propriétaire voit l'historique de SON lead ──
    def test_owner_without_journal_permission_sees_own_lead_history(self):
        self.assertFalse(self.owner.can_view_activity_log)
        resp = auth(self.owner).get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    # ── Borne 2 : un non-propriétaire sans permission est refusé (403) ──
    def test_non_owner_without_journal_permission_forbidden(self):
        self.assertFalse(self.other_com.can_view_activity_log)
        resp = auth(self.other_com).get(self._url())
        self.assertEqual(resp.status_code, 403)

    # ── Le Journal GLOBAL reste tout-ou-rien : le propriétaire y est interdit ──
    def test_global_journal_still_gated_for_owner(self):
        resp = auth(self.owner).get('/api/django/audit/entries/')
        self.assertEqual(resp.status_code, 403)

    # ── Le Directeur (permission Journal) voit l'historique de n'importe quel
    #    objet de sa société, même sans en être propriétaire ──
    def test_director_with_permission_sees_any_object_history(self):
        self.assertTrue(self.directeur.can_view_activity_log)
        resp = auth(self.directeur).get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    # ── Scopage société : l'objet d'une autre société est un 404 ──
    def test_cross_company_is_404(self):
        other_company = Company.objects.create(
            nom='Autre', slug='vx243-autre')
        other_dir_role = Role.objects.create(
            company=other_company, nom='Directeur',
            permissions=DIRECTEUR_PERMISSIONS, est_systeme=True)
        other_director = CustomUser.objects.create_user(
            username='vx243otherdir', password='Secret@2026',
            company=other_company, role=other_dir_role, role_legacy='admin')
        resp = auth(other_director).get(self._url())
        self.assertEqual(resp.status_code, 404)

    def test_invalid_content_type_404(self):
        url = reverse('audit-object-history', kwargs={
            'content_type': 'bogus.model', 'object_id': '1'})
        resp = auth(self.directeur).get(url)
        self.assertEqual(resp.status_code, 404)
