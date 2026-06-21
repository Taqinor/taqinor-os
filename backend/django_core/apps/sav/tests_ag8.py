"""AG8 — Tests des actions agentiques SAV (registre AG1).

Couvre :
- le catalogue porte les deux actions SAV (`sav.ticket.create`,
  `sav.ticket.update`) après `SavConfig.ready()` ;
- `ouvrir_ticket_sav` reproduit le comportement de l'outil FastAPI hard-codé :
  endpoint `POST /api/django/sav/tickets/`, permission `sav_gerer`, `client`
  requis, et la société N'EST PAS dans le schéma d'entrée (posée côté serveur) ;
- `mettre_a_jour_ticket` cible `PATCH …/tickets/{id}/` (id requis) ;
- `for_user` ne propose les actions SAV qu'à un utilisateur portant `sav_gerer`.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from authentication.models import Company
from apps.roles.models import Role
from apps.agent.registry import all_actions, for_user

User = get_user_model()


def _by_key(key):
    for a in all_actions():
        if a.key == key:
            return a
    return None


class SavAgentActionsCatalogueTest(TestCase):
    def test_both_actions_registered(self):
        keys = {a.key for a in all_actions()}
        self.assertIn('sav.ticket.create', keys)
        self.assertIn('sav.ticket.update', keys)

    def test_ouvrir_ticket_matches_legacy_tool(self):
        a = _by_key('sav.ticket.create')
        self.assertIsNotNone(a)
        # Même endpoint + verbe que l'outil FastAPI hard-codé.
        self.assertEqual(a.endpoint, '/api/django/sav/tickets/')
        self.assertEqual(a.method, 'POST')
        # Même permission que le TicketViewSet (write → sav_gerer).
        self.assertEqual(a.required_permission, 'sav_gerer')
        # client requis ; company JAMAIS dans le schéma (posée côté serveur).
        props = a.inputs['properties']
        self.assertIn('client', a.inputs['required'])
        self.assertIn('client', props)
        self.assertIn('description', props)
        self.assertNotIn('company', props)

    def test_mettre_a_jour_ticket_shape(self):
        a = _by_key('sav.ticket.update')
        self.assertIsNotNone(a)
        self.assertEqual(a.endpoint, '/api/django/sav/tickets/{id}/')
        self.assertEqual(a.method, 'PATCH')
        self.assertEqual(a.required_permission, 'sav_gerer')
        self.assertIn('id', a.inputs['required'])
        self.assertNotIn('company', a.inputs['properties'])


class SavAgentActionsPermissionTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='SAV Co', slug='sav-co')
        self.sav_role = Role.objects.create(
            company=self.company, nom='SAV', permissions=['sav_gerer'])
        self.sav_user = User.objects.create_user(
            username='sav', password='x', role=self.sav_role,
            company=self.company)
        self.other_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'])
        self.other_user = User.objects.create_user(
            username='ro', password='x', role=self.other_role,
            company=self.company)

    def test_sav_user_sees_sav_actions(self):
        keys = {a.key for a in for_user(self.sav_user)}
        self.assertIn('sav.ticket.create', keys)
        self.assertIn('sav.ticket.update', keys)

    def test_non_sav_user_does_not_see_sav_actions(self):
        keys = {a.key for a in for_user(self.other_user)}
        self.assertNotIn('sav.ticket.create', keys)
        self.assertNotIn('sav.ticket.update', keys)
