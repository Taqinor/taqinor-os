"""CADV8 (C-CADV-008) — la relance cadencée des devis (QJ4) saute tout devis
dont le lead est « ne plus contacter » (loi 09-08 art. 9, ACRM17) : ni
notification, ni brouillon wa.me, ni ligne ``DevisNudgeLog``. L'opposition
levée, le palier dû part au passage suivant.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_facture_relances_devis_opposition"
"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.crm import stages

User = get_user_model()


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
    DEVIS_NUDGE_DAYS=[2, 5, 10])
class NudgeOppositionTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client, Lead
        from apps.ventes.models import Devis
        from authentication.models import Company
        self.company = Company.objects.create(nom='CADV8', slug='cadv8-co')
        self.vendeur = User.objects.create_user(
            username='cadv8_vendeur', password='x', role_legacy='responsable',
            company=self.company, email='vendeur-cadv8@example.invalid')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='CADV8',
            email='cadv8@example.invalid')
        self.oppose = Lead.objects.create(
            company=self.company, nom='Oppose', stage=stages.QUOTE_SENT,
            telephone='+212612340008', ne_plus_contacter=True)
        normal = Lead.objects.create(
            company=self.company, nom='Normal', stage=stages.QUOTE_SENT,
            telephone='+212612340009')
        # Midi local de J-3 (jours calendaires à Casablanca, cf. QJ4).
        envoi = datetime.combine(
            timezone.localdate() - timedelta(days=3), time(12, 0),
            tzinfo=timezone.get_current_timezone())
        self.devis_oppose, self.devis_normal = (
            Devis.objects.create(
                company=self.company, reference=f'DEV-CADV8-{n}',
                client=client, lead=lead, statut=Devis.Statut.ENVOYE,
                taux_tva=Decimal('20'), date_envoi=envoi,
                created_by=self.vendeur)
            for n, lead in (('O', self.oppose), ('N', normal)))

    def test_lead_oppose_ne_recoit_aucune_relance(self):
        from apps.ventes.models import DevisNudgeLog
        from apps.ventes.services import send_devis_followup_nudges

        self.assertEqual(send_devis_followup_nudges(), 1)
        self.assertFalse(DevisNudgeLog.objects.filter(
            devis=self.devis_oppose).exists())
        self.assertEqual(DevisNudgeLog.objects.filter(
            devis=self.devis_normal).count(), 1)

        # Opposition levée ⇒ le palier dû part au passage suivant.
        self.oppose.ne_plus_contacter = False
        self.oppose.save(update_fields=['ne_plus_contacter'])
        self.assertEqual(send_devis_followup_nudges(), 1)
        self.assertEqual(DevisNudgeLog.objects.filter(
            devis=self.devis_oppose).count(), 1)
