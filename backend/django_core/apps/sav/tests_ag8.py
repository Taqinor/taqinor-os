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


class SavTicketsAssistantTest(TestCase):
    """SAV3 — ``GET sav/assistant/tickets/`` : lignes compactes de
    ``assistant_tickets.json`` (ouverts non annulés, retard de SLA d'abord)."""

    LIGNE = {
        'ticket_id', 'reference', 'client_id', 'client_nom', 'equipement',
        'statut', 'priorite', 'cree_le', 'sla_due_at', 'en_retard_sla',
        'sous_garantie', 'a_faire', 'lien'}

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.sav.models import Ticket
        from apps.sav.tests import make_installation
        self.company = Company.objects.create(nom='SAV Liste', slug='sav-liste')
        self.inst, self.client_obj = make_installation(self.company, ref='CHT-LST')
        aujourdhui = timezone.localdate()
        self.user = User.objects.create_user(
            username='lst', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='Lst',
                                     permissions=['sav_voir']))

        def ticket(ref, statut, due=None, **kw):
            return Ticket.objects.create(
                company=self.company, reference=ref, client=self.client_obj,
                installation=self.inst, statut=statut, sla_due_at=due,
                description='texte du client', **kw)
        self.tard = ticket('SAV-LST-1', 'nouveau', aujourdhui - timedelta(days=2),
                           priorite='haute')
        self.ok = ticket('SAV-LST-2', 'en_cours', aujourdhui + timedelta(days=5))
        self.sans_sla = ticket('SAV-LST-3', 'planifie')
        self.resolu = ticket('SAV-LST-4', 'resolu')
        self.annule = ticket('SAV-LST-5', 'nouveau', annule=True)

    def _get(self, **params):
        from apps.sav.tests import auth
        return auth(self.user).get('/api/django/sav/assistant/tickets/', params)

    def test_ouverts_non_annules_le_plus_en_retard_d_abord(self):
        r = self._get()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(set(r.data), {'q', 'statut', 'total', 'limite', 'lignes', 'lien'})
        self.assertEqual((r.data['total'], r.data['limite'], r.data['lien']),
                         (3, 10, '/sav/action-requise'))
        self.assertEqual([x['reference'] for x in r.data['lignes']],
                         ['SAV-LST-1', 'SAV-LST-2', 'SAV-LST-3'])
        for ligne in r.data['lignes']:
            self.assertEqual(set(ligne), self.LIGNE)
        premier = r.data['lignes'][0]
        self.assertTrue(premier['en_retard_sla'])
        self.assertEqual((premier['a_faire'], premier['lien']),
                         ('planifier', f'/sav?id={self.tard.pk}'))
        self.assertEqual([x['a_faire'] for x in r.data['lignes']],
                         ['planifier', 'resoudre', 'demarrer'])
        self.assertNotIn('texte du client', str(r.data))

    def test_filtres_statut_retard_et_texte(self):
        self.assertEqual([x['reference'] for x in self._get(statut='resolu').data['lignes']],
                         ['SAV-LST-4'])
        self.assertEqual(self._get(statut='resolu').data['lignes'][0]['a_faire'], 'cloturer')
        retard = self._get(retard_sla='true')
        self.assertEqual([x['reference'] for x in retard.data['lignes']], ['SAV-LST-1'])
        self.assertEqual(retard.data['total'], 1)
        self.assertEqual(self._get(q='lst-2').data['total'], 1)
        self.assertEqual(self._get(priorite='haute').data['total'], 1)
        self.assertEqual(self._get(client=self.client_obj.pk, limite=2).data['limite'], 2)

    def test_valeur_hors_liste_400_et_droit_403(self):
        from apps.sav.tests import auth
        for params in ({'statut': 'ferme'}, {'retard_sla': 'peut-etre'},
                       {'limite': 26}, {'client': 'abc'}):
            self.assertEqual(self._get(**params).status_code, 400, params)
        sans_droit = User.objects.create_user(
            username='lst_crm', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='LstCrm',
                                     permissions=['crm_voir']))
        self.assertEqual(
            auth(sans_droit).get('/api/django/sav/assistant/tickets/').status_code, 403)

    def test_autre_societe_absente(self):
        autre = Company.objects.create(nom='SAV Liste 2', slug='sav-liste-2')
        user = User.objects.create_user(
            username='lst_autre', password='x', company=autre,
            role=Role.objects.create(company=autre, nom='LstAutre',
                                     permissions=['sav_voir']))
        from apps.sav.tests import auth
        r = auth(user).get('/api/django/sav/assistant/tickets/')
        self.assertEqual((r.data['total'], r.data['lignes']), (0, []))


