"""Tests FG369 — bibliothèque de modèles de workflow installables.

Couvre :
  * forme du catalogue (codes/longueurs/type_approbation valides, alignés FG366) ;
  * ``installer_modele_workflow`` crée la définition + ses étapes (champs copiés) ;
  * idempotence : ré-installer le même code ne crée aucun doublon ;
  * isolation multi-tenant : deux sociétés installent le même code sans collision ;
  * code inconnu → ``ModeleWorkflowInconnu`` ;
  * endpoint : liste (auth requise), install gate admin/responsable
    (403 utilisateur limité), install crée puis 200 idempotent, code inconnu 400,
    company imposée côté serveur (jamais lue du corps).

Découplage : aucune importation d'app domaine — uniquement les modèles FG366 et
``core.workflow_templates`` / ``core.views``. ``core`` reste une fondation.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core.models import (
    WorkflowDefinition,
    WorkflowStepDefinition,
)
from core import workflow_templates
from core.views import WorkflowTemplateViewSet

User = get_user_model()


class CatalogueShapeTests(TestCase):
    """Le catalogue est des données pures, bien formées et alignées FG366."""

    def test_catalogue_has_the_prebuilt_models(self):
        codes = {t['code'] for t in workflow_templates.WORKFLOW_TEMPLATES}
        # ARC10 a ajouté le pilote domaine « cloture_ncr » (clôture NCR qhse).
        self.assertEqual(
            codes,
            {'relance_devis', 'onboarding_chantier', 'rappel_garantie',
             'cloture_ncr'},
        )

    def test_codes_are_unique(self):
        codes = [t['code'] for t in workflow_templates.WORKFLOW_TEMPLATES]
        self.assertEqual(len(codes), len(set(codes)))

    def test_field_lengths_fit_fg366_models(self):
        valid_types = {
            c[0] for c in WorkflowStepDefinition.APPROBATION_CHOICES}
        for tpl in workflow_templates.WORKFLOW_TEMPLATES:
            # WorkflowDefinition : code ≤ 64, nom ≤ 120.
            self.assertLessEqual(len(tpl['code']), 64)
            self.assertLessEqual(len(tpl['nom']), 120)
            self.assertTrue(tpl['steps'], 'un modèle doit avoir des étapes')
            ordres = [s['ordre'] for s in tpl['steps']]
            self.assertEqual(ordres, sorted(ordres))
            self.assertEqual(len(ordres), len(set(ordres)))
            for step in tpl['steps']:
                # WorkflowStepDefinition : nom ≤ 120, role_requis ≤ 80,
                # escalade_vers ≤ 120, type_approbation ∈ choix FG366.
                self.assertLessEqual(len(step['nom']), 120)
                self.assertLessEqual(len(step.get('role_requis', '')), 80)
                self.assertLessEqual(len(step.get('escalade_vers', '')), 120)
                self.assertIn(step['type_approbation'], valid_types)
                sla = step['sla_heures']
                self.assertTrue(sla is None or sla > 0)

    def test_liste_returns_copy_with_nb_etapes(self):
        listing = workflow_templates.liste_modeles_workflow()
        self.assertEqual(len(listing), len(workflow_templates.WORKFLOW_TEMPLATES))
        relance = next(
            m for m in listing if m['code'] == 'relance_devis')
        self.assertEqual(relance['nb_etapes'], len(relance['steps']))
        # Copie défensive : muter la sortie ne touche pas le catalogue global.
        relance['steps'][0]['nom'] = 'MUTÉ'
        raw = workflow_templates.get_modele_workflow('relance_devis')
        self.assertNotEqual(raw['steps'][0]['nom'], 'MUTÉ')

    def test_get_unknown_code_raises(self):
        with self.assertRaises(workflow_templates.ModeleWorkflowInconnu):
            workflow_templates.get_modele_workflow('inexistant')


class InstallServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Install Co')
        cls.other = Company.objects.create(nom='Autre Co')

    def test_install_creates_definition_and_steps(self):
        definition, created = workflow_templates.installer_modele_workflow(
            self.company, 'relance_devis')
        self.assertTrue(created)
        self.assertEqual(definition.company, self.company)
        self.assertEqual(definition.code, 'relance_devis')
        self.assertTrue(definition.actif)

        tpl = workflow_templates.get_modele_workflow('relance_devis')
        self.assertEqual(definition.steps.count(), len(tpl['steps']))

        # Les champs d'étape sont copiés fidèlement.
        first_tpl = tpl['steps'][0]
        first_step = definition.steps.order_by('ordre').first()
        self.assertEqual(first_step.nom, first_tpl['nom'])
        self.assertEqual(
            first_step.type_approbation, first_tpl['type_approbation'])
        self.assertEqual(first_step.sla_heures, first_tpl['sla_heures'])
        self.assertEqual(first_step.role_requis, first_tpl['role_requis'])
        self.assertEqual(first_step.escalade_vers, first_tpl['escalade_vers'])

    def test_install_is_idempotent(self):
        first, created1 = workflow_templates.installer_modele_workflow(
            self.company, 'onboarding_chantier')
        self.assertTrue(created1)
        steps_after_first = first.steps.count()

        second, created2 = workflow_templates.installer_modele_workflow(
            self.company, 'onboarding_chantier')
        self.assertFalse(created2)
        self.assertEqual(second.pk, first.pk)

        # Aucun doublon de définition NI d'étape.
        self.assertEqual(
            WorkflowDefinition.objects.filter(
                company=self.company, code='onboarding_chantier').count(),
            1,
        )
        self.assertEqual(second.steps.count(), steps_after_first)

    def test_per_company_isolation(self):
        d_a, _ = workflow_templates.installer_modele_workflow(
            self.company, 'rappel_garantie')
        d_b, _ = workflow_templates.installer_modele_workflow(
            self.other, 'rappel_garantie')
        self.assertNotEqual(d_a.pk, d_b.pk)
        self.assertEqual(d_a.company, self.company)
        self.assertEqual(d_b.company, self.other)
        # Même code, deux sociétés → 2 définitions distinctes (pas de collision).
        self.assertEqual(
            WorkflowDefinition.objects.filter(code='rappel_garantie').count(),
            2,
        )

    def test_install_unknown_code_raises(self):
        with self.assertRaises(workflow_templates.ModeleWorkflowInconnu):
            workflow_templates.installer_modele_workflow(
                self.company, 'pas_un_modele')


class WorkflowTemplateEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Endpoint Co')
        cls.admin = User.objects.create_user(
            username='fg369_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.resp = User.objects.create_user(
            username='fg369_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.limited = User.objects.create_user(
            username='fg369_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def _list(self, user):
        view = WorkflowTemplateViewSet.as_view({'get': 'list'})
        req = self.factory.get('/workflow-templates/')
        if user is not None:
            force_authenticate(req, user=user)
        return view(req)

    def _install(self, user, body):
        view = WorkflowTemplateViewSet.as_view({'post': 'installer'})
        req = self.factory.post(
            '/workflow-templates/installer/', body, format='json')
        force_authenticate(req, user=user)
        return view(req)

    def test_list_requires_auth(self):
        resp = self._list(None)
        # Anonyme : l'accès est refusé. Sous JWT, DRF renvoie 401
        # (NotAuthenticated) ; 403 avec d'autres authentificateurs — les deux
        # prouvent que l'endpoint exige une authentification.
        self.assertIn(
            resp.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_list_ok_for_authenticated_user(self):
        resp = self._list(self.limited)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Dérivé du catalogue (4 depuis ARC10 : relance_devis, relance_facture,
        # approbation_bc, cloture_ncr) — ne plus casser à chaque ajout.
        from core.workflow_templates import WORKFLOW_TEMPLATES
        self.assertEqual(len(resp.data), len(WORKFLOW_TEMPLATES))
        self.assertEqual(
            set(resp.data[0].keys()),
            {'code', 'nom', 'description', 'nb_etapes', 'steps'},
        )

    def test_install_forbidden_for_limited_tier(self):
        resp = self._install(self.limited, {'code': 'relance_devis'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(WorkflowDefinition.objects.exists())

    def test_install_requires_code(self):
        resp = self._install(self.admin, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_install_unknown_code_is_400(self):
        resp = self._install(self.admin, {'code': 'nope'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_install_creates_then_idempotent(self):
        resp = self._install(self.resp, {'code': 'relance_devis'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data['created'])
        self.assertEqual(resp.data['code'], 'relance_devis')
        self.assertGreater(resp.data['nb_etapes'], 0)

        again = self._install(self.resp, {'code': 'relance_devis'})
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertFalse(again.data['created'])
        self.assertEqual(
            WorkflowDefinition.objects.filter(
                company=self.company, code='relance_devis').count(),
            1,
        )

    def test_install_forces_company_server_side(self):
        # Même si le corps tente d'injecter une autre société, c'est celle de
        # l'utilisateur qui est utilisée (jamais lue du corps).
        other = Company.objects.create(nom='Pirate Co')
        resp = self._install(
            self.admin,
            {'code': 'rappel_garantie', 'company': other.pk},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        definition = WorkflowDefinition.objects.get(
            code='rappel_garantie')
        self.assertEqual(definition.company, self.company)
        self.assertFalse(
            WorkflowDefinition.objects.filter(company=other).exists())
