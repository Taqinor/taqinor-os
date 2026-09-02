"""AUD319 — un rejeu CONCURRENT du même `client_op_id` ne casse plus le lot.

Défaut d'origine : `_apply_one` teste l'existence d'un `FieldOp` HORS de tout
verrou, puis n'ouvre `transaction.atomic()` qu'autour du handler + du
`FieldOp.objects.create()` — une fenêtre TOCTOU. La
`UniqueConstraint(company, client_op_id)` existe bien, mais seule
`FieldOpError` était catchée : `django.db.IntegrityError` remontait non gérée
à travers `apply_batch` puis `FieldSyncView.post` (qui ne catche que
`ValueError`) → 500 générique, alors que les opérations PRÉCÉDENTES du même
lot étaient déjà committées et que le terminal ne savait plus ce qui avait
réellement été appliqué.

La course est simulée de façon DÉTERMINISTE : la lecture de dédup
(`_fieldop_memorise`, le point de lecture unique) rate au premier appel — la
fenêtre TOCTOU — puis retrouve le gagnant au second. La violation d'unicité
elle-même n'est PAS simulée : c'est la vraie contrainte PostgreSQL qui la
lève, sur une vraie ligne `FieldOp` concurrente.

Run :
    python manage.py test apps.installations.tests_aud319_field_sync_course -v2
"""
import itertools
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations import field_sync
from apps.installations.models import (
    ComponentSerial, FieldOp, Installation, Intervention,
)

User = get_user_model()
_seq = itertools.count(1)
SYNC_URL = '/api/django/installations/sync/'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud319-co-{n}', defaults={'nom': f'AUD319 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FieldSyncCourseTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'aud319-{next(_seq)}', password='x',
            company=self.company, role_legacy='admin')
        self.api = auth(self.user)
        self.inst = Installation.objects.create(
            company=self.company, reference=f'AUD319-{next(_seq)}',
            statut=Installation.Statut.EN_COURS)
        self.iv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention=Intervention.Type.POSE, created_by=self.user)

    def _op(self, op_id, numero='SN-1'):
        return {'client_op_id': op_id, 'op_type': 'intervention.serial',
                'payload': {'intervention': self.iv.id,
                            'designation': 'Onduleur',
                            'numero_serie': numero}}

    def test_collision_avec_le_gagnant_rend_un_replayed(self):
        """ROUGE avant AUD319 : IntegrityError non catchée → 500 générique."""
        gagnant = FieldOp.objects.create(
            company=self.company, client_op_id='op-course',
            op_type='intervention.serial', target_type='intervention',
            target_id=self.iv.id, result={'serial': 999,
                                          'numero_serie': 'SN-GAGNANT'},
            ok=True, created_by=self.user)
        vrai = field_sync._fieldop_memorise
        with mock.patch.object(
                field_sync, '_fieldop_memorise',
                side_effect=[None, gagnant]) as lecture:
            r = self.api.post(
                SYNC_URL, {'ops': [self._op('op-course')]}, format='json')
        self.assertEqual(lecture.call_count, 2)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        self.assertEqual(r.data['replayed'], 1)
        self.assertEqual(r.data['errors'], 0)
        self.assertEqual(r.data['results'][0]['status'], 'replayed')
        self.assertEqual(
            r.data['results'][0]['result'], {'serial': 999,
                                             'numero_serie': 'SN-GAGNANT'})
        # L'effet du PERDANT a été annulé avec sa transaction.
        self.assertEqual(
            ComponentSerial.objects.filter(intervention=self.iv).count(), 0)
        self.assertEqual(
            FieldOp.objects.filter(
                company=self.company, client_op_id='op-course').count(), 1)
        self.assertIs(field_sync._fieldop_memorise, vrai)

    def test_le_lot_continue_apres_la_collision(self):
        """Les op suivantes du lot s'appliquent — plus de 500 au milieu."""
        gagnant = FieldOp.objects.create(
            company=self.company, client_op_id='op-course-2',
            op_type='intervention.serial', target_type='intervention',
            target_id=self.iv.id, result={'serial': 1, 'numero_serie': 'X'},
            ok=True, created_by=self.user)
        with mock.patch.object(
                field_sync, '_fieldop_memorise',
                side_effect=[None, gagnant, None]):
            r = self.api.post(SYNC_URL, {'ops': [
                self._op('op-course-2'),
                self._op('op-suivante', numero='SN-2'),
            ]}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        self.assertEqual(r.data['replayed'], 1)
        self.assertEqual(r.data['applied'], 1)
        self.assertEqual(r.data['errors'], 0)
        self.assertEqual(
            ComponentSerial.objects.filter(
                intervention=self.iv, numero_serie='SN-2').count(), 1)

    def test_collision_sans_gagnant_est_une_erreur_pas_un_500(self):
        """Une ligne concurrente `ok=False` n'est pas un rejeu : le lot
        continue avec une erreur applicative, jamais une 500."""
        FieldOp.objects.create(
            company=self.company, client_op_id='op-ko',
            op_type='intervention.serial', target_type='intervention',
            target_id=self.iv.id, result={}, ok=False, created_by=self.user)
        r = self.api.post(SYNC_URL, {'ops': [
            self._op('op-ko'),
            self._op('op-ok', numero='SN-3'),
        ]}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        self.assertEqual(r.data['errors'], 1)
        self.assertEqual(r.data['applied'], 1)
        self.assertEqual(r.data['results'][0]['status'], 'error')
        self.assertIn("intégrité", r.data['results'][0]['error'])
        self.assertEqual(
            ComponentSerial.objects.filter(
                intervention=self.iv, numero_serie='SN-3').count(), 1)

    def test_rejeu_ordinaire_inchange(self):
        """Non-régression : hors course, le rejeu reste un no-op mémorisé."""
        r1 = self.api.post(
            SYNC_URL, {'ops': [self._op('op-simple')]}, format='json')
        self.assertEqual(r1.data['applied'], 1)
        r2 = self.api.post(
            SYNC_URL, {'ops': [self._op('op-simple')]}, format='json')
        self.assertEqual(r2.data['replayed'], 1)
        self.assertEqual(
            ComponentSerial.objects.filter(intervention=self.iv).count(), 1)
