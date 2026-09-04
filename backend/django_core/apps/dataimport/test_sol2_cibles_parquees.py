"""SOL2(b) — la cible d'import `eleves_education` suit l'édition.

`FIELD_MAPS` déclare littéralement le mapping d'en-têtes de la cible ici, dans
`dataimport`, alors que l'ÉCRITURE est déléguée à
`apps.education.services.creer_eleve_import`. En édition solaire `apps.education`
n'est pas chargée : sans retrait, `target in TARGETS` resterait vrai et le
commit lèverait un `ImportError` au lieu du refus propre « cible inconnue ».

En édition complète (défaut de la CI) RIEN ne change — c'est ce que gardent les
deux premiers tests.
"""
from django.test import TestCase

from apps.dataimport.services import (
    CIBLES_MODULE_PROPRIETAIRE, FIELD_MAPS, TARGETS,
    cibles_parquees_par_edition,
)


class CiblesParqueesTests(TestCase):
    def test_edition_complete_ne_retire_rien(self):
        self.assertEqual(cibles_parquees_par_edition('full'), frozenset())
        # Le mapping d'en-têtes reste déclaré ici quelle que soit l'édition —
        # seule la DISPONIBILITÉ de la cible bouge.
        self.assertIn('eleves_education', FIELD_MAPS)

    def test_cibles_resolues_coherentes_avec_l_edition_courante(self):
        from django.conf import settings

        present = 'eleves_education' in set(TARGETS)
        self.assertEqual(present, settings.TAQINOR_EDITION == 'full')

    def test_edition_solaire_retire_les_eleves(self):
        self.assertEqual(
            cibles_parquees_par_edition('solar'), frozenset({'eleves_education'}))

    def test_chaque_cible_declaree_pointe_vers_un_module_connu(self):
        """Le mapping cible → module propriétaire reste vrai."""
        from core import modules as modules_infra

        manifests = modules_infra.collect_manifests()
        for cible, module in CIBLES_MODULE_PROPRIETAIRE.items():
            self.assertIn(
                cible, FIELD_MAPS,
                f'{cible} n\'est plus une cible de FIELD_MAPS')
            self.assertIn(
                module, manifests,
                f'module propriétaire inconnu pour {cible} : {module}')
