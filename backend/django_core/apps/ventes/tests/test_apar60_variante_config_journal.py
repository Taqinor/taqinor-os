"""APAR60 (C-APAR-039, volet ventes) — ``PUT /ventes/devis/variante-config/``
journalise ``variante_pct`` dans ``SettingsAuditLog`` (avant/après,
utilisateur), comme l'écran Profil ; une valeur refusée n'écrit rien.

Test-du-test : retirer l'appel ``log_change`` ⇒
``test_changement_journalise`` échoue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.parametres.models import CompanyProfile, SettingsAuditLog
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ventes/devis/variante-config/'


class VarianteConfigJournalTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR60', slug='apar60-co')
        profil = CompanyProfile.get(company=self.company)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            variante_pct=Decimal('10'))
        self.admin = User.objects.create_user(
            username='apar60_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def _journal(self):
        return SettingsAuditLog.objects.filter(
            company=self.company, field='variante_pct')

    def test_changement_journalise(self):
        resp = self.api.put(URL, {'variante_pct': '15'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self._journal().count(), 1)
        ligne = self._journal().get()
        self.assertEqual(Decimal(ligne.old_value), Decimal('10'))
        self.assertEqual(Decimal(ligne.new_value), Decimal('15'))
        self.assertEqual(ligne.user_id, self.admin.pk)
        # CLAUSE PERSISTANCE — profil relu.
        self.assertEqual(CompanyProfile.get(company=self.company).variante_pct,
                         Decimal('15'))

    def test_valeur_refusee_aucune_ligne(self):
        resp = self.api.put(URL, {'variante_pct': '150'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(self._journal().exists())
