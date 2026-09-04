"""SOL1 — cohérence « tags de manifeste (sku) ↔ registre d'éditions ».

Le registre ``erp_agentique/settings/editions.py`` est STATIQUE (une app
parquée n'étant pas chargée, son ``AppConfig`` est inatteignable) ; les
manifests ODX2, eux, vivent sur les ``AppConfig``. Rien ne garantit
mécaniquement que les deux racontent la même histoire — sauf ce test.

Invariants gardés :

1. toute app installable déclare un ``sku`` EXPLICITE et valide ;
2. tout module tagué ``vertical_<x>`` est parqué dans l'édition solaire ;
3. réciproquement, toute app parquée dans l'édition solaire porte un ``sku``
   ``vertical_<x>`` (jamais ``solar_core`` ni ``generic``) ;
4. chaque entrée du registre pointe vers une app RÉELLEMENT installée en
   édition complète et sa clé de module correspond au manifeste ;
5. les libellés FR du registre sont non vides (ils NOMMENT une app qui, en
   édition solaire, n'a plus d'``AppConfig`` pour se présenter).

Ce test tourne en édition ``full`` (la gate PR) : toutes les apps parquées
sont donc chargées et comparables à leur entrée de registre.
"""
from django.apps import apps as django_apps
from django.test import TestCase

from core import modules
from erp_agentique.settings import editions


def _manifests_bruts():
    """``{app_name: manifest brut}`` — l'attribut tel que déclaré (non normalisé).

    On lit le dict BRUT (pas ``collect_manifests``) pour pouvoir exiger la
    présence EXPLICITE de ``sku`` : la normalisation applique un défaut.
    """
    out = {}
    for app_config in django_apps.get_app_configs():
        manifest = getattr(app_config, 'module_manifest', None)
        if manifest:
            out[app_config.name] = manifest
    return out


class SkuManifesteTests(TestCase):
    def test_chaque_manifeste_declare_un_sku_explicite(self):
        manque = [
            nom for nom, manifest in _manifests_bruts().items()
            if 'sku' not in manifest
        ]
        self.assertEqual(
            manque, [],
            'apps sans « sku » dans leur module_manifest (SOL1) : '
            f'{sorted(manque)}')

    def test_chaque_sku_est_dans_le_vocabulaire(self):
        invalides = {
            nom: manifest.get('sku')
            for nom, manifest in _manifests_bruts().items()
            if not modules.sku_valide(manifest.get('sku'))
        }
        self.assertEqual(
            invalides, {},
            'sku hors vocabulaire SOL1 (solar_core/generic/optional/'
            f'vertical_<x>) : {invalides}')

    def test_sku_expose_par_la_collecte(self):
        manifests = modules.collect_manifests()
        self.assertEqual(manifests['ventes']['sku'], 'solar_core')
        self.assertEqual(manifests['pos']['sku'], 'optional')
        self.assertTrue(modules.est_vertical(manifests['sante']['sku']))
        self.assertFalse(modules.est_vertical(manifests['crm']['sku']))


class RegistreEditionsTests(TestCase):
    def test_registre_pointe_vers_des_apps_installees(self):
        """Chaque entrée du registre existe et sa clé matche le manifeste."""
        installees = {
            app_config.name: app_config
            for app_config in django_apps.get_app_configs()
        }
        problemes = []
        for chemin, (cle, libelle) in \
                editions.PARKED_APPS[editions.EDITION_SOLAR].items():
            app_config = installees.get(chemin)
            if app_config is None:
                problemes.append(
                    f'{chemin} : absent d\'INSTALLED_APPS (édition full)')
                continue
            manifest = getattr(app_config, 'module_manifest', None) or {}
            if manifest.get('key') != cle:
                problemes.append(
                    f'{chemin} : clé de registre « {cle} » ≠ clé de '
                    f'manifeste « {manifest.get("key")} »')
            if not libelle or not libelle.strip():
                problemes.append(f'{chemin} : libellé FR vide dans le registre')
        self.assertEqual(problemes, [], '; '.join(problemes))

    def test_verticaux_et_apps_parquees_coincident(self):
        """``vertical_*`` ⇔ parqué dans l'édition solaire (bidirectionnel)."""
        verticaux = {
            manifest.get('key')
            for manifest in _manifests_bruts().values()
            if modules.est_vertical(manifest.get('sku'))
        }
        parques = set(editions.modules_parques(editions.EDITION_SOLAR))
        self.assertEqual(
            verticaux, parques,
            'Divergence tags ↔ registre — tagués vertical_* mais non parqués : '
            f'{sorted(verticaux - parques)} ; parqués mais non tagués '
            f'vertical_* : {sorted(parques - verticaux)}')

    def test_aucune_app_parquee_n_est_solar_core(self):
        parques = editions.modules_parques(editions.EDITION_SOLAR)
        fautes = [
            manifest.get('key')
            for manifest in _manifests_bruts().values()
            if manifest.get('key') in parques
            and manifest.get('sku') == modules.SKU_SOLAR_CORE
        ]
        self.assertEqual(
            fautes, [],
            f'apps parquées taguées solar_core : {sorted(fautes)}')

    def test_edition_full_ne_parque_rien(self):
        self.assertEqual(editions.apps_parquees(editions.EDITION_FULL), {})
        self.assertEqual(
            editions.modules_parques(editions.EDITION_FULL), frozenset())


class EditionSelectionTests(TestCase):
    def test_defaut_est_full(self):
        self.assertEqual(editions.normaliser_edition(None), 'full')
        self.assertEqual(editions.normaliser_edition(''), 'full')
        self.assertEqual(editions.edition_active(env={}), 'full')

    def test_valeur_connue_normalisee(self):
        self.assertEqual(editions.normaliser_edition('  SOLAR '), 'solar')
        self.assertEqual(
            editions.edition_active(env={'TAQINOR_EDITION': 'solar'}), 'solar')

    def test_coquille_leve(self):
        """Une coquille ÉCHOUE — jamais un repli silencieux sur « full »."""
        with self.assertRaises(editions.EditionInconnue):
            editions.normaliser_edition('solaire')

    def test_filtrage_installed_apps(self):
        source = ['core', 'apps.crm', 'apps.mrp', 'apps.sante']
        self.assertEqual(
            editions.filtrer_installed_apps(source, 'solar'),
            ['core', 'apps.crm'])
        self.assertEqual(
            editions.filtrer_installed_apps(source, 'full'), source)

    def test_est_module_parque_couvre_les_sous_modules(self):
        self.assertTrue(editions.est_module_parque('apps.mrp.urls', 'solar'))
        self.assertTrue(
            editions.est_module_parque('apps.education.public_urls', 'solar'))
        self.assertTrue(editions.est_module_parque('apps.mrp', 'solar'))
        self.assertFalse(editions.est_module_parque('apps.crm.urls', 'solar'))
        # Un préfixe qui n'est pas une frontière de module ne matche pas.
        self.assertFalse(
            editions.est_module_parque('apps.mrpbis.urls', 'solar'))
        self.assertFalse(editions.est_module_parque('apps.mrp.urls', 'full'))

    def test_filtrage_chemins(self):
        source = {
            'A': 'apps.immobilier.models.PieceEtatLieux.EtatGeneral',
            'B': 'apps.ventes.models.RoofLayout.Orientation',
        }
        self.assertEqual(
            editions.filtrer_chemins(source, 'solar'),
            {'B': 'apps.ventes.models.RoofLayout.Orientation'})
        self.assertEqual(editions.filtrer_chemins(source, 'full'), source)
