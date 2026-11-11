"""QX25be — ``target_phone`` sur la liste d'activités (« Mes activités »).

Rend chaque ligne actionnable (tel:/wa.me côté front) : le téléphone de la cible
(lead/client) est résolu via un sélecteur crm, jamais un import de modèle crm.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.records.models import Activity, ActivityType
from apps.records.serializers import ActivitySerializer

User = get_user_model()


class Qx25TargetPhoneTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX25 Co', slug='qx25-co')
        self.user = User.objects.create_user(
            username='qx25_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.type_appel = ActivityType.objects.create(
            company=self.company, nom='Appel', ordre=10)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', telephone='+212600000060')
        self.act = Activity.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=self.lead.id, activity_type=self.type_appel,
            summary='Appeler', due_date=date.today(), assigned_to=self.user)

    def _req(self):
        return type('R', (), {'user': self.user})()

    def test_target_phone_resolved_for_lead(self):
        data = ActivitySerializer(
            self.act, context={'request': self._req()}).data
        self.assertEqual(data['target_phone'], '+212600000060')

    def test_target_phone_none_for_personal_task(self):
        personal = Activity.objects.create(
            company=self.company, activity_type=self.type_appel,
            summary='Tâche perso', due_date=date.today(),
            assigned_to=self.user, personnelle=True)
        data = ActivitySerializer(
            personal, context={'request': self._req()}).data
        self.assertIsNone(data['target_phone'])

    def test_target_phone_in_mine_endpoint(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.get('/api/django/records/activities/mine/')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Cherche notre activité dans les buckets et vérifie le champ présent.
        found = False
        for bucket in resp.data.values():
            if not isinstance(bucket, list):
                continue
            for row in bucket:
                if row.get('id') == self.act.id:
                    self.assertEqual(row.get('target_phone'), '+212600000060')
                    found = True
        self.assertTrue(found)

    def test_target_phone_masque_sans_client_pii_voir(self):
        """ALEC34 (C-ALEC-031) — Commercial terrain livré (sans
        `client_pii_voir`) : `target_phone` null dans `activities/mine/` ;
        Directeur : le numéro."""
        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        roles = dict(CANONICAL_SYSTEM_ROLES)

        def lignes(nom):
            role = Role.objects.create(company=self.company, nom=nom,
                                       permissions=list(roles[nom]))
            user = User.objects.create_user(
                username=f'alec34-{nom}', password='x', role=role,
                company=self.company)
            Activity.objects.create(
                company=self.company,
                content_type=ContentType.objects.get_for_model(Lead),
                object_id=self.lead.id, activity_type=self.type_appel,
                summary=f'Appel {nom}', due_date=date.today(),
                assigned_to=user, created_by=user)
            api = APIClient()
            api.credentials(
                HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
            resp = api.get('/api/django/records/activities/mine/')
            self.assertEqual(resp.status_code, 200, resp.content)
            return [row for bucket in resp.data.values() if isinstance(bucket, list)
                    for row in bucket if row.get('summary') == f'Appel {nom}']

        terrain = lignes('Commercial terrain')
        self.assertEqual(len(terrain), 1)
        self.assertIsNone(terrain[0]['target_phone'])
        directeur = lignes('Directeur')
        self.assertEqual(len(directeur), 1)
        self.assertEqual(directeur[0]['target_phone'], '+212600000060')
