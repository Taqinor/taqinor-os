"""QJR660 (décision fondateur 01/10/2026) — une correction sur place d'un
devis envoyé GARDE la cadence d'origine des relances ventes (j+2 / j+5 /
j+10) : elle reste ancrée sur ``date_envoi`` (premier envoi), jamais sur la
date de la correction (``etude_params.resync_apres_envoi``).

Scénario : envoyé à J-2 (midi local), corrigé AUJOURD'HUI par un PATCH (la
trace QJR518 pose le marqueur « Document mis à jour le … ») ; le passage des
relances du jour déclenche bien le niveau 0, et ``date_envoi`` est intacte.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_nudges_apres_correction"
"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisNudgeLog, LigneDevis
from apps.ventes.services import send_devis_followup_nudges
from authentication.models import Company

User = get_user_model()
CONSOLE = 'django.core.mail.backends.console.EmailBackend'


@override_settings(EMAIL_BACKEND=CONSOLE, DEVIS_NUDGE_DAYS=[2, 5, 10])
class NudgesApresCorrectionTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR660 Co', slug='qjr660-co')
        self.user = User.objects.create_user(
            username='qjr660_resp', password='x', role_legacy='responsable',
            company=self.company, email='vendeur@qjr660.ma')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Client QJR660',
            email='client@qjr660.ma')
        produit = Produit.objects.create(
            company=self.company, nom='Panneau QJR660', sku='QJR660-PV',
            prix_vente=Decimal('1000'), quantite_stock=10)
        jour_envoi = timezone.localdate() - timedelta(days=2)
        self.envoi = datetime.combine(
            jour_envoi, time(12, 0), tzinfo=timezone.get_current_timezone())
        self.devis = Devis.objects.create(
            company=self.company,
            reference=f'DEV-{timezone.now():%Y%m}-6601',
            client=client, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), date_envoi=self.envoi,
            created_by=self.user)
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation=produit.nom,
            quantite=Decimal('2'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), ordre=0)

    def _corriger(self):
        r = self.api.patch(f'/api/django/ventes/devis/{self.devis.id}/',
                           {'note': 'Pose en mars.'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.devis.refresh_from_db()

    def test_la_correction_ne_reecrit_pas_date_envoi(self):
        self._corriger()
        # Anti-faux-vert : c'est bien une correction tracée (marqueur QJR518).
        self.assertIsNotNone(
            (self.devis.etude_params or {}).get('resync_apres_envoi'))
        self.assertEqual(self.devis.date_envoi, self.envoi)

    def test_le_niveau_0_part_a_j2_du_PREMIER_envoi(self):
        self._corriger()
        self.assertEqual(send_devis_followup_nudges(), 1)
        log = DevisNudgeLog.objects.get(devis=self.devis)
        self.assertEqual((log.niveau, log.jours), (0, 2))
