# -*- coding: utf-8 -*-
"""ACAL294 — garde de PARITÉ : chaque cible de champs personnalisés déclarée
par un manifeste (``PLATFORM['customfield_models']``) porte un champ CONCRET
``custom_data``.

LE CONSTAT (C-ACAL-146) : ``apps/calepinage/platform.py`` déclarait
``'calepinage'`` cible de champs personnalisés alors que le modèle n'avait
pas ``custom_data`` — la définition se créait, la saisie n'avait nulle part
où vivre, et le contrôle d'un renommage de code levait ``FieldError`` (500).
"""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.customfields import registry
from core import platform as core_platform


class CiblesOntCustomDataTest(SimpleTestCase):

    def test_chaque_cible_declaree_porte_un_champ_custom_data(self):
        manquantes, cibles = [], []
        for nom, manifeste in core_platform.collect_platform_manifests() \
                .items():
            for cle in manifeste.get('customfield_models') or ():
                modele = registry.get_model(cle)
                cibles.append(cle)
                champs = ({champ.name for champ in modele._meta.concrete_fields}
                          if modele is not None else set())
                if 'custom_data' not in champs:
                    manquantes.append('%s → %s' % (nom, cle))
        self.assertIn('calepinage', cibles)
        self.assertEqual(manquantes, [],
                         'Cible de champs personnalisés SANS colonne '
                         'custom_data : %s' % ', '.join(manquantes))
