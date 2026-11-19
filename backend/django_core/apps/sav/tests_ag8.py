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
        self.assertEqual(a.objets, {'client': 'client', 'equipement': 'equipement',
                                    'installation': 'chantier'})
        self.assertEqual(_by_key('sav.ticket.update').objets, {'id': 'ticket'})

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
            # Objet nommé : seul le LABEL est montré en 1re ligne de l'aperçu.
            self.assertLessEqual(len(a.label), 90, key)
            self.assertEqual(a.inputs['properties']['priorite']['enum'],
                             list(Ticket.Priorite.values), key)
            self.assertLessEqual(len(a.description), 600, key)
            self.assertIn(a.required_permission, _gardes_de_la_route(a)[0], key)
        self.assertEqual(
            _by_key('sav.ticket.create').inputs['properties']['type']['enum'],
            list(Ticket.Type.values))
        self.assertIn("client n'est pas prévenu", _by_key('sav.ticket.create').label)
        self.assertIn('statut inchangé', _by_key('sav.ticket.update').label)


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


class SavLibellesAssistantTest(TestCase):
    """Copilote vague 2 — l'aperçu d'une proposition NOMME le ticket et
    l'équipement (``selectors_libelles.libelles_sav`` via la table de
    l'agent) : dans la société ET la portée seulement, jamais la description
    du problème (texte tiers)."""

    def setUp(self):
        from apps.sav.models import Equipement, Ticket
        from apps.sav.tests import make_installation, make_produit
        self.company = Company.objects.create(nom='SAV Lib', slug='sav-lib')
        inst, client = make_installation(self.company, ref='CHT-LIB')
        self.eq = Equipement.objects.create(
            company=self.company, produit=make_produit(self.company),
            installation=inst, numero_serie='SN-LIB')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-LIB-1', client=client,
            equipement=self.eq, description='mot de passe du wifi')

    def _libelles(self, permissions, company=None):
        from apps.agent.libelles import libelles_objets
        company = company or self.company
        user = User.objects.create_user(
            username=f'lib_{len(permissions)}_{company.pk}', password='x', company=company,
            role=Role.objects.create(company=company, nom=f'R{len(permissions)}',
                                     permissions=permissions))
        return libelles_objets(user, {'ticket': self.ticket.pk, 'equipement': self.eq.pk})

    def test_ticket_et_equipement_nommes_dans_la_portee(self):
        out = self._libelles(['sav_voir', 'equipement_voir'])
        self.assertEqual(out, {'ticket': 'SAV-LIB-1 — Client (Nouveau)',
                               'equipement': 'Onduleur X — n° SN-LIB — Client'})
        self.assertNotIn('wifi', str(out))

    def test_hors_droit_hors_portee_autre_societe_absents(self):
        from apps.roles.permissions_registre import SCOPE_SELF
        self.assertEqual(self._libelles(['crm_voir']), {})
        self.assertEqual(self._libelles(['sav_voir', 'equipement_voir', SCOPE_SELF]), {})
        autre = Company.objects.create(nom='SAV Lib 2', slug='sav-lib-2')
        self.assertEqual(self._libelles(['sav_voir', 'equipement_voir'], autre), {})


