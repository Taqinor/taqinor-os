"""AG8 — Tests des actions agentiques SAV (registre AG1).

Couvre :
- le catalogue porte les deux actions SAV (`sav.ticket.create`,
  `sav.ticket.update`) après `SavConfig.ready()` ;
- `ouvrir_ticket_sav` reproduit le comportement de l'outil FastAPI hard-codé :
  endpoint `POST /api/django/sav/tickets/`, permission `sav_gerer`, client OU
  équipement (REP5), et la société N'EST PAS dans le schéma d'entrée ;
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
        # REP5 — client OU équipement (la route déduit client + chantier de
        # l'équipement) ; company JAMAIS dans le schéma (posée côté serveur).
        props = a.inputs['properties']
        self.assertEqual(a.inputs['required'], ['description'])
        self.assertLessEqual({'client', 'equipement', 'description'}, set(props))
        self.assertNotIn('company', props)
        self.assertEqual(a.objets, {'client': 'client'})

    def test_mettre_a_jour_ticket_shape(self):
        a = _by_key('sav.ticket.update')
        self.assertIsNotNone(a)
        self.assertEqual(a.endpoint, '/api/django/sav/tickets/{id}/')
        self.assertEqual(a.method, 'PATCH')
        self.assertEqual(a.required_permission, 'sav_gerer')
        self.assertIn('id', a.inputs['required'])
        self.assertNotIn('company', a.inputs['properties'])
        # REP5 — réaffecter exige sav_reassign (garde par champ) : retiré.
        self.assertEqual(set(a.inputs['properties']),
                         {'id', 'priorite', 'description'})

    def test_rep5_a_confirmer_et_valeurs_exactes_du_modele(self):
        from apps.agent.registry import RISK_OUTWARD
        from apps.agent.tests.test_registry import _gardes_de_la_route
        from apps.sav.models import Ticket
        for key in ('sav.ticket.create', 'sav.ticket.update'):
            a = _by_key(key)
            self.assertEqual(a.risk, RISK_OUTWARD, key)
            self.assertTrue(a.confirm_summary, key)
            self.assertEqual(a.inputs['properties']['priorite']['enum'],
                             list(Ticket.Priorite.values), key)
            self.assertLessEqual(len(a.description), 600, key)
            self.assertIn(a.required_permission, _gardes_de_la_route(a)[0], key)
        self.assertEqual(
            _by_key('sav.ticket.create').inputs['properties']['type']['enum'],
            list(Ticket.Type.values))


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


class SavTicketParEquipementRelaiTest(TestCase):
    """REP5 — un ticket ouvert par l'équipement SEUL (corps de l'action)
    porte le client et le chantier déduits par la route."""

    def test_post_par_equipement_deduit_client_et_chantier(self):
        from apps.sav.models import Equipement, Ticket
        from apps.sav.tests import auth, make_installation, make_produit
        company = Company.objects.create(nom='SAV Eq', slug='sav-eq')
        user = User.objects.create_user(
            username='sav_eq', password='x', company=company,
            role=Role.objects.create(company=company, nom='SAV',
                                     permissions=['sav_voir', 'sav_gerer']))
        inst, client = make_installation(company, ref='CHT-REP5')
        eq = Equipement.objects.create(
            company=company, produit=make_produit(company),
            installation=inst, numero_serie='SN-REP5')
        a = _by_key('sav.ticket.create')
        r = auth(user).post(a.endpoint, {
            'equipement': eq.id, 'description': 'Onduleur en panne',
            'type': 'correctif', 'priorite': 'haute'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        ticket = Ticket.objects.get(company=company)
        self.assertEqual((ticket.client_id, ticket.installation_id),
                         (client.id, inst.id))