class SavTicketFicheAssistantTest(TestCase):
    """SAV4 — ``GET sav/assistant/tickets/<id>/`` : la fiche compacte de
    ``assistant_ticket_fiche.json`` — jamais de coût, ni de note écrite pour le
    client ; le texte du client est tronqué et reste une donnée."""

    CLES = {
        'id', 'reference', 'statut', 'statut_libelle', 'priorite', 'type', 'client',
        'installation', 'equipement', 'description', 'sla', 'technicien',
        'activites', 'pieces', 'statuts_suivants', 'a_faire', 'lien'}

    def setUp(self):
        from decimal import Decimal
        from apps.sav import activity
        from apps.sav.models import Equipement, PieceConsommee, Ticket
        from apps.sav.tests import make_installation, make_produit
        self.company = Company.objects.create(nom='SAV Fiche', slug='sav-fiche')
        self.inst, self.client_obj = make_installation(self.company, ref='CHT-FCH')
        self.produit = make_produit(self.company)
        self.eq = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            numero_serie='SN-FCH')
        self.tech = User.objects.create_user(
            username='tech_fch', password='x', company=self.company,
            first_name='Hamza', last_name='Idrissi')
        self.user = User.objects.create_user(
            username='fch', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='Fch',
                                     permissions=['sav_voir', 'prix_achat_voir']))
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-FCH-1', client=self.client_obj,
            installation=self.inst, equipement=self.eq, statut='nouveau',
            technicien_responsable=self.tech, cout=Decimal('98765.43'),
            description='Erreur F13. ' + 'x' * 700)
        activity.log_note(self.ticket, self.user, 'note interne')
        activity.log_note(self.ticket, self.user, 'écrite pour le client',
                          visible_client=True)
        activity.log_changes(Ticket(pk=self.ticket.pk, company=self.company,
                                    cout=Decimal('0')), self.ticket, self.user)
        PieceConsommee.objects.create(
            company=self.company, ticket=self.ticket, produit=self.produit,
            quantite=Decimal('2'))

    def _get(self, pk=None, user=None):
        from apps.sav.tests import auth
        return auth(user or self.user).get(
            f'/api/django/sav/assistant/tickets/{pk or self.ticket.pk}/')

    def test_fiche_forme_du_contrat_sans_cout(self):
        r = self._get()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(set(r.data), self.CLES)
        self.assertEqual(r.data['statuts_suivants'], ['en_cours', 'planifie'])
        self.assertEqual((r.data['a_faire'], r.data['lien']),
                         ('planifier', f'/sav?id={self.ticket.pk}'))
        self.assertEqual(r.data['technicien'], 'Hamza Idrissi')
        self.assertEqual(r.data['equipement']['numero_serie'], 'SN-FCH')
        self.assertEqual(r.data['pieces'], [
            {'operation': 'ajout', 'produit': 'Onduleur X', 'quantite': 2.0}])
        self.assertLessEqual(len(r.data['description']), 600)
        self.assertNotIn('98765', str(r.data))
        self.assertNotIn('Coût', str(r.data['activites']))

    def test_activites_sans_note_visible_du_client(self):
        textes = [a['texte'] for a in self._get().data['activites']]
        self.assertIn('note interne', textes)
        self.assertNotIn('écrite pour le client', textes)
        for activite in self._get().data['activites']:
            self.assertEqual(set(activite), {'type', 'le', 'par', 'texte'})

    def test_hors_societe_hors_portee_et_hors_droit(self):
        from apps.roles.permissions_registre import SCOPE_SELF
        autre = Company.objects.create(nom='SAV Fiche 2', slug='sav-fiche-2')
        etranger = User.objects.create_user(
            username='fch_autre', password='x', company=autre,
            role=Role.objects.create(company=autre, nom='FchAutre',
                                     permissions=['sav_voir']))
        self.assertEqual(self._get(user=etranger).status_code, 404)
        restreint = User.objects.create_user(
            username='fch_self', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='FchSelf',
                                     permissions=['sav_voir', SCOPE_SELF]))
        self.assertEqual(self._get(user=restreint).status_code, 404)
        sans_droit = User.objects.create_user(
            username='fch_crm', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='FchCrm',
                                     permissions=['crm_voir']))
        self.assertEqual(self._get(user=sans_droit).status_code, 403)

    def test_ticket_annule_n_a_aucun_statut_suivant(self):
        from apps.sav.models import Ticket
        Ticket.objects.filter(pk=self.ticket.pk).update(annule=True)
        r = self._get()
        self.assertEqual((r.data['statuts_suivants'], r.data['a_faire']), ([], 'rien'))


