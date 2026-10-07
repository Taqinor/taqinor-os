# -*- coding: utf-8 -*-
"""ACAL301 — ``anonymiser_lead`` émet ENFIN ``core.events.lead_erased``.

Le signal était déclaré et catalogué (PUB100) mais personne ne l'émettait :
l'abonné adsengine attendait en vain, et la rétention des prospects (qui ne
passe PAS par ``core.dsr.effacer``) n'avait aucun moyen de prévenir les apps
qui référencent le lead. Le point d'émission UNIQUE est ``anonymiser_lead``
(DSR et rétention), APRÈS validation, avec le payload catalogué.
"""
from __future__ import annotations

from django.test import TestCase

from apps.crm.dsr_provider import anonymiser_lead
from apps.crm.models import Lead
from authentication.models import Company
from core import event_catalog
from core.events import lead_erased


class LeadErasedEmisTest(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ACAL301', slug='acal301')
        self.recus = []

        def recepteur(sender, **kwargs):
            self.recus.append(kwargs)

        self.recepteur = recepteur
        lead_erased.connect(recepteur, dispatch_uid='acal301_test')
        self.addCleanup(lead_erased.disconnect, dispatch_uid='acal301_test')

    def test_anonymiser_lead_emet_lead_erased_avec_payload_catalogue(self):
        lead = Lead.objects.create(company=self.company, nom='Dupont',
                                   telephone='0612345678')
        lead.refresh_from_db()
        cle_telephone = lead.phone_normalise
        self.assertTrue(cle_telephone)

        with self.captureOnCommitCallbacks(execute=True):
            anonymiser_lead(self.company, lead, motif='essai ACAL301')
            # Rien n'est émis AVANT la validation de la transaction.
            self.assertEqual(self.recus, [])

        self.assertEqual(len(self.recus), 1)
        recu = {cle: valeur for cle, valeur in self.recus[0].items()
                if cle != 'signal'}
        self.assertEqual(sorted(recu),
                         sorted(event_catalog.entry('lead_erased')['payload']))
        self.assertEqual(recu['company'], self.company)
        self.assertEqual(recu['crm_lead_id'], lead.pk)
        # La clé téléphone est celle d'AVANT le scrub (les abonnés joignent
        # leurs miroirs par elle).
        self.assertEqual(recu['phone_key'], cle_telephone)
        lead.refresh_from_db()
        self.assertEqual(lead.phone_normalise, '')
