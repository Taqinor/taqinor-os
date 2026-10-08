"""ACHT15 (C-ACHT-014) — une demande d'achat qui quitte le brouillon sort de
l'archive (`soumettre` remet `archivee=False`, `date_archivage=None`), et
toute modification de ligne touche `DemandeAchat.date_modification` pour que
la purge NTP2P35 n'archive pas une demande activement éditée.

Rejoue CACH-9 : DA archivée puis soumise → absente de la liste active.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_da_archivee"
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import DemandeAchat, DemandeAchatLigne
from apps.installations.tasks import purger_demandes_achat_brouillon_task

User = get_user_model()
BASE = '/api/django/installations'


class DaArchiveeTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht15', defaults={'nom': 'Co ACHT15'})
        self.user = User.objects.create_user(
            username='resp-acht15', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self._n = 0

    def _da(self):
        self._n += 1
        da = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-ACHT15-{self._n}',
            objet='Archive', created_by=self.user)
        ligne = DemandeAchatLigne.objects.create(
            demande=da, designation='Article', quantite=Decimal('1'),
            prix_estime=Decimal('10'))
        return da, ligne

    def test_soumettre_desarchive(self):
        da, _ = self._da()
        DemandeAchat.objects.filter(pk=da.pk).update(
            archivee=True, date_archivage=timezone.now())
        r = self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(r.status_code, 200, r.data)
        da.refresh_from_db()
        self.assertFalse(da.archivee)
        self.assertIsNone(da.date_archivage)
        r = self.api.get(f'{BASE}/demandes-achat/', {'statut': 'soumise'})
        self.assertEqual(r.status_code, 200)
        lignes = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertIn(da.pk, [d['id'] for d in lignes])

    def test_ligne_modifiee_retarde_la_purge(self):
        da, ligne = self._da()
        ancien, _ = self._da()
        cent_jours = timezone.now() - timedelta(days=100)
        DemandeAchat.objects.filter(pk__in=[da.pk, ancien.pk]).update(
            date_modification=cent_jours)
        r = self.api.patch(f'{BASE}/demandes-achat-lignes/{ligne.id}/',
                           {'quantite': '3'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        purger_demandes_achat_brouillon_task()
        da.refresh_from_db()
        ancien.refresh_from_db()
        self.assertFalse(da.archivee)
        # Témoin : la DA vraiment abandonnée est bien archivée.
        self.assertTrue(ancien.archivee)
