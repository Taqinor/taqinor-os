"""ACRM29 (C-ACRM-024) — « Ma file » lit l'échéance EFFECTIVE d'un devis
(``apps.ventes.selectors.date_validite_effective``), celle du PDF.

Sonde V_VA LSEL-4 : un devis ``envoye`` SANS ``date_validite`` dont
l'échéance effective (création + ``quote_validity_days``) tombe dans 3 jours
n'apparaissait pas (``present False``). Un devis expiré depuis longtemps mais
toujours ``envoye`` reste présent (voulu par la docstring).

Aucun mock : devis réels, réglage société réel.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core.dates import aujourd_hui_local

from apps.crm.models import Lead
from apps.crm.selectors import devis_expirant_bientot
from apps.ventes.models import Devis
from apps.ventes.selectors import date_validite_effective

User = get_user_model()


class DevisExpirantEffectifTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM29 Solaire', slug='acrm29-expirant')
        self.user = User.objects.create_user(
            username='acrm29-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Expirant', owner=self.user)
        self.today = aujourd_hui_local()

    def _devis(self, reference, **champs):
        devis = Devis.objects.create(
            company=self.company, reference=reference, lead=self.lead,
            statut='envoye', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user, **champs)
        return devis

    def test_date_nulle_prise_par_date_effective(self):
        devis = self._devis('DEV-ACRM29-0001')
        # Échéance effective dans 3 jours : on recule la création d'autant.
        validite = (date_validite_effective(devis)
                    - devis.date_creation.date()).days
        Devis.objects.filter(pk=devis.pk).update(
            date_validite=None,
            date_creation=timezone.now() - datetime.timedelta(
                days=validite - 3))
        devis.refresh_from_db()
        attendue = date_validite_effective(devis)
        self.assertIsNotNone(attendue)
        lignes = {d['devis_id']: d for d in devis_expirant_bientot(
            self.company, self.user, dans_jours=7, today=self.today)}
        self.assertIn(devis.pk, lignes)
        self.assertEqual(lignes[devis.pk]['date_expiration'], attendue)

    def test_expire_toujours_envoye_present(self):
        devis = self._devis(
            'DEV-ACRM29-0002',
            date_validite=self.today - datetime.timedelta(days=400))
        ids = {d['devis_id'] for d in devis_expirant_bientot(
            self.company, self.user, dans_jours=7, today=self.today)}
        self.assertIn(devis.pk, ids)
