"""ADEV47 (C-ADEV-013) — l'expiration nocturne des devis est CONDITIONNELLE :
un devis accepté entre la lecture et l'écriture de la boucle reste ACCEPTÉ,
sans chatter « expiré » ni événement d'expiration ; un devis non accepté
expire comme avant.

La course est rendue déterministe : le point d'injection déclaré est
``apps.ventes.utils.expiry.is_expired`` (appelé par la boucle APRÈS la
sélection et AVANT l'écriture) — l'enveloppe commet l'acceptation puis rend
le verdict réel. Le reste (boucle, `is_expired`, chatter, événement) est réel.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_xfac_adev47_expiration_conditionnelle"
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone


class ExpirationConditionnelleTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        from authentication.models import Company
        self.company = Company.objects.create(nom='ADEV47', slug='adev47-co')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV47',
            email='adev47@example.invalid')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ADEV47-1', client=client,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            date_envoi=timezone.now() - timedelta(days=90))
        Devis.objects.filter(pk=self.devis.pk).update(
            date_validite=timezone.now().date() - timedelta(days=30))

    def _expirer(self):
        from apps.ventes.domain.recouvrement import expire_stale_devis
        return expire_stale_devis()

    def test_accepte_pendant_boucle_reste_accepte(self):
        from apps.ventes.models import Devis
        from apps.ventes.utils import expiry
        reel = expiry.is_expired
        maintenant = timezone.now().date()

        def _course(devis, today=None):
            verdict = reel(devis, today=today)
            # Acceptation committée ENTRE la sélection et l'écriture.
            Devis.objects.filter(pk=devis.pk).update(
                statut=Devis.Statut.ACCEPTE, date_acceptation=maintenant)
            return verdict

        from core.events import devis_expired
        recus = []

        def _ecoute(sender, **kwargs):
            recus.append(kwargs.get('devis'))
        devis_expired.connect(_ecoute)
        self.addCleanup(devis_expired.disconnect, _ecoute)
        with patch.object(expiry, 'is_expired', side_effect=_course):
            resultat = self._expirer()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertIsNotNone(self.devis.date_acceptation)
        self.assertEqual(resultat['expired'], 0)
        self.assertEqual(recus, [])

    def test_envoye_expire(self):
        from apps.ventes.models import Devis
        resultat = self._expirer()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.EXPIRE)
        self.assertEqual(resultat['expired'], 1)
