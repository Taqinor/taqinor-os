"""NTSEC19 — Tests campagnes de revue d'accès + attestation manager.

Garanties : le lancement génère un item par compte du périmètre, un manager
atteste ou révoque, une révocation retire le rôle, tout scopé société.
"""
from apps.roles.models import Role
from authentication.models import CustomUser
from testkit.base import TenantAPITestCase
from testkit.factories import UserFactory

from apps.accessreview.models import AccessReviewCampaign, AccessReviewItem
from apps.accessreview.services import generate_items


class AccessReviewTests(TenantAPITestCase):
    BASE = '/api/django/accessreview/campaigns/'

    def _admin(self):
        return self.client_as(role=CustomUser.ROLE_ADMIN)

    def test_create_generates_items_for_each_user(self):
        UserFactory(company=self.company, username='m1')
        UserFactory(company=self.company, username='m2')
        r = self._admin().post(
            self.BASE, {'nom': 'Q3 review', 'perimetre': 'all'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        campaign = AccessReviewCampaign.objects.get()
        # Un item par compte actif de la société (au moins m1, m2, l'admin…).
        self.assertGreaterEqual(campaign.items.count(), 3)
        self.assertEqual(
            campaign.items.filter(company=self.company).count(),
            campaign.items.count())

    def test_non_admin_forbidden(self):
        r = self.client_as().post(self.BASE, {'nom': 'x'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_items_scoped_to_company(self):
        UserFactory(company=self.other_company, username='foreigner')
        campaign = AccessReviewCampaign.objects.create(
            company=self.company, nom='c', perimetre='all')
        generate_items(campaign)
        users = set(campaign.items.values_list('user__username', flat=True))
        self.assertNotIn('foreigner', users)

    def test_attester_revoke_removes_role(self):
        role = Role.objects.create(company=self.company, nom='Compta')
        member = UserFactory(
            company=self.company, username='rev', role=role)
        campaign = AccessReviewCampaign.objects.create(
            company=self.company, nom='c', perimetre='all')
        generate_items(campaign)
        item = AccessReviewItem.objects.get(campagne=campaign, user=member)
        r = self._admin().post(
            f'{self.BASE}{campaign.id}/attester/',
            {'item': item.id, 'decision': 'revoque',
             'commentaire': 'plus besoin'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        member.refresh_from_db()
        self.assertIsNone(member.role_id)
        item.refresh_from_db()
        self.assertEqual(item.decision, 'revoque')
        self.assertIsNotNone(item.reviewer_id)
        self.assertIsNotNone(item.decided_at)

    def test_attester_maintien_keeps_role(self):
        role = Role.objects.create(company=self.company, nom='Compta')
        member = UserFactory(
            company=self.company, username='keep', role=role)
        campaign = AccessReviewCampaign.objects.create(
            company=self.company, nom='c', perimetre='all')
        generate_items(campaign)
        item = AccessReviewItem.objects.get(campagne=campaign, user=member)
        r = self._admin().post(
            f'{self.BASE}{campaign.id}/attester/',
            {'item': item.id, 'decision': 'maintenu'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        member.refresh_from_db()
        self.assertEqual(member.role_id, role.id)

    def test_cannot_attest_foreign_item(self):
        other_campaign = AccessReviewCampaign.objects.create(
            company=self.other_company, nom='c', perimetre='all')
        member = UserFactory(company=self.other_company, username='fm')
        foreign_item = AccessReviewItem.objects.create(
            company=self.other_company, campagne=other_campaign, user=member)
        my_campaign = AccessReviewCampaign.objects.create(
            company=self.company, nom='mine', perimetre='all')
        r = self._admin().post(
            f'{self.BASE}{my_campaign.id}/attester/',
            {'item': foreign_item.id, 'decision': 'revoque'}, format='json')
        self.assertEqual(r.status_code, 400)
