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
from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
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

    def test_code_parametres_et_non_nom_de_role(self):
        """ADRG11 (D-ADRG-5) — le PUT suit ``parametres_modifier``, jamais un
        nom de rôle : un rôle personnalisé qui porte le code écrit ; le
        Commercial responsable livré (sans le code) reçoit 403, rien d'écrit.
        Mutant : rétablir le test ``role_nom in (…)`` ⇒ échec."""
        gestion = Role.objects.create(
            company=self.company, nom='Gestion paramètres',
            permissions=['parametres_modifier', 'ventes_voir'])
        resp_role = Role.objects.create(
            company=self.company, nom='Commercial responsable',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Commercial responsable']))
        parametreur = User.objects.create_user(
            username='adrg11_param', password='x', company=self.company,
            role=gestion, role_legacy='normal')
        commercial_resp = User.objects.create_user(
            username='adrg11_comresp', password='x', company=self.company,
            role=resp_role, role_legacy='responsable')
        api = APIClient()
        api.force_authenticate(commercial_resp)
        self.assertEqual(
            api.put(URL, {'variante_pct': '30'}, format='json').status_code, 403)
        api.force_authenticate(parametreur)
        resp = api.put(URL, {'variante_pct': '15'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # CLAUSE PERSISTANCE — relu par GET : seule la valeur autorisée.
        self.assertEqual(Decimal(api.get(URL).data['variante_pct']), Decimal('15'))
