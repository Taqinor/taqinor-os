"""Tests YDOCF3 — accepter une variante de devis effondre ses sœurs
(version_parent=root, is_active=True) avec le motif « variante non retenue »,
et n'émet qu'un seul devis_accepted. Un devis sans variante reste inchangé."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes import services as ventes_services
from apps.ventes.models import Devis
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ydocf3-co', nom='YDOCF3 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestVariantCollapseOnAcceptance(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ydocf3_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='F3',
            email='ydocf3@example.com', telephone='+212600000003')

    def _devis(self, num, version_parent=None, statut=Devis.Statut.ENVOYE):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{9100 + num}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            version_parent=version_parent, is_active=True)

    def test_accepting_variant_collapses_root_and_siblings(self):
        root = self._devis(1)
        variant_b = self._devis(2, version_parent=root)
        variant_c = self._devis(3, version_parent=root)

        received = []

        def _listener(sender, devis, user, ancien_statut, **kwargs):
            received.append(devis.id)
        devis_accepted.connect(_listener, dispatch_uid='test_ydocf3_listener')
        try:
            ventes_services.accept_devis(
                devis=variant_b, user=self.user, nom='Client Test')
        finally:
            devis_accepted.disconnect(dispatch_uid='test_ydocf3_listener')

        variant_b.refresh_from_db()
        root.refresh_from_db()
        variant_c.refresh_from_db()

        self.assertEqual(variant_b.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(root.statut, Devis.Statut.REFUSE)
        self.assertEqual(root.motif_refus, 'variante non retenue')
        self.assertFalse(root.is_active)
        self.assertEqual(variant_c.statut, Devis.Statut.REFUSE)
        self.assertEqual(variant_c.motif_refus, 'variante non retenue')
        self.assertFalse(variant_c.is_active)
        # Exactly one devis_accepted for the whole group.
        self.assertEqual(received, [variant_b.id])

    def test_devis_without_variant_unaffected(self):
        devis = self._devis(4)
        other_group_root = self._devis(5)
        self._devis(6, version_parent=other_group_root)

        ventes_services.accept_devis(
            devis=devis, user=self.user, nom='Client Test')
        devis.refresh_from_db()
        other_group_root.refresh_from_db()

        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        # Another group's devis must never be touched.
        self.assertEqual(other_group_root.statut, Devis.Statut.ENVOYE)
        self.assertTrue(other_group_root.is_active)

    def test_already_terminal_sibling_not_reopened(self):
        """A sibling that is already refused/expired (is_active=False) is not
        touched again — the collapse only targets live, active siblings."""
        root = self._devis(7)
        variant_b = self._devis(8, version_parent=root)
        variant_c = self._devis(9, version_parent=root)
        variant_c.statut = Devis.Statut.REFUSE
        variant_c.motif_refus = 'refus client'
        variant_c.is_active = False
        variant_c.save()

        ventes_services.accept_devis(
            devis=variant_b, user=self.user, nom='Client Test')
        variant_c.refresh_from_db()
        self.assertEqual(variant_c.motif_refus, 'refus client')
