"""Garde-fou de cohérence inter-modules — teste l'auditeur check_data_integrity.

Vérifie (a) que des données propres ne déclenchent aucune fuite, et (b) que
l'auditeur DÉTECTE bien un lien inter-sociétés (qu'un FK seul autoriserait). C'est
le filet « la donnée doit rester connectée DANS sa société » que le founder a
demandé, et qui s'étend automatiquement aux futurs modèles porteurs de `company`.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis
from authentication.management.commands.check_data_integrity import (
    cross_company_fk_pairs,
    find_cross_company_leaks,
)

MONTH = '202606'


class TestCrossCompanyAuditor(TestCase):
    def setUp(self):
        self.a, _ = Company.objects.get_or_create(
            slug='di-a', defaults={'nom': 'Société A'})
        self.b, _ = Company.objects.get_or_create(
            slug='di-b', defaults={'nom': 'Société B'})

    def _devis(self, company, client, num):
        return Devis.objects.create(
            company=company, reference=f'DEV-{MONTH}-{num:04d}',
            client=client, statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))

    def test_discovers_known_cross_module_links(self):
        """L'introspection trouve au moins Devis.client / Devis.lead."""
        pairs = {(m._meta.label, f) for (m, f) in cross_company_fk_pairs()}
        self.assertIn(('ventes.Devis', 'client'), pairs)
        self.assertIn(('ventes.Devis', 'lead'), pairs)

    def test_clean_data_has_no_devis_leak(self):
        client_a = Client.objects.create(
            company=self.a, nom='C', prenom='A', email='c@a.com')
        self._devis(self.a, client_a, 1)
        labels = {(lbl, col) for (lbl, col, _n, _s) in find_cross_company_leaks()}
        self.assertNotIn(('ventes.Devis', 'client'), labels)

    def test_detects_cross_company_link(self):
        """Devis (A) pointant un Client (B) : le FK l'autorise, l'audit le voit."""
        client_b = Client.objects.create(
            company=self.b, nom='C', prenom='B', email='c@b.com')
        self._devis(self.a, client_b, 2)
        leaks = find_cross_company_leaks()
        labels = {(lbl, col) for (lbl, col, _n, _s) in leaks}
        self.assertIn(('ventes.Devis', 'client'), labels)
