"""NTADM45 — Test e2e : export puis import d'un package de configuration.

Parcours complet : export → modification d'un libellé sur la cible → diff
détecte exactement la modif → application → idempotence (re-diff vide).
Aucune donnée client dans le package (vérifié par assertion).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from ..config_package_service import (
    appliquer_import, exporter_config, previsualiser_import)

User = get_user_model()


class ConfigPackageE2ETests(TestCase):
    def setUp(self):
        self.source = Company.objects.create(nom='Source')
        self.cible = Company.objects.create(nom='Cible')
        self.admin = User.objects.create_user(
            username='e2e_admin', password='pw', company=self.source,
            role_legacy='admin')

    def test_export_diff_appliquer_idempotent(self):
        from apps.parametres.models_messages import MessageTemplate

        # 1. Config source : un template avec un libellé donné.
        MessageTemplate.objects.create(
            company=self.source, cle='facture', corps_fr='Bonjour, votre facture.')
        package = exporter_config(self.source, nom='E2E', user=self.admin)

        # Aucune donnée client (leads/devis/clients) dans le package.
        self.assertNotIn('leads', package.contenu)
        self.assertNotIn('clients', package.contenu)
        self.assertIn('message_templates', package.contenu)

        # 2. Cible a le même template mais un libellé DIFFÉRENT.
        MessageTemplate.objects.create(
            company=self.cible, cle='facture', corps_fr='Texte différent.')

        # 3. Diff détecte exactement la modification.
        diff = previsualiser_import(self.cible, package.contenu)
        self.assertEqual(len(diff['message_templates']['modifications']), 1)

        # 4. Application.
        appliquer_import(self.cible, package.contenu, user=self.admin)
        tpl = MessageTemplate.objects.get(company=self.cible, cle='facture')
        self.assertEqual(tpl.corps_fr, 'Bonjour, votre facture.')

        # 5. Idempotence : re-diff vide.
        diff2 = previsualiser_import(self.cible, package.contenu)
        self.assertEqual(len(diff2['message_templates']['modifications']), 0)
        self.assertEqual(len(diff2['message_templates']['ajouts']), 0)