class SavTransitionActionsTest(TestCase):
    """SAV5 — les deux actions de transition : à confirmer, leur libellé dit
    quand le client est prévenu, et aucune entrée ne lève un garde-fou."""

    def test_transition_et_resoudre_declarees_a_confirmer(self):
        from apps.agent.registry import LOT_COPILOTE, RISK_OUTWARD
        for cle in ('sav.ticket.transition', 'sav.ticket.resoudre'):
            a = _by_key(cle)
            self.assertEqual((a.risk, a.lot, a.method), (RISK_OUTWARD, LOT_COPILOTE, 'POST'), cle)
            self.assertEqual(a.objets, {'id': 'ticket'}, cle)
            self.assertEqual(a.required_permission, 'sav_gerer', cle)
            self.assertIn('prévenu', a.label, cle)
            self.assertLessEqual(len(a.label), 90, cle)
            self.assertLessEqual(len(a.description), 600, cle)
            self.assertTrue(a.description.startswith('Sert à'), cle)
            self.assertIn('Ne pas utiliser pour', a.description, cle)
            interdits = {'sans_facture', 'motif', 'visible_client', 'company', 'forcer'}
            self.assertFalse(interdits & set(a.inputs['properties']), cle)

    def test_gestes_derives_de_la_machine_d_etats(self):
        from apps.sav import machine_etats
        from apps.sav.models import Ticket
        from apps.sav.selectors_assistant import GESTES_TRANSITION, STATUT_DU_GESTE
        a = _by_key('sav.ticket.transition')
        self.assertEqual(a.inputs['properties']['vers']['enum'], list(GESTES_TRANSITION))
        self.assertNotIn('resoudre', GESTES_TRANSITION)
        cibles = set().union(*machine_etats._transitions().values())
        self.assertLessEqual(set(STATUT_DU_GESTE.values()), cibles)
        self.assertEqual(
            _by_key('sav.ticket.resoudre').inputs['properties']['canal_resolution']['enum'],
            list(Ticket.CanalResolution.values))

    def test_clause_de_notification_lue_du_service(self):
        """Les statuts qui préviennent le client sont ceux de la notification
        du service : nouveau (réouverture), planifié, résolu."""
        from apps.sav.models import Ticket
        from apps.sav.notifications_client import STATUT_TO_CLE
        from apps.sav.selectors_assistant import STATUT_DU_GESTE
        previennent = {g for g, s in STATUT_DU_GESTE.items() if s in STATUT_TO_CLE}
        self.assertEqual(previennent, {'planifier', 'reouvrir', 'resoudre'})
        self.assertNotIn(Ticket.Statut.CLOTURE, STATUT_TO_CLE)
        self.assertNotIn(Ticket.Statut.EN_COURS, STATUT_TO_CLE)


