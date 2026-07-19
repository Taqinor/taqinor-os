"""WIR51 — CRUD serveur des définitions de workflow (FG366) + isolation tenant.

Comble le « GAP BACKEND CONFIRMÉ » de l'écran Workflows : composer une
définition multi-étapes la PERSISTE côté serveur (un rechargement la conserve).
``company`` est forcée côté serveur (jamais lue du corps) ; une société ne voit
ni ne peut modifier les définitions (ni les étapes) d'un autre tenant.
"""
from authentication.models import CustomUser
from testkit.base import TenantAPITestCase

from core.models import WorkflowDefinition, WorkflowStepDefinition

BASE = '/api/django/core/workflow-definitions/'
STEPS = '/api/django/core/workflow-step-definitions/'


def _payload(nom='Validation devis', n=3):
    return {
        'nom': nom,
        'description': "Chaîne d'approbation",
        'steps': [
            {
                'ordre': i + 1, 'nom': f'Étape {i + 1}',
                'type_approbation': 'manuelle', 'sla_heures': 24,
                'role_requis': 'Responsable', 'escalade_vers': '',
            }
            for i in range(n)
        ],
    }


class WorkflowDefinitionCrudTests(TenantAPITestCase):
    def _admin(self):
        return self.client_as(role=CustomUser.ROLE_ADMIN)

    def test_create_persists_definition_with_steps(self):
        r = self._admin().post(BASE, _payload(), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertEqual(len(body['steps']), 3)
        self.assertTrue(body['code'])  # code dérivé du nom, non vide
        d = WorkflowDefinition.objects.get(id=body['id'])
        self.assertEqual(d.company_id, self.company.id)
        self.assertEqual(d.steps.count(), 3)
        # Étapes renumérotées 1..n (unicité (definition, ordre) garantie).
        self.assertEqual(
            sorted(d.steps.values_list('ordre', flat=True)), [1, 2, 3])

    def test_reload_preserves_definition(self):
        self._admin().post(BASE, _payload('Ma def'), format='json')
        r = self._admin().get(BASE)
        self.assertEqual(r.status_code, 200, r.content)
        rows = r.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['steps']), 3)

    def test_company_forced_not_from_body(self):
        payload = _payload()
        payload['company'] = self.other_company.id  # tentative d'injection
        r = self._admin().post(BASE, payload, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        d = WorkflowDefinition.objects.get(id=r.json()['id'])
        self.assertEqual(d.company_id, self.company.id)  # ignoré, forcé serveur

    def test_write_requires_admin_or_responsable_tier(self):
        r = self.client_as(role=CustomUser.ROLE_NORMAL).post(
            BASE, _payload(), format='json')
        self.assertEqual(r.status_code, 403, r.content)

    def test_update_replaces_steps(self):
        cr = self._admin().post(BASE, _payload(n=3), format='json').json()
        r = self._admin().put(
            f"{BASE}{cr['id']}/", _payload(nom='Validation devis', n=2),
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()['steps']), 2)
        self.assertEqual(
            WorkflowStepDefinition.objects.filter(
                definition_id=cr['id']).count(), 2)

    def test_tenant_isolation_list_and_retrieve(self):
        other_def = WorkflowDefinition.objects.create(
            company=self.other_company, code='autre', nom='Autre')
        WorkflowStepDefinition.objects.create(
            definition=other_def, ordre=1, nom='X')
        r = self._admin().get(BASE)
        self.assertNotIn(other_def.id, [row['id'] for row in r.json()])
        r2 = self._admin().get(f'{BASE}{other_def.id}/')
        self.assertEqual(r2.status_code, 404, r2.content)

    def test_step_viewset_scoped_and_rejects_foreign_definition(self):
        other_def = WorkflowDefinition.objects.create(
            company=self.other_company, code='autre2', nom='Autre2')
        # Rattacher une étape à une définition d'un AUTRE tenant → refusé.
        r = self._admin().post(STEPS, {
            'definition': other_def.id, 'ordre': 1, 'nom': 'Injection',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        # La liste des étapes est scopée à la société de l'appelant.
        WorkflowStepDefinition.objects.create(
            definition=other_def, ordre=2, nom='Etape autre')
        rl = self._admin().get(STEPS)
        self.assertEqual(rl.status_code, 200, rl.content)
        self.assertEqual(rl.json(), [])
