"""AACQ25 — L'état « connecteur Odoo » de l'audit et de l'écran Connexion est
l'état RÉEL du connecteur (``odoo_client.is_configured``) : sans
``ODOO_COMPANY_ID`` il est inactif (remédiation qui nomme la variable) ; avec,
il n'est actif que pour la société propriétaire.
"""
import os
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from apps.adsengine import audit

ODOO_ENV = {'ODOO_URL': 'https://x.odoo.com', 'ODOO_DB': 'x',
            'ODOO_USERNAME': 'x', 'ODOO_API_KEY': 'x'}


def _odoo_item(section):
    return [i for i in section['items'] if 'odoo' in i.lower()]


class AuditOdooTests(TestCase):
    def setUp(self):
        self.proprietaire = Company.objects.create(
            nom='Proprio', slug='aacq25-proprio')
        self.autre = Company.objects.create(nom='Autre', slug='aacq25-autre')

    def _loop(self):
        loops = {lp['id']: lp for lp in audit.pending_activation_loops()}
        return loops['odoo_connector']

    def test_sans_company_id_inactif(self):
        with mock.patch.dict(os.environ, ODOO_ENV):
            os.environ.pop('ODOO_COMPANY_ID', None)  # restauré par patch.dict
            loop = self._loop()
            self.assertFalse(loop['actif'])
            self.assertIn('ODOO_COMPANY_ID', loop['cles_requises'])
            self.assertIn('poser ODOO_COMPANY_ID = id de la société '
                          'propriétaire', loop['remediation_fr'])
            self.assertTrue(_odoo_item(
                audit._audit_tracking(self.proprietaire)))

    def test_actif_pour_la_seule_societe(self):
        with mock.patch.dict(os.environ, {
                **ODOO_ENV, 'ODOO_COMPANY_ID': str(self.proprietaire.pk)}):
            self.assertTrue(self._loop()['actif'])
            self.assertFalse(_odoo_item(
                audit._audit_tracking(self.proprietaire)))
            self.assertTrue(_odoo_item(audit._audit_tracking(self.autre)))
