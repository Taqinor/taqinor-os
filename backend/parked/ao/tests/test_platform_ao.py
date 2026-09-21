"""AOF165 — manifeste plateforme AO : HONNÊTE, donc vérifiable.

La règle d'honnêteté ARC41 dit qu'une surface DÉCLARÉE doit être CÂBLÉE. Ce
module en fait un test au lieu d'une bonne intention : chaque clé déclarée par
``apps/ao/platform.py`` est confrontée à son câblage réel, et une déclaration
inventée fait rougir la suite.

Il verrouille aussi les deux surfaces laissées VIDES à dessein
(``searchable_models`` et l'extension de ``record_targets``) : les remplir sans
câbler d'abord ``apps/reporting/search.py`` périmerait la baseline de
``core/platform_coverage.py`` et créerait des dérives nouvelles. Le test dit
POURQUOI elles sont vides, pour qu'un futur agent ne les « complète » pas en
croyant réparer un oubli.

Run :
    python manage.py test apps.ao.tests.test_platform_ao -v2
"""
from django.apps import apps as django_apps
from django.test import SimpleTestCase

from apps.ao.platform import PLATFORM
from core import platform as core_platform

#: Surfaces qui doivent exister dans TOUT manifeste (contrat ARC28).
SURFACES = (
    'module', 'record_targets', 'searchable_models', 'customfield_models',
    'import_specs', 'agent_actions_module', 'automation_state_fields',
    'kpi_providers',
)


class LeManifesteRespecteLeContratARC28(SimpleTestCase):
    def test_toutes_les_surfaces_sont_presentes(self):
        for surface in SURFACES:
            self.assertIn(surface, PLATFORM, surface)

    def test_le_module_est_ao(self):
        self.assertEqual(PLATFORM['module'], 'ao')

    def test_le_manifeste_est_collecte_par_le_registre(self):
        manifestes = core_platform.collect_platform_manifests()
        self.assertIn('ao', manifestes)
        self.assertEqual(manifestes['ao']['module'], 'ao')


class ChaqueChampPersonnaliseDeclareEstReellementStockable(SimpleTestCase):
    """``customfield_models`` : une clé déclarée DOIT pouvoir stocker sa valeur.

    Le chargeur central ARC31 enregistre la clé, mais les valeurs vivent dans
    un champ ``custom_data`` (``JSONField``) porté PAR LE MODÈLE CIBLE — c'est
    ainsi que les deux pilotes (``contrats.Contrat``, ``flotte.Vehicule``) sont
    câblés. Déclarer une clé sur un modèle sans ce champ donnerait un écran qui
    accepte la saisie et la jette en silence.
    """

    def test_chaque_cle_resout_un_modele_de_l_app_ao(self):
        for cle in PLATFORM['customfield_models']:
            modele = django_apps.get_model('ao', cle)
            self.assertIsNotNone(modele, cle)
            self.assertEqual(modele._meta.app_label, 'ao')

    def test_chaque_cle_declaree_porte_bien_custom_data(self):
        for cle in PLATFORM['customfield_models']:
            modele = django_apps.get_model('ao', cle)
            champs = {f.name for f in modele._meta.get_fields()}
            self.assertIn(
                'custom_data', champs,
                "%s est déclaré « customfieldable » mais ne porte pas de "
                "champ custom_data : les valeurs saisies seraient perdues "
                "en silence." % cle)

    def test_le_patron_de_reference_porte_bien_custom_data(self):
        """Garde du test lui-même : le pilote ``contrats.Contrat`` le porte."""
        contrat = django_apps.get_model('contrats', 'contrat')
        self.assertIn('custom_data',
                      {f.name for f in contrat._meta.get_fields()})

    def test_une_cle_inventee_ne_resout_rien(self):
        with self.assertRaises(LookupError):
            django_apps.get_model('ao', 'modele_qui_n_existe_pas')


