"""STKCAT21 — `core/product_roles.py` reste une FONDATION PURE.

`core` est la couche que TOUTES les apps peuvent importer vers le bas ; elle
ne doit rien importer de `apps/*` (contrat `.importlinter`, CI `lint-imports`).
C'est précisément pour cela que le classifieur par mots-clés — qui vit côté
`apps.ventes` — est INJECTÉ dans `role_effectif` au lieu d'être importé.

Ce fichier vérifie l'invariant EN CODE (lecture du source par `ast`), pas en
prose : une prose ne se vérifie pas.

Run :
    docker compose exec django_core python manage.py test \
        core.tests.test_stkcat21_product_roles -v 2
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from core import product_roles
from core.product_roles import FAMILLE_VERS_ROLE, ROLES_DEVIS, SOURCES_ROLE

SOURCE = Path(product_roles.__file__).with_suffix('.py')


def _modules_importes():
    """Tous les modules cités par un `import` du fichier (niveau module)."""
    arbre = ast.parse(SOURCE.read_text(encoding='utf-8'), filename=str(SOURCE))
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            noms.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            noms.add(noeud.module)
    return noms


class TestProductRolesFondationPure(SimpleTestCase):
    def test_aucun_import_d_app_ni_de_django(self):
        interdits = sorted(
            nom for nom in _modules_importes()
            if nom.split('.')[0] in ('apps', 'django', 'authentication', 'rest_framework')
        )
        self.assertEqual(
            interdits, [],
            "core/product_roles.py importe %s — la couche de fondation ne "
            "dépend d'aucune app (contrat .importlinter). Le classifieur par "
            "mots-clés s'INJECTE (paramètre `classer_nom`)." % interdits)

    def test_le_classifieur_est_injecte_pas_importe(self):
        # Sans classifieur, le rang « mots-clés » est simplement sauté : la
        # fonction ne va JAMAIS chercher une implémentation par elle-même.
        self.assertEqual(
            product_roles.role_effectif(nom='Panneau Jinko 710W'),
            (None, None))
        self.assertEqual(
            product_roles.role_effectif(
                nom='Panneau Jinko 710W',
                classer_nom=lambda n: 'panneau'),
            ('panneau', 'nom'))


class TestVocabulaireIntegre(SimpleTestCase):
    def test_roles_uniques_non_vides(self):
        self.assertEqual(len(ROLES_DEVIS), len(set(ROLES_DEVIS)))
        for role in ROLES_DEVIS:
            self.assertTrue(role and role.strip() == role, repr(role))

    def test_sources_declarees(self):
        self.assertEqual(SOURCES_ROLE, ('declare', 'categorie', 'nom'))
        sources = set()
        for cas in (
            dict(role_devis='panneau'),
            dict(type_equipement='panneau'),
            dict(nom='x', classer_nom=lambda n: 'panneau'),
        ):
            sources.add(product_roles.role_effectif(**cas)[1])
        self.assertEqual(sources, set(SOURCES_ROLE))

    def test_la_carte_des_familles_ne_pointe_que_le_vocabulaire(self):
        for famille, role in FAMILLE_VERS_ROLE.items():
            with self.subTest(famille=famille):
                self.assertTrue(role is None or role in ROLES_DEVIS)

    def test_les_alias_deprecies_de_structure_sont_conserves(self):
        # Un réglage `ParametresGammes` enregistré hier doit rester accepté :
        # ces deux alias ne se retirent JAMAIS (STKCAT2).
        self.assertIn('structure_acier', ROLES_DEVIS)
        self.assertIn('structure_alu', ROLES_DEVIS)
        self.assertIn('structure', ROLES_DEVIS)
