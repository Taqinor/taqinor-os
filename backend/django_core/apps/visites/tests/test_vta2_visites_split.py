"""VTA2 — la visite technique terrain est relogée d'``apps.crm`` vers
``apps.visites`` en STATE-ONLY.

Ce que le test prouve (patron ``apps/frais/tests/test_odx15_frais_split.py``) :

* les 2 modèles vivent dans ``apps.visites`` mais gardent leurs tables
  PHYSIQUES ``crm_visiteterrain`` / ``crm_visitemedia`` — le move ne touche
  aucune donnée ;
* les INDEX gardent leurs noms historiques (les renommer produirait du SQL,
  donc un move qui n'en serait plus un) ;
* la FK ``lead`` est une référence STRING : ``apps.visites.models`` n'importe
  JAMAIS ``apps.crm`` (contrat ``independence`` d'import-linter) ;
* ``apps.crm.models`` ne ré-exporte PAS les classes déménagées — un shim
  recréerait exactement l'arête que le move supprime ;
* les DEUX migrations du move sont ``SeparateDatabaseAndState`` avec
  ``database_operations == []``, et celle de ``visites`` DÉPEND du retrait
  côté ``crm`` (aucun instant avec deux modèles pour la même table) ;
* les données existantes restent lisibles par les DEUX bouts de la relation
  (``lead.visites_terrain`` fonctionne toujours depuis le CRM).

Run :
    python manage.py test apps.visites.tests.test_vta2_visites_split -v2
"""
from importlib import import_module

from django.contrib.auth import get_user_model
from django.db.migrations.operations.special import SeparateDatabaseAndState
from django.test import TestCase

from authentication.models import Company

User = get_user_model()


class TablesEtEtatTests(TestCase):
    """Le move déplace du CODE, jamais des DONNÉES."""

    def test_modeles_dans_visites_avec_tables_preservees(self):
        from apps.visites.models import VisiteMedia, VisiteTerrain

        attendu = {
            VisiteTerrain: 'crm_visiteterrain',
            VisiteMedia: 'crm_visitemedia',
        }
        for model, table in attendu.items():
            self.assertEqual(model._meta.db_table, table)
            self.assertEqual(model._meta.app_label, 'visites')

    def test_index_gardent_leurs_noms_historiques(self):
        from apps.visites.models import VisiteMedia, VisiteTerrain

        noms = {index.name for index in VisiteTerrain._meta.indexes}
        self.assertEqual(
            noms, {'crm_vterr_comp_statut_idx', 'crm_vterr_comp_com_idx'})
        self.assertEqual(
            {index.name for index in VisiteMedia._meta.indexes},
            {'crm_vmedia_visite_slot_idx'})

    def test_fk_lead_est_une_reference_string(self):
        """``apps.visites.models`` ne doit importer AUCUN modèle de domaine."""
        import inspect

        from apps.visites import models as visites_models

        source = inspect.getsource(visites_models)
        self.assertNotIn('from apps.crm', source)
        self.assertNotIn('import apps.crm', source)
        self.assertIn("'crm.Lead'", source)

    def test_fk_lead_pointe_bien_le_lead_du_crm(self):
        from apps.crm.models import Lead
        from apps.visites.models import VisiteTerrain

        champ = VisiteTerrain._meta.get_field('lead')
        self.assertIs(champ.related_model, Lead)
        self.assertEqual(champ.remote_field.related_name, 'visites_terrain')

    def test_crm_models_ne_reexporte_pas_les_classes_demenagees(self):
        """PAS de shim : il recréerait `crm.models -> visites.models`.

        C'est la différence assumée avec ODX15 (où compta ré-exporte) : ici les
        DEUX modules sont dans le contrat ``independence`` d'import-linter, une
        ré-exportation serait donc interdite — et inutile, puisque le reste du
        CRM lit la visite par ``apps.visites.selectors``.
        """
        from apps.crm import models as crm_models

        self.assertFalse(hasattr(crm_models, 'VisiteTerrain'))
        self.assertFalse(hasattr(crm_models, 'VisiteMedia'))


class MigrationsDuMoveTests(TestCase):
    """La garantie du move, lue sur les FICHIERS, pas sur un commentaire."""

    CHEMINS = (
        'apps.crm.migrations.0099_vta2_visites_split',
        'apps.visites.migrations.0001_vta2_visites_split',
        # 0002 (ContentType) est volontairement HORS de cette liste : c'est
        # une RunPython idempotente qui ne touche QUE django_content_type.
    )

    def test_migrations_du_move_sont_state_only(self):
        for chemin in self.CHEMINS:
            module = import_module(chemin)
            operations = module.Migration.operations
            self.assertTrue(operations, chemin)
            for operation in operations:
                self.assertIsInstance(operation, SeparateDatabaseAndState,
                                      chemin)
                self.assertEqual(operation.database_operations, [], chemin)
                self.assertTrue(operation.state_operations, chemin)

    def test_migration_visites_depend_du_retrait_dans_crm(self):
        """L'ordre garantit qu'aucun instant n'a deux modèles par table."""
        module = import_module(
            'apps.visites.migrations.0001_vta2_visites_split')
        self.assertIn(('crm', '0099_vta2_visites_split'),
                      module.Migration.dependencies)

    def test_migration_contenttypes_est_reversible(self):
        """Un move qu'on ne peut pas défaire n'est pas un move sûr."""
        module = import_module(
            'apps.visites.migrations.0002_vta2_rename_stale_contenttypes')
        operation = module.Migration.operations[0]
        self.assertIsNotNone(operation.reverse_code)
        self.assertEqual(sorted(module.MOVED_MODELS),
                         ['visitemedia', 'visiteterrain'])


class DonneesLisiblesDesDeuxBoutsTests(TestCase):
    """Le CRM continue de voir les visites d'un lead (relation inverse)."""

    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Lead

        cls.company = Company.objects.create(nom='VTA2 Société')
        # Tenant-distinctness : une SECONDE société RÉELLE, avec ses données.
        cls.autre = Company.objects.create(nom='VTA2 Autre société')
        cls.user = User.objects.create_user(
            username='vta2_com', password='x', role_legacy='normal',
            company=cls.company)
        cls.lead = Lead.objects.create(
            company=cls.company, nom='Bennani', ville='Bouskoura')
        cls.lead_autre = Lead.objects.create(
            company=cls.autre, nom='Autre lead', ville='Rabat')

    def test_relation_inverse_depuis_le_lead(self):
        from apps.visites.models import VisiteTerrain

        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, commercial=self.user)
        self.assertEqual(list(self.lead.visites_terrain.all()), [visite])
        self.assertEqual(list(self.user.visites_terrain.all()), [visite])

    def test_isolation_multi_societe_conservee(self):
        from apps.visites.models import VisiteTerrain

        VisiteTerrain.objects.create(company=self.company, lead=self.lead)
        VisiteTerrain.objects.create(
            company=self.autre, lead=self.lead_autre)
        self.assertEqual(
            VisiteTerrain.objects.filter(company=self.company).count(), 1)
        self.assertEqual(
            list(self.lead_autre.visites_terrain.values_list(
                'company_id', flat=True)),
            [self.autre.id])