class ChaqueSpecDImportDeclareeEstReellementImplementee(SimpleTestCase):
    """``import_specs`` : les clés DOIVENT être celles d'``apps/ao/imports.py``."""

    def test_chaque_spec_existe_dans_field_maps_ao(self):
        from apps.ao.imports import FIELD_MAPS_AO

        self.assertTrue(PLATFORM['import_specs'])
        for spec in PLATFORM['import_specs']:
            self.assertIn(spec, FIELD_MAPS_AO, spec)

    def test_aucune_spec_implementee_n_est_oubliee(self):
        """L'inverse : une spec câblée mais NON déclarée serait invisible."""
        from apps.ao.imports import FIELD_MAPS_AO

        self.assertEqual(sorted(PLATFORM['import_specs']),
                         sorted(FIELD_MAPS_AO))

    def test_les_specs_entrent_dans_les_cibles_dataimport(self):
        from apps.dataimport.services import TARGETS

        for spec in PLATFORM['import_specs']:
            self.assertIn(spec, TARGETS, spec)


class LAutomatisationNeDeclareQueDesChampsDEtat(SimpleTestCase):
    def test_le_statut_est_declare_et_existe_sur_le_modele(self):
        champs = PLATFORM['automation_state_fields']
        self.assertEqual(len(champs), 1)
        entree = champs[0]
        self.assertEqual(entree['model'], 'ao.appeloffre')
        modele = django_apps.get_model('ao', 'appeloffre')
        modele._meta.get_field(entree['field'])  # lève si le champ n'existe pas

    def test_aucune_date_n_est_declaree_comme_champ_d_etat(self):
        """Une date limite est un couperet de calendrier, pas un état.

        La déclarer ici ferait croire à une automatisation no-code
        ``RECORD_STATE_CHANGE`` qui n'existe pas : les échéances passent par
        ``EcheanceAO`` et le beat ``ao.rappeler_echeances``.
        """
        modele = django_apps.get_model('ao', 'appeloffre')
        for entree in PLATFORM['automation_state_fields']:
            champ = modele._meta.get_field(entree['field'])
            self.assertFalse(
                champ.get_internal_type().endswith('DateField'),
                'champ de date déclaré comme champ d\'état : %s'
                % entree['field'])


class LesSurfacesVidesLeSontAVecUneRaison(SimpleTestCase):
    """Ne pas « compléter » ces surfaces sans câbler d'abord — voir docstring."""

    def test_searchable_models_reste_vide_faute_de_spec_de_recherche(self):
        from apps.reporting.search import _SEARCH_SPECS

        cles_de_recherche = {cle for cle, _spec in _SEARCH_SPECS}
        for modele in PLATFORM['searchable_models']:
            self.assertIn(
                modele, cles_de_recherche,
                "modèle déclaré cherchable sans spec dans "
                "apps/reporting/search.py : la recherche globale ne rendrait "
                "RIEN pour ce modèle (déclaration non câblée, ARC41).")

    def test_aucune_cible_chatter_sans_recherche_nouvelle(self):
        """Toute cible ajoutée ici doit être cherchable, ou baselinée.

        ``core.platform_coverage`` fait rougir la CI sur une dérive NOUVELLE :
        un ``record_target`` non cherchable et non présent dans la baseline.
        Ce test le dit AVANT la CI, en français.
        """
        from core.platform_coverage import BASELINE_DRIFT, all_drift

        cherchables = set(core_platform.searchable_models(company=None))
        for modele in PLATFORM['record_targets']:
            if modele in cherchables:
                continue
            self.assertIn(
                (modele, 'chatter_sans_recherche'), BASELINE_DRIFT,
                "%s est chatter-isé mais introuvable en recherche, et cette "
                "dérive n'est pas dans la baseline : la CI rougira." % modele)
        # Aucune dérive NOUVELLE imputable à ce manifeste.
        nouvelles = {(m, c) for (m, c) in all_drift() - BASELINE_DRIFT
                     if m.startswith('ao.')}
        self.assertEqual(nouvelles, set())

    def test_la_baseline_ao_reste_exacte(self):
        """Une entrée de baseline qui n'est PLUS vraie doit être retirée.

        Tant que ``ao.appeloffre`` n'est pas cherchable, son entrée reste
        légitime — si un futur agent le rend cherchable, il devra retirer
        l'entrée de ``core/platform_coverage.py`` DANS LE MÊME COMMIT.
        """
        from core.platform_coverage import stale_baseline

        restantes = {(m, c) for (m, c) in stale_baseline()
                     if m.startswith('ao.')}
        self.assertEqual(restantes, set())
