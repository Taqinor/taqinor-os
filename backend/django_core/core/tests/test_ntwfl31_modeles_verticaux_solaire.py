"""Tests NTWFL31 — modèles de processus verticaux solaire (seed).

Acceptance criteria couverte : installer le modèle « Réclamation SAV complexe »
crée une ``WorkflowDefinition`` à 3 étapes avec un formulaire de qualification
attaché, et l'installation est IDEMPOTENTE (ré-installer ne duplique rien).
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from core import workflow_templates
from core.models import (
    FormulaireDefinition, WorkflowDefinition, WorkflowStepDefinition,
)

CODES_VERTICAUX = (
    'validation_devis_forte_remise',
    'onboarding_chantier_grand_compte',
    'reclamation_sav_complexe',
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FormeDesModelesVerticauxTests(SimpleTestCase):
    """Forme du seed — pur catalogue, aucune base touchée."""

    def test_les_trois_modeles_verticaux_sont_au_catalogue(self):
        codes = {t['code'] for t in workflow_templates.WORKFLOW_TEMPLATES}
        for code in CODES_VERTICAUX:
            self.assertIn(code, codes)

    def test_chaque_modele_vertical_porte_un_formulaire(self):
        for code in CODES_VERTICAUX:
            tpl = workflow_templates.get_modele_workflow(code)
            avec_formulaire = [s for s in tpl['steps'] if s.get('formulaire')]
            self.assertEqual(
                len(avec_formulaire), 1,
                f'{code} doit livrer exactement un formulaire par défaut')
            spec = avec_formulaire[0]['formulaire']
            self.assertTrue(spec['code'])
            self.assertTrue(spec['nom'])
            self.assertTrue(spec['schema'])
            for champ in spec['schema']:
                self.assertTrue(champ.get('nom'))
                self.assertIn(champ.get('type'),
                              {'texte', 'nombre', 'date', 'choix', 'booleen'})

    def test_longueurs_des_formulaires_tiennent_dans_ntwfl12(self):
        code_max = FormulaireDefinition._meta.get_field('code').max_length
        nom_max = FormulaireDefinition._meta.get_field('nom').max_length
        for code in CODES_VERTICAUX:
            for step in workflow_templates.get_modele_workflow(code)['steps']:
                spec = step.get('formulaire')
                if not spec:
                    continue
                self.assertLessEqual(len(spec['code']), code_max)
                self.assertLessEqual(len(spec['nom']), nom_max)

    def test_condition_de_visibilite_au_format_core_rules(self):
        """Un champ conditionnel du seed est RÉELLEMENT évalué par FG367."""
        from core.rules import evaluate_condition_group

        tpl = workflow_templates.get_modele_workflow(
            'onboarding_chantier_grand_compte')
        spec = next(s['formulaire'] for s in tpl['steps'] if s.get('formulaire'))
        regle = spec['champs_conditionnels']['detail_penalites']['visible_si']
        self.assertTrue(
            evaluate_condition_group(regle, {'penalites_de_retard': True}))
        self.assertFalse(
            evaluate_condition_group(regle, {'penalites_de_retard': False}))

    def test_liste_expose_le_formulaire_sans_muter_le_catalogue(self):
        listing = workflow_templates.liste_modeles_workflow()
        entree = next(m for m in listing
                      if m['code'] == 'reclamation_sav_complexe')
        spec = next(s['formulaire'] for s in entree['steps']
                    if s.get('formulaire'))
        spec['nom'] = 'MUTÉ'
        brut = workflow_templates.get_modele_workflow(
            'reclamation_sav_complexe')
        brut_spec = next(s['formulaire'] for s in brut['steps']
                         if s.get('formulaire'))
        self.assertNotEqual(brut_spec['nom'], 'MUTÉ')


class InstallationModelesVerticauxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl31', 'NTWFL31')
        cls.autre = make_company('ntwfl31-autre', 'NTWFL31 Autre')

    def test_reclamation_sav_complexe_trois_etapes_avec_formulaire(self):
        definition, created = workflow_templates.installer_modele_workflow(
            self.company, 'reclamation_sav_complexe')
        tpl = workflow_templates.get_modele_workflow(
            'reclamation_sav_complexe')

        self.assertTrue(created)
        self.assertEqual(definition.company_id, self.company.pk)
        self.assertEqual(definition.steps.count(), len(tpl['steps']))
        self.assertEqual(definition.steps.count(), 3)

        qualification = definition.steps.get(ordre=1)
        self.assertIsNotNone(qualification.formulaire)
        self.assertEqual(qualification.formulaire.company_id, self.company.pk)
        spec = tpl['steps'][0]['formulaire']
        self.assertEqual(qualification.formulaire.code, spec['code'])
        self.assertEqual(qualification.formulaire.schema, spec['schema'])
        # Les étapes suivantes n'en portent pas — on n'en invente pas.
        self.assertIsNone(definition.steps.get(ordre=2).formulaire)
        self.assertIsNone(definition.steps.get(ordre=3).formulaire)

    def test_reinstallation_ne_duplique_rien(self):
        premiere, created1 = workflow_templates.installer_modele_workflow(
            self.company, 'reclamation_sav_complexe')
        etapes = premiere.steps.count()
        formulaires = FormulaireDefinition.objects.filter(
            company=self.company).count()

        seconde, created2 = workflow_templates.installer_modele_workflow(
            self.company, 'reclamation_sav_complexe')

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(seconde.pk, premiere.pk)
        self.assertEqual(seconde.steps.count(), etapes)
        self.assertEqual(
            FormulaireDefinition.objects.filter(
                company=self.company).count(), formulaires)
        self.assertEqual(
            WorkflowDefinition.objects.filter(
                company=self.company,
                code='reclamation_sav_complexe').count(), 1)

    def test_formulaire_existant_est_reutilise_jamais_ecrase(self):
        spec = next(
            s['formulaire']
            for s in workflow_templates.get_modele_workflow(
                'reclamation_sav_complexe')['steps']
            if s.get('formulaire'))
        # L'admin a DÉJÀ un formulaire de ce code, adapté à sa société.
        maison = FormulaireDefinition.objects.create(
            company=self.company, code=spec['code'], nom='Version maison',
            schema=[{'nom': 'champ_maison', 'type': 'texte', 'requis': True}])

        definition, _ = workflow_templates.installer_modele_workflow(
            self.company, 'reclamation_sav_complexe')
        etape = definition.steps.get(ordre=1)

        self.assertEqual(etape.formulaire_id, maison.pk)
        maison.refresh_from_db()
        self.assertEqual(maison.nom, 'Version maison')
        self.assertEqual(maison.schema,
                         [{'nom': 'champ_maison', 'type': 'texte',
                           'requis': True}])

    def test_les_trois_modeles_sinstallent(self):
        for code in CODES_VERTICAUX:
            definition, created = workflow_templates.installer_modele_workflow(
                self.company, code)
            tpl = workflow_templates.get_modele_workflow(code)
            self.assertTrue(created, code)
            self.assertEqual(definition.steps.count(), len(tpl['steps']), code)
            self.assertEqual(
                definition.steps.filter(formulaire__isnull=False).count(),
                1, code)

    def test_isolation_multi_tenant(self):
        a, _ = workflow_templates.installer_modele_workflow(
            self.company, 'validation_devis_forte_remise')
        b, _ = workflow_templates.installer_modele_workflow(
            self.autre, 'validation_devis_forte_remise')
        self.assertNotEqual(a.pk, b.pk)
        form_a = a.steps.get(ordre=1).formulaire
        form_b = b.steps.get(ordre=1).formulaire
        self.assertNotEqual(form_a.pk, form_b.pk)
        self.assertEqual(form_a.company_id, self.company.pk)
        self.assertEqual(form_b.company_id, self.autre.pk)

    def test_modele_sans_formulaire_reste_inchange(self):
        definition, _ = workflow_templates.installer_modele_workflow(
            self.company, 'relance_devis')
        self.assertEqual(
            definition.steps.filter(formulaire__isnull=False).count(), 0)
        self.assertFalse(
            FormulaireDefinition.objects.filter(company=self.company).exists())

    def test_formulaire_bloque_bien_lapprobation_de_letape(self):
        """Le formulaire seedé est un VRAI formulaire NTWFL12 : ses champs
        requis bloquent l'approbation tant qu'ils ne sont pas remplis."""
        from core import workflow

        definition, _ = workflow_templates.installer_modele_workflow(
            self.company, 'reclamation_sav_complexe')
        instance = workflow.demarrer_workflow(
            definition, self.company, self.company)
        with self.assertRaises(ValueError):
            workflow.approuver_etape(instance)

        step = workflow.etape_courante_de(instance)
        step.donnees_formulaire = {
            'nature_du_defaut': 'Panne onduleur',
            'date_constat': '2026-09-01',
            'installation_sous_garantie': True,
            'description_client': 'Plus aucune production depuis samedi.',
        }
        step.save(update_fields=['donnees_formulaire'])
        workflow.approuver_etape(instance)
        instance.refresh_from_db()
        self.assertEqual(instance.etape_courante, 2)

    def test_type_approbation_des_etapes_aligne_fg366(self):
        valides = {c[0] for c in WorkflowStepDefinition.APPROBATION_CHOICES}
        for code in CODES_VERTICAUX:
            for step in workflow_templates.get_modele_workflow(code)['steps']:
                self.assertIn(step['type_approbation'], valides)
