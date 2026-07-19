"""PUB63 — Pipeline témoignage → brief créatif.

Prouve : un projet éligible (deal signé + satisfaction ≥ 4/5 + photos) AVEC
consentement PUB75 actif → brief structuré (faits vérifiés) mis en file
``CreativeBacklogItem`` ; sans consentement → BLOQUÉ (rien créé). Les lectures
cross-app (ventes / qhse / installations) sont simulées : on teste la logique du
pipeline + la garde consentement, pas les sélecteurs eux-mêmes.
"""
import datetime
from unittest import mock

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import backlog
from apps.adsengine.models import (
    ConsentRecord, CreativeAsset, CreativeBacklogItem,
)

FACTS = {
    'signed': True, 'client_id': 77, 'client_nom': 'M. Témoin',
    'puissance_kwc': 6.5, 'production_kwh': 9800.0,
    'economie_annuelle': 12000.0, 'ville': 'Marrakech',
    'reference': 'DV-2026-001',
}


def make_consent(company, client_id=77, **kw):
    defaults = dict(
        company=company, client_id=client_id, client_nom='M. Témoin',
        portee_photo=True, portee_temoignage=True,
        date_consentement=datetime.date(2026, 1, 1))
    defaults.update(kw)
    return ConsentRecord.objects.create(**defaults)


def patch_selectors(*, facts=FACTS, satisfaction=4.5, has_photos=True,
                    ville='Marrakech', avant=1, apres=1):
    """Contexte de patch des trois sélecteurs cross-app."""
    class _QS:
        def __init__(self, n):
            self._n = n

        def count(self):
            return self._n

        def exists(self):
            return self._n > 0

    def _photos(company, chantier_id, *, phase=None):
        if phase == 'avant':
            return _QS(avant)
        if phase == 'apres':
            return _QS(apres)
        return _QS(avant + apres)

    return [
        mock.patch('apps.ventes.selectors.faits_temoignage_devis',
                   return_value=facts),
        mock.patch('apps.qhse.selectors.satisfaction_moyenne',
                   return_value=satisfaction),
        mock.patch('apps.installations.selectors.chantier_a_photos',
                   return_value=has_photos),
        mock.patch('apps.installations.selectors.chantier_photos',
                   side_effect=_photos),
        mock.patch('apps.installations.selectors.chantier_ville',
                   return_value=ville),
    ]


class TestimonialBriefTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Témoin Co', slug='temoin-co')

    def _run(self, **kw):
        patches = patch_selectors(**kw)
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        return backlog.queue_testimonial_brief(
            self.company, devis_id=1, chantier_id=1)

    def test_eligible_with_consent_queues_brief(self):
        make_consent(self.company)
        res = self._run()
        self.assertTrue(res['queued'], res)
        self.assertIsNone(res['blocked_reason'])
        # Un item de backlog EN FILE, un asset PENDING « client réel ».
        item = res['backlog_item']
        self.assertEqual(item.status, CreativeBacklogItem.Statut.EN_FILE)
        asset = res['asset']
        self.assertTrue(asset.depicts_real_client)
        self.assertEqual(asset.source_lane, 'temoignage')
        self.assertFalse(asset.is_policy_passed)  # PENDING
        self.assertIsNotNone(asset.consent_id)
        # Brief ancré sur des faits vérifiés (ville + kWc dans l'accroche).
        self.assertIn('Marrakech', res['brief']['hook_text'])
        self.assertTrue(res['brief']['faits_verifies'])
        self.assertTrue(res['brief']['avant_apres_disponible'])
        self.assertEqual(CreativeBacklogItem.objects.count(), 1)

    def test_blocked_without_consent(self):
        res = self._run()  # aucun ConsentRecord créé
        self.assertFalse(res['queued'])
        self.assertEqual(res['blocked_reason'], 'consentement_manquant')
        self.assertEqual(CreativeAsset.objects.count(), 0)
        self.assertEqual(CreativeBacklogItem.objects.count(), 0)

    def test_blocked_when_deal_not_signed(self):
        make_consent(self.company)
        res = self._run(facts={**FACTS, 'signed': False})
        self.assertFalse(res['queued'])
        self.assertEqual(res['blocked_reason'], 'deal_non_signe')
        self.assertEqual(CreativeBacklogItem.objects.count(), 0)

    def test_blocked_on_low_satisfaction(self):
        make_consent(self.company)
        res = self._run(satisfaction=3.0)
        self.assertFalse(res['queued'])
        self.assertEqual(res['blocked_reason'], 'satisfaction_insuffisante')

    def test_blocked_without_photos(self):
        make_consent(self.company)
        res = self._run(has_photos=False)
        self.assertFalse(res['queued'])
        self.assertEqual(res['blocked_reason'], 'pas_de_photos')

    def test_revoked_consent_blocks(self):
        c = make_consent(self.company)
        c.revoked_at = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
        c.save(update_fields=['revoked_at'])
        res = self._run()
        self.assertFalse(res['queued'])
        self.assertEqual(res['blocked_reason'], 'consentement_manquant')

    def test_scope_photo_only_consent_blocks(self):
        # Un consentement PHOTO seul ne couvre pas le témoignage (nom/citation).
        make_consent(self.company, portee_temoignage=False)
        res = self._run()
        self.assertFalse(res['queued'])
        self.assertEqual(res['blocked_reason'], 'consentement_manquant')
