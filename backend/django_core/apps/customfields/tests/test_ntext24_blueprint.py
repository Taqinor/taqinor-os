"""NTEXT24 — blueprint tenant : export/import de la CONFIG de plateforme.

Exporter la config d'une société pilote puis l'importer dans une société vierge
recrée objets/champs/règles/rapports/vues/gabarits à l'identique — jamais les
DONNÉES (aucun ``CustomRecord`` ne voyage), et ré-importer est idempotent.
"""
from django.test import TestCase

from authentication.models import Company
from core.models import VuePersonnalisee

from apps.automation.models import (
    ActionType, AutomationRule, AutomationStep, TriggerType,
)
from apps.customfields.blueprint import (
    VERSION_BLUEPRINT, exporter_blueprint, importer_blueprint,
)
from apps.customfields.models import (
    CustomFieldDef, CustomObjectDef, CustomRecord,
)
from apps.parametres.models import GabaritDocumentCustom
from apps.reporting.models import RapportDefinition


class BlueprintTests(TestCase):
    def setUp(self):
        self.pilote = Company.objects.create(nom='NTEXT24 Pilote')
        self.vierge = Company.objects.create(nom='NTEXT24 Vierge')

        objet = CustomObjectDef.objects.create(
            company=self.pilote, code='pret-materiel',
            libelle='Prêt de matériel')
        CustomFieldDef.objects.create(
            company=self.pilote, module=objet.field_module, code='materiel',
            libelle='Matériel', type='text', obligatoire=True, ordre=1)
        CustomFieldDef.objects.create(
            company=self.pilote, module=objet.field_module, code='retour',
            libelle='Date de retour', type='date', ordre=2)
        # DONNÉE (jamais exportée).
        CustomRecord.objects.create(
            company=self.pilote, objet=objet, data={'materiel': 'Échelle'})

        regle = AutomationRule.objects.create(
            company=self.pilote, nom='Relance J+3',
            trigger_type=TriggerType.DEVIS_ACCEPTED,
            trigger_config={'x': 1}, action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'}, ordre=2)
        AutomationStep.objects.create(
            rule=regle, ordre=1, action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'Bonjour'})
        AutomationStep.objects.create(
            rule=regle, ordre=2, action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'})

        RapportDefinition.objects.create(
            company=self.pilote, titre='CA par commercial',
            dataset='vitals', spec={'group_by': ['route']},
            partage=RapportDefinition.Partage.SOCIETE)
        VuePersonnalisee.objects.create(
            company=self.pilote, cible='crm.lead', nom='Leads chauds',
            config={'tri': '-created_at'},
            partage=VuePersonnalisee.Partage.SOCIETE, est_defaut=True)
        GabaritDocumentCustom.objects.create(
            company=self.pilote, code='fiche-visite', nom='Fiche de visite',
            cible=GabaritDocumentCustom.Cible.CHANTIER, corps='<p>{{ x }}</p>')

    def test_export_contains_every_section_and_no_data(self):
        blueprint = exporter_blueprint(self.pilote)
        self.assertEqual(blueprint['version'], VERSION_BLUEPRINT)
        sections = blueprint['sections']
        self.assertEqual(len(sections['objets']), 1)
        self.assertEqual(len(sections['champs']), 2)
        self.assertEqual(len(sections['regles']), 1)
        self.assertEqual(len(sections['rapports']), 1)
        self.assertEqual(len(sections['vues']), 1)
        self.assertEqual(len(sections['gabarits']), 1)
        self.assertEqual(len(sections['regles'][0]['etapes']), 2)
        # Aucune donnée saisie ne voyage.
        self.assertNotIn('enregistrements', sections)
        texte = str(sections)
        self.assertNotIn('Échelle', texte)
        # Aucun identifiant technique ni société d'origine.
        self.assertNotIn('company', sections['objets'][0])
        self.assertNotIn('id', sections['objets'][0])

    def test_import_recreates_config_in_a_blank_company(self):
        blueprint = exporter_blueprint(self.pilote)
        resultat = importer_blueprint(self.vierge, blueprint)
        self.assertEqual(resultat['objets']['crees'], 1)
        self.assertEqual(resultat['champs']['crees'], 2)

        objet = CustomObjectDef.objects.get(
            company=self.vierge, code='pret-materiel')
        self.assertEqual(objet.libelle, 'Prêt de matériel')
        self.assertEqual(
            CustomFieldDef.objects.filter(
                company=self.vierge, module=objet.field_module).count(), 2)
        regle = AutomationRule.objects.get(
            company=self.vierge, nom='Relance J+3')
        self.assertEqual(regle.trigger_config, {'x': 1})
        self.assertEqual(
            [s.action_type for s in regle.steps.order_by('ordre')],
            [ActionType.SEND_EMAIL, ActionType.SET_FIELD])
        self.assertTrue(RapportDefinition.objects.filter(
            company=self.vierge, titre='CA par commercial').exists())
        vue = VuePersonnalisee.objects.get(
            company=self.vierge, cible='crm.lead')
        self.assertTrue(vue.est_defaut)
        self.assertTrue(GabaritDocumentCustom.objects.filter(
            company=self.vierge, code='fiche-visite').exists())
        # Les DONNÉES ne sont jamais recréées.
        self.assertEqual(
            CustomRecord.objects.filter(company=self.vierge).count(), 0)

    def test_import_is_idempotent(self):
        blueprint = exporter_blueprint(self.pilote)
        importer_blueprint(self.vierge, blueprint)
        second = importer_blueprint(self.vierge, blueprint)
        self.assertEqual(second['objets']['crees'], 0)
        self.assertEqual(second['objets']['majs'], 1)
        self.assertEqual(
            CustomObjectDef.objects.filter(company=self.vierge).count(), 1)
        self.assertEqual(
            CustomFieldDef.objects.filter(company=self.vierge).count(), 2)
        regle = AutomationRule.objects.get(company=self.vierge)
        self.assertEqual(regle.steps.count(), 2)

    def test_import_never_touches_the_source_company(self):
        blueprint = exporter_blueprint(self.pilote)
        importer_blueprint(self.vierge, blueprint)
        self.assertEqual(
            CustomObjectDef.objects.filter(company=self.pilote).count(), 1)
        self.assertEqual(
            CustomRecord.objects.filter(company=self.pilote).count(), 1)

    def test_future_version_is_refused(self):
        with self.assertRaises(ValueError):
            importer_blueprint(
                self.vierge, {'version': VERSION_BLUEPRINT + 1,
                              'sections': {}})

    def test_malformed_blueprint_is_refused(self):
        with self.assertRaises(ValueError):
            importer_blueprint(self.vierge, 'pas un blueprint')

    def test_incomplete_natural_key_line_is_skipped(self):
        resultat = importer_blueprint(self.vierge, {
            'version': VERSION_BLUEPRINT,
            'sections': {'objets': [{'libelle': 'Sans code'}]},
        })
        self.assertEqual(resultat['objets']['crees'], 0)
        self.assertEqual(
            CustomObjectDef.objects.filter(company=self.vierge).count(), 0)