class SavParcAssistantTest(TestCase):
    """SAV2 — ``GET sav/assistant/parc/`` : le parc d'un client retrouvé par
    nom, téléphone ou série, avec garantie effective, tickets ouverts et
    contrat actif (forme de ``assistant_parc.json``)."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.crm.models import Client
        from apps.sav.models import Equipement, Ticket
        from apps.sav.tests import make_installation, make_produit
        self.company = Company.objects.create(nom='SAV Parc', slug='sav-parc')
        self.inst, self.client_obj = make_installation(self.company, ref='CHT-PARC')
        Client.objects.filter(pk=self.client_obj.pk).update(
            nom='Chraibi', prenom='Nadia', telephone='0661234567')
        self.pose = timezone.localdate() - timedelta(days=30)
        self.eq = Equipement.objects.create(
            company=self.company, produit=make_produit(self.company),
            installation=self.inst, numero_serie='SN-PARC', date_pose=self.pose)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-PARC-1', client=self.client_obj,
            installation=self.inst, equipement=self.eq, description='panne')
        self.voit = self._user('parc_pii', ['sav_voir', 'client_pii_voir'])
        self.sans_pii = self._user('parc_nopii', ['sav_voir'])

    def _user(self, nom, permissions, company=None):
        company = company or self.company
        return User.objects.create_user(
            username=nom, password='x', company=company,
            role=Role.objects.create(company=company, nom=nom, permissions=permissions))

    def _get(self, user, **params):
        from apps.sav.tests import auth
        return auth(user).get('/api/django/sav/assistant/parc/', params)

    def test_parc_par_nom_forme_du_contrat(self):
        r = self._get(self.voit, q='chraibi')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(set(r.data), {'q', 'total', 'limite', 'clients'})
        self.assertEqual((r.data['total'], r.data['limite']), (1, 5))
        ligne = r.data['clients'][0]
        self.assertEqual(set(ligne), {
            'client_id', 'nom', 'telephone', 'chantiers', 'equipements',
            'tickets_ouverts', 'contrat_actif', 'a_faire', 'lien'})
        self.assertEqual((ligne['nom'], ligne['telephone']), ('Chraibi Nadia', '0661234567'))
        self.assertEqual(ligne['chantiers'][0]['installation_id'], self.inst.pk)
        equipement = ligne['equipements'][0]
        self.assertEqual(equipement['equipement_id'], self.eq.pk)
        self.assertTrue(equipement['sous_garantie'])
        self.assertEqual(equipement['fin_garantie_effective'],
                         self.eq.date_fin_garantie_effective.isoformat())
        self.assertEqual(ligne['tickets_ouverts'][0]['ticket_id'], self.ticket.pk)
        self.assertEqual(ligne['tickets_ouverts'][0]['lien'], f'/sav?id={self.ticket.pk}')
        self.assertEqual((ligne['a_faire'], ligne['contrat_actif']), ('suivre_ticket', None))
        self.assertEqual(ligne['lien'], f'/crm?id={self.client_obj.pk}')

    def test_parc_par_telephone_et_par_serie(self):
        for q in ('06 61 23 45 67', 'sn-parc'):
            r = self._get(self.voit, q=q)
            self.assertEqual([c['client_id'] for c in r.data['clients']],
                             [self.client_obj.pk], q)

    def test_telephone_vide_sans_client_pii_voir(self):
        r = self._get(self.sans_pii, q='chraibi')
        self.assertEqual(r.data['clients'][0]['telephone'], '')
        self.assertNotIn('0661234567', str(r.data))

    def test_q_obligatoire_et_limite_bornee_400(self):
        self.assertEqual(self._get(self.voit).status_code, 400)
        self.assertEqual(self._get(self.voit, q='x', limite=11).status_code, 400)

    def test_aucun_resultat_et_autre_societe_absente(self):
        self.assertEqual(self._get(self.voit, q='zzz').data['clients'], [])
        autre = Company.objects.create(nom='SAV Parc 2', slug='sav-parc-2')
        r = self._get(self._user('parc_autre', ['sav_voir'], autre), q='chraibi')
        self.assertEqual((r.data['total'], r.data['clients']), (0, []))

    def test_sans_droit_sav_voir_403(self):
        self.assertEqual(
            self._get(self._user('parc_crm', ['crm_voir']), q='chraibi').status_code, 403)

    def test_equipement_remplace_exclu_et_contrat_actif_dit(self):
        from apps.sav.models import ContratMaintenance, Equipement
        from apps.sav.tests import make_produit
        Equipement.objects.create(
            company=self.company, produit=make_produit(self.company, sku='OND-R'),
            installation=self.inst, numero_serie='SN-OLD', statut='remplace')
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, date_debut=self.pose,
            actif=True)
        ligne = self._get(self.voit, q='chraibi').data['clients'][0]
        self.assertEqual([e['numero_serie'] for e in ligne['equipements']], ['SN-PARC'])
        self.assertEqual(ligne['contrat_actif'], {'id': contrat.pk, 'fin': None})
