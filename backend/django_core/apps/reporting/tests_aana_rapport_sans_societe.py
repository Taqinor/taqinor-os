"""AANA27 (C-AANA-009) — un rapport planifié SANS société n'est ni rendu ni
créé.

Scénario R10 : ``SavedReport(company=None, target_kind='stock')``. Avant le
correctif : ``_company_filter`` renvoyait ``{}`` et le rendu listait les
produits de TOUTES les sociétés (258 lignes, 2 sociétés) — e-mail et lien
public compris.

Données RÉELLES en base (aucun mock). Rétablir ``{}`` rougit ce test.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.reporting import scheduled_reports
from apps.reporting.models import SavedReport
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()


class TestRapportSansSociete(TestCase):
    def setUp(self):
        for slug in ('aana27-a', 'aana27-b'):
            company = Company.objects.get_or_create(
                slug=slug, defaults={'nom': slug.upper()})[0]
            Produit.objects.create(
                company=company, nom=f'Produit {slug}', sku=f'{slug}-P',
                prix_vente=Decimal('10'), quantite_stock=1)

    def test_refuse(self):
        rapport = SavedReport.objects.create(
            company=None, name='Orphelin',
            target_kind=SavedReport.TargetKind.STOCK)

        # Aucun rendu (ni e-mail, ni lien public, ni xlsx historique).
        self.assertEqual(scheduled_reports.rendre_rapport(rapport),
                         (None, None, None, None))
        self.assertEqual(scheduled_reports.render_report_xlsx(rapport),
                         (None, None))
        # Le moteur de rendu lui-même ne voit aucune ligne.
        _entetes, lignes = scheduled_reports.render_stock(rapport)
        self.assertEqual(lignes, [])

        # Création refusée (400) pour un appelant sans société.
        superuser = User.objects.create_superuser(
            username='aana27_root', password='x', email='root@example.com')
        self.assertIsNone(superuser.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(superuser)}')
        avant = SavedReport.objects.count()
        resp = api.post('/api/django/reporting/saved-reports/', {
            'name': 'Sans société', 'target_kind': 'stock',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('company', resp.data)
        self.assertEqual(SavedReport.objects.count(), avant)
