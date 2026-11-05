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

    def _creee_il_y_a(self, delta):
        Intervention.objects.filter(pk=self.iv.pk).update(
            date_creation=timezone.now() - delta)

    def test_checkin_date_de_saisie(self):
        # ACHT130 — réaligné : saisie relative, après la création (J-2).
        self._creee_il_y_a(timedelta(days=2))
        saisie = (timezone.now() - timedelta(days=1)).replace(microsecond=0)
        res = self._sync('intervention.checkin', {},
                         client_ts=saisie.isoformat())
        self.assertEqual(res['status'], 'applied', res)
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.arrivee_site_le, saisie)

    def test_client_ts_invraisemblable_heure_de_synchro(self):
        """ACHT130 (C-ACHT-VER4-020) — horloge −1 an, ou retour antérieur au
        check-in : heure de synchro + mention ; témoin H-3 → H = 180 min."""
        from apps.installations.field_capture import crew_time
        from apps.installations.models import InterventionActivity
        self._creee_il_y_a(timedelta(days=2))
        maintenant = timezone.now()
        # (a) check-in à J-365 → ramené.
        res = self._sync('intervention.checkin', {}, client_ts=(
            maintenant - timedelta(days=365)).isoformat())
        self.assertEqual(res['status'], 'applied', res)
        self.iv.refresh_from_db()
        self.assertGreaterEqual(self.iv.arrivee_site_le, maintenant)
        self.assertTrue(InterventionActivity.objects.filter(
            intervention=self.iv, body__contains='invraisemblable').exists())
        # (b) check-in H-1, retour H-3 → retour ramené, durée ≥ 0.
        self._sync('intervention.checkin', {}, client_ts=(
            maintenant - timedelta(hours=1)).isoformat())
        res = self._sync('intervention.retour', {}, client_ts=(
            maintenant - timedelta(hours=3)).isoformat())
        self.assertEqual(res['status'], 'applied', res)
        self.iv.refresh_from_db()
        self.assertGreaterEqual(self.iv.retour_depot_le, maintenant)
        self.assertGreaterEqual(crew_time(self.iv)['duree_sur_site_min'], 0)
        # Témoin : check-in H-3, retour H → 180 min, sans mention.
        self._sync('intervention.checkin', {}, client_ts=(
            maintenant - timedelta(hours=3)).isoformat())
        self._sync('intervention.retour', {}, client_ts=maintenant.isoformat())
        self.iv.refresh_from_db()
        self.assertEqual(crew_time(self.iv)['duree_sur_site_min'], 180)
        self.assertEqual(InterventionActivity.objects.filter(
            intervention=self.iv, body__contains='invraisemblable').count(), 2)

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