class SavNoterActionTest(TestCase):
    """SAV6 — ``sav.ticket.noter`` : écriture silencieuse d'une note INTERNE ;
    ``visible_client`` et ``reponse_type_id`` ne sont pas des entrées."""

    def test_declaration_silencieuse_entree_body_seulement(self):
        from apps.agent.registry import LOT_COPILOTE, RISK_INTERNAL
        a = _by_key('sav.ticket.noter')
        self.assertEqual((a.risk, a.lot, a.method, a.required_permission, a.lecture),
                         (RISK_INTERNAL, LOT_COPILOTE, 'POST', 'sav_gerer', False))
        self.assertEqual(a.endpoint, '/api/django/sav/tickets/{id}/noter/')
        self.assertEqual(set(a.inputs['properties']), {'id', 'body'})
        self.assertEqual(a.inputs['required'], ['id', 'body'])
        self.assertEqual(a.objets, {'id': 'ticket'})
        self.assertLessEqual(len(a.description), 600)

    def test_la_note_posee_par_la_route_reste_interne(self):
        from apps.sav.models import Ticket, TicketActivity
        from apps.sav.tests import auth, make_installation
        company = Company.objects.create(nom='SAV Note', slug='sav-note')
        _, client = make_installation(company, ref='CHT-NOTE')
        user = User.objects.create_user(
            username='note', password='x', company=company,
            role=Role.objects.create(company=company, nom='Note',
                                     permissions=['sav_voir', 'sav_gerer']))
        ticket = Ticket.objects.create(
            company=company, reference='SAV-NOTE-1', client=client, created_by=user)
        a = _by_key('sav.ticket.noter')
        r = auth(user).post(a.endpoint.format(id=ticket.pk),
                            {'body': 'client rappelé'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        note = TicketActivity.objects.get(ticket=ticket, kind=TicketActivity.Kind.NOTE)
        self.assertEqual((note.body, note.visible_client), ('client rappelé', False))


class SavBriefTest(TestCase):
    """SAV7 — ``brief_sav(user, aujourdhui)`` : le bloc ``tickets`` du point du
    matin — compteurs complets, cinq lignes au plus, retard de SLA d'abord."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.sav.models import Ticket
        from apps.sav.tests import make_installation
        self.aujourdhui = timezone.localdate()
        self.company = Company.objects.create(nom='SAV Brief', slug='sav-brief')
        _, client = make_installation(self.company, ref='CHT-BRF')
        self.user = User.objects.create_user(
            username='brf', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='Brf',
                                     permissions=['sav_voir']))
        for n in range(7):
            Ticket.objects.create(
                company=self.company, reference=f'SAV-BRF-{n}', client=client,
                sla_due_at=self.aujourdhui - timedelta(days=3 - n) if n < 3 else None)
        Ticket.objects.create(company=self.company, reference='SAV-BRF-OK',
                              client=client, statut='cloture')

    def test_compteurs_complets_lignes_bornees_retard_d_abord(self):
        from apps.sav.selectors_assistant import brief_sav
        bloc = brief_sav(self.user, self.aujourdhui)
        self.assertEqual(set(bloc), {'ouverts', 'en_retard_sla', 'lignes', 'lien'})
        self.assertEqual((bloc['ouverts'], bloc['en_retard_sla'], bloc['lien']),
                         (7, 3, '/sav/action-requise'))
        self.assertEqual(len(bloc['lignes']), 5)
        self.assertEqual([x['en_retard_sla'] for x in bloc['lignes']][:2], [True, True])
        self.assertEqual(bloc['lignes'][0]['reference'], 'SAV-BRF-0')

    def test_sans_droit_sav_voir_aucun_bloc(self):
        from apps.sav.selectors_assistant import brief_sav
        sans = User.objects.create_user(
            username='brf_crm', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='BrfCrm',
                                     permissions=['crm_voir']))
        self.assertIsNone(brief_sav(sans, self.aujourdhui))
