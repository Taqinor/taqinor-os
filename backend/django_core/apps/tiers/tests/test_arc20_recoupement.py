"""ARC20 — Recoupement « qui est ce tiers ? » : selectors + endpoint doublons.

On prouve :
  - ``find_by_ice`` / ``find_by_email`` sont company-scopés et insensibles à la
    casse ;
  - ``find_duplicates`` détecte le MÊME ICE/email porté par plusieurs fiches
    Tiers (doublon inter-référentiel), en lecture seule, company-scopé ;
  - l'endpoint ``/tiers/tiers/doublons/`` est réservé aux admins et company-scopé.
"""
from testkit.base import TenantAPITestCase

from apps.tiers import selectors
from apps.tiers.models import Tiers


class Arc20SelectorTests(TenantAPITestCase):
    def test_find_by_ice_company_scoped_case_insensitive(self):
        Tiers.objects.create(company=self.company, nom='A', ice='ICE-1')
        Tiers.objects.create(company=self.other_company, nom='B', ice='ICE-1')
        found = selectors.find_by_ice(self.company, 'ice-1')
        self.assertEqual(found.count(), 1)
        self.assertEqual(found.first().company_id, self.company.id)

    def test_find_by_email_empty_returns_none(self):
        self.assertEqual(selectors.find_by_email(self.company, '').count(), 0)

    def test_find_duplicates_detects_cross_referential(self):
        # Deux fiches Tiers différentes partagent le même ICE → doublon.
        Tiers.objects.create(company=self.company, nom='Fournisseur X',
                             ice='ICE-DUP', is_fournisseur=True)
        Tiers.objects.create(company=self.company, nom='Partenaire X',
                             ice='ICE-DUP', is_partenaire=True)
        # Un tiers isolé (email unique) ne forme pas de cluster.
        Tiers.objects.create(company=self.company, nom='Seul',
                             email='seul@example.ma')
        clusters = selectors.find_duplicates(self.company)
        self.assertEqual(len(clusters), 1)
        c = clusters[0]
        self.assertEqual(c['cle'], 'ice')
        self.assertEqual(c['valeur'], 'ice-dup')
        self.assertEqual(len(c['tiers']), 2)

    def test_find_duplicates_is_company_scoped(self):
        # Même ICE dans DEUX sociétés → pas un cluster commun.
        Tiers.objects.create(company=self.company, nom='A', ice='SHARED')
        Tiers.objects.create(company=self.other_company, nom='B', ice='SHARED')
        self.assertEqual(len(selectors.find_duplicates(self.company)), 0)


class Arc20EndpointTests(TenantAPITestCase):
    URL = '/api/django/tiers/tiers/doublons/'

    def test_admin_gets_report(self):
        Tiers.objects.create(company=self.company, nom='F', ice='E1',
                             is_fournisseur=True)
        Tiers.objects.create(company=self.company, nom='P', ice='E1',
                             is_partenaire=True)
        admin = self.client_as(role='admin')
        r = admin.get(self.URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(len(r.data['clusters']), 1)

    def test_non_admin_forbidden(self):
        # Un utilisateur normal (rôle par défaut) n'accède pas au rapport admin.
        r = self.client_as().get(self.URL)
        self.assertIn(r.status_code, (401, 403))

    def test_report_is_company_scoped(self):
        Tiers.objects.create(company=self.other_company, nom='X', ice='OTHER')
        Tiers.objects.create(company=self.other_company, nom='Y', ice='OTHER')
        admin = self.client_as(role='admin')
        r = admin.get(self.URL)
        self.assertEqual(r.status_code, 200)
        # Les doublons de l'AUTRE société ne fuient jamais.
        self.assertEqual(r.data['count'], 0)
