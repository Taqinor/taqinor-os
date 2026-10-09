"""ACHT32 (C-ACHT-029) — les handlers de `/installations/sync/` appliquent
l'instant de SAISIE (`client_ts`, borné au présent) et refusent en `conflit`
une op de saisie dont `base_updated_at` précède la dernière modification en
ligne (option (a) d'ACHT91, détection de `offlinesync/conflicts.py`).

Rejoue CINT-6 : check-in du 01/10 synchronisé plus tard enregistré à l'heure
de synchro ; op hors-ligne (qté 3) écrasant une correction en ligne (5).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_sync_horodatage"
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    ConsommationLigne, Installation, Intervention, MaterielConsommation,
)

User = get_user_model()
SYNC = '/api/django/installations/sync/'
BASE = '/api/django/installations/interventions'


class SyncHorodatageTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht32', defaults={'nom': 'Co ACHT32'})
        self.user = User.objects.create_user(
            username='resp-acht32', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT32')
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user)
        self.cons = MaterielConsommation.objects.create(
            company=self.company, intervention=self.iv)
        self.ligne = ConsommationLigne.objects.create(
            company=self.company, consommation=self.cons,
            designation='Câble', quantite_prevue=Decimal('10'),
            quantite_utilisee=Decimal('10'),
            # Hors nomenclature : ensure_consommation (vue et synchro)
            # retire sinon toute ligne absente de la BoM du chantier.
            hors_nomenclature=True)

    def _sync(self, op_type, payload, **op):
        payload.setdefault('intervention', self.iv.id)
        corps = {'client_op_id': str(uuid.uuid4()), 'op_type': op_type,
                 'payload': payload}
        corps.update(op)
        r = self.api.post(SYNC, {'ops': [corps]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['results'][0]

    def test_checkin_date_de_saisie(self):
        res = self._sync('intervention.checkin', {},
                         client_ts='2026-10-01T08:00:00Z')
        self.assertEqual(res['status'], 'applied', res)
        self.iv.refresh_from_db()
        self.assertEqual(
            self.iv.arrivee_site_le.isoformat(), '2026-10-01T08:00:00+00:00')

    def test_op_ancienne_en_conflit(self):
        base = self.ligne.date_modification.isoformat()
        r = self.api.post(
            f'{BASE}/{self.iv.id}/modifier-ligne-consommation/',
            {'ligne': self.ligne.id, 'quantite_utilisee': '5'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        res = self._sync('intervention.consommation_ligne',
                         {'ligne': self.ligne.id, 'quantite_utilisee': '3'},
                         base_updated_at=base)
        self.assertEqual(res['status'], 'conflit', res)
        self.assertEqual(res['valeur_serveur']['quantite_utilisee'], '5.00')
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.quantite_utilisee, Decimal('5'))

    def test_base_a_jour_appliquee(self):
        base = self.ligne.date_modification.isoformat()
        res = self._sync('intervention.consommation_ligne',
                         {'ligne': self.ligne.id, 'quantite_utilisee': '3'},
                         base_updated_at=base)
        self.assertEqual(res['status'], 'applied', res)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.quantite_utilisee, Decimal('3'))

    def test_client_ts_futur_borne(self):
        futur = (timezone.now() + timedelta(days=3)).isoformat()
        avant = timezone.now()
        res = self._sync('intervention.checkin', {}, client_ts=futur)
        self.assertEqual(res['status'], 'applied', res)
        self.iv.refresh_from_db()
        apres = timezone.now()
        self.assertGreaterEqual(self.iv.arrivee_site_le, avant)
        self.assertLessEqual(self.iv.arrivee_site_le, apres)

    def test_sans_client_ts_retrocompatible(self):
        avant = timezone.now()
        res = self._sync('intervention.checkin', {})
        self.assertEqual(res['status'], 'applied', res)
        self.iv.refresh_from_db()
        self.assertGreaterEqual(self.iv.arrivee_site_le, avant)
        res = self._sync('intervention.consommation_ligne',
                         {'ligne': self.ligne.id, 'quantite_utilisee': '3'})
        self.assertEqual(res['status'], 'applied', res)
