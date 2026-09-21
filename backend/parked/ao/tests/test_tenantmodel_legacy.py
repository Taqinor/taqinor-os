"""AOF4 — les 8 modèles legacy AO passent au socle ``core.models.TenantModel``.

Ils portaient une FK ``company`` hand-rollée et AUCUN horodatage. La conversion
doit être invisible en base :

  1. chaque modèle hérite de ``TenantModel`` (FK company + timestamps) ;
  2. chaque modèle REDÉCLARE ``company`` dans son corps pour CONSERVER son
     ``related_name`` historique (motif ARC1) — jamais un renommage
     d'accesseur, qui casserait ``company.appels_offres`` & co ;
  3. les ``db_table = 'compta_*'`` sont STRICTEMENT inchangées et la migration
     ``0002_tenantmodel`` ne contient AUCUN ``AlterModelTable`` (un renommage
     de table en production serait irréversible) ;
  4. la migration est purement ADDITIVE (que des ``AddField``) ;
  5. ``created_at``/``updated_at`` sont réellement peuplés à la création et
     ``updated_at`` bouge à la mise à jour, sans toucher ``date_creation``.

Run :
    python manage.py test apps.ao.tests.test_tenantmodel_legacy -v2
"""
import importlib

from django.test import SimpleTestCase, TestCase

from apps.ao.models import (
    AppelOffre, BordereauPrix, CautionSoumission, DossierSoumission,
    EcheanceAO, LigneBordereau, PieceSoumission, ResultatAO,
)
from authentication.models import Company
from core.models import TenantModel

#: modèle → (table physique gelée, related_name historique de ``company``)
ATTENDU = {
    AppelOffre: ('compta_appeloffre', 'appels_offres'),
    BordereauPrix: ('compta_bordereauprix', 'bordereaux_prix'),
    LigneBordereau: ('compta_lignebordereau', 'lignes_bordereau'),
    CautionSoumission: ('compta_cautionsoumission', 'cautions_soumission'),
    DossierSoumission: ('compta_dossiersoumission', 'dossiers_soumission'),
    PieceSoumission: ('compta_piecesoumission', 'pieces_soumission'),
    EcheanceAO: ('compta_echeanceao', 'echeances_ao'),
    ResultatAO: ('compta_resultatao', 'resultats_ao'),
}


class TestSocleTenantModel(SimpleTestCase):
    def test_les_huit_modeles_heritent_du_socle(self):
        for model in ATTENDU:
            self.assertTrue(issubclass(model, TenantModel), model.__name__)

    def test_horodatages_gagnes(self):
        for model in ATTENDU:
            noms = {f.name for f in model._meta.get_fields()}
            self.assertIn('created_at', noms, model.__name__)
            self.assertIn('updated_at', noms, model.__name__)

    def test_tables_physiques_inchangees(self):
        for model, (table, _) in ATTENDU.items():
            self.assertEqual(model._meta.db_table, table, model.__name__)
            self.assertEqual(model._meta.app_label, 'ao', model.__name__)

    def test_related_names_historiques_conserves(self):
        for model, (_, related) in ATTENDU.items():
            champ = model._meta.get_field('company')
            self.assertEqual(
                champ.remote_field.related_name, related, model.__name__)
            self.assertTrue(
                hasattr(Company, related),
                f"Company.{related} doit rester accessible")

    def test_date_creation_historique_conservee(self):
        """``date_creation`` porte des données : jamais supprimée/renommée."""
        for model in (AppelOffre, BordereauPrix, CautionSoumission,
                      DossierSoumission, EcheanceAO, ResultatAO):
            noms = {f.name for f in model._meta.get_fields()}
            self.assertIn('date_creation', noms, model.__name__)


class TestMigration0002Additive(SimpleTestCase):
    """La migration ne doit contenir que des ``AddField``."""

    def setUp(self):
        self.migration = importlib.import_module(
            'apps.ao.migrations.0002_tenantmodel')

    def test_aucun_alter_model_table(self):
        from django.db import migrations as dj_migrations
        interdits = (
            dj_migrations.AlterModelTable,
            dj_migrations.RenameModel,
            dj_migrations.DeleteModel,
            dj_migrations.RemoveField,
        )
        for op in self.migration.Migration.operations:
            self.assertNotIsInstance(op, interdits, type(op).__name__)

    def test_uniquement_des_addfield(self):
        from django.db import migrations as dj_migrations
        self.assertTrue(self.migration.Migration.operations)
        for op in self.migration.Migration.operations:
            self.assertIsInstance(op, dj_migrations.AddField,
                                  type(op).__name__)
            self.assertIn(op.name, ('created_at', 'updated_at'))


class TestHorodatagesPeuples(TestCase):
    def test_created_updated_at_peuples_et_date_creation_intacte(self):
        company = Company.objects.create(nom='AOF4 Co', slug='aof4-co')
        ao = AppelOffre.objects.create(
            company=company, reference='AO-AOF4-01', objet='Socle')
        self.assertIsNotNone(ao.created_at)
        self.assertIsNotNone(ao.updated_at)
        self.assertIsNotNone(ao.date_creation)
        premier_created = ao.created_at
        premier_updated = ao.updated_at
        ao.objet = 'Socle (modifié)'
        ao.save()
        ao.refresh_from_db()
        self.assertGreaterEqual(ao.updated_at, premier_updated)
        self.assertEqual(ao.created_at, premier_created)

    def test_accesseur_inverse_historique_fonctionne(self):
        company = Company.objects.create(nom='AOF4 Rev', slug='aof4-rev')
        AppelOffre.objects.create(
            company=company, reference='AO-AOF4-02', objet='Inverse')
        self.assertEqual(company.appels_offres.count(), 1)
