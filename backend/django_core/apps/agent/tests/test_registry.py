"""AG1 — Tests du registre d'actions agentiques.

Couvre :
- :class:`AgentAction` valide ses champs (risk autorisé, key obligatoire) ;
- :func:`register` est unique (refuse une key en double) ;
- :func:`for_user` filtre par permission ERP (rôle de la société) ;
- un superuser voit tout, un anonyme rien, une action sans permission est
  ouverte à tout authentifié.
"""
import ast
import re
from pathlib import Path

from django.apps import apps
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model

from authentication.models import Company
from apps.roles.models import Role
from apps.agent.registry import (
    AgentAction, RISK_INTERNAL, RISK_OUTWARD, register, unregister,
    all_actions, for_user,
)

User = get_user_model()


class AgentActionDataclassTest(TestCase):
    def test_invalid_risk_rejected(self):
        with self.assertRaises(ValueError):
            AgentAction(key='k', label='L', description='d',
                        endpoint='/x/', risk='bogus')

    def test_empty_key_rejected(self):
        with self.assertRaises(ValueError):
            AgentAction(key='', label='L', description='d', endpoint='/x/')

    def test_as_dict_shape(self):
        a = AgentAction(
            key='demo.read', label='Lire', description='Lit un truc',
            endpoint='/api/x/', method='get', required_permission='stock_voir',
            risk=RISK_OUTWARD, confirm_summary='résumé')
        d = a.as_dict()
        self.assertEqual(d['key'], 'demo.read')
        self.assertEqual(d['method'], 'GET')  # normalisé en majuscules
        self.assertEqual(d['required_permission'], 'stock_voir')
        self.assertEqual(d['risk'], RISK_OUTWARD)
        self.assertEqual(d['confirm_summary'], 'résumé')
        # COP-G7 — le catalogue porte la carte, le lot et les objets nommés.
        self.assertEqual((d['carte'], d['lot'], d['objets']), (None, None, {}))
        b = AgentAction(
            key='demo.carte', label='L', description='d', endpoint='/x/{id}/',
            carte='document', lot='copilote', objets={'id': 'devis'})
        self.assertEqual(
            {k: b.as_dict()[k] for k in ('carte', 'lot', 'objets')},
            {'carte': 'document', 'lot': 'copilote', 'objets': {'id': 'devis'}})
        # ``objets`` est une copie : le catalogue servi ne mute pas l'action.
        b.as_dict()['objets']['id'] = 'facture'
        self.assertEqual(b.objets, {'id': 'devis'})

    def test_carte_lot_et_objets_hors_ensemble_refuses(self):
        for champ, valeur in (('carte', 'inconnue'), ('lot', 'tous'),
                              ('objets', {'id': 'ligne'})):
            with self.assertRaises(ValueError, msg=champ):
                AgentAction(key='k', label='L', description='d',
                            endpoint='/x/', **{champ: valeur})


class RegisterUniquenessTest(TestCase):
    def tearDown(self):
        unregister('tmp.unique')

    def test_duplicate_key_rejected(self):
        a = AgentAction(key='tmp.unique', label='X', description='d',
                        endpoint='/x/')
        register(a)
        try:
            with self.assertRaises(ValueError):
                register(AgentAction(key='tmp.unique', label='Y',
                                     description='d2', endpoint='/y/'))
        finally:
            unregister('tmp.unique')

    def test_register_appears_in_all_actions(self):
        register(AgentAction(key='tmp.unique', label='X', description='d',
                             endpoint='/x/', risk=RISK_INTERNAL))
        keys = [a.key for a in all_actions()]
        self.assertIn('tmp.unique', keys)


class ForUserFilterTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Agent Co', slug='agent-co')
        # Rôle « lecture seule » : ne porte que crm_voir.
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'])
        self.readonly = User.objects.create_user(
            username='ro', password='x', role=self.readonly_role,
            company=self.company)
        # Rôle « vendeur » : peut créer des devis + PDF.
        self.sales_role = Role.objects.create(
            company=self.company, nom='Vendeur',
            permissions=['ventes_creer', 'ventes_pdf', 'crm_voir'])
        self.sales = User.objects.create_user(
            username='sales', password='x', role=self.sales_role,
            company=self.company)
        self.superuser = User.objects.create_superuser(
            username='root', password='x')

    def test_readonly_user_sees_only_permitted(self):
        keys = {a.key for a in for_user(self.readonly)}
        self.assertIn('crm.lead.list', keys)              # crm_voir → autorisé
        self.assertNotIn('ventes.devis.creer_auto', keys)  # ventes_creer manquant
        self.assertNotIn('ventes.devis.generer_pdf', keys)
        self.assertNotIn('stock.produit.delete', keys)

    def test_sales_user_sees_sales_actions(self):
        keys = {a.key for a in for_user(self.sales)}
        self.assertIn('ventes.devis.creer_auto', keys)
        self.assertIn('ventes.devis.generer_pdf', keys)
        self.assertIn('crm.lead.list', keys)
        self.assertNotIn('stock.produit.delete', keys)  # stock_supprimer manquant

    def test_superuser_sees_everything(self):
        keys = {a.key for a in for_user(self.superuser)}
        builtin = {a.key for a in all_actions()}
        self.assertTrue(builtin.issubset(keys))

    def test_action_without_permission_open_to_authenticated(self):
        a = AgentAction(key='tmp.open', label='Ouvert', description='d',
                        endpoint='/open/', required_permission=None)
        register(a)
        try:
            self.assertIn('tmp.open', {x.key for x in for_user(self.readonly)})
        finally:
            unregister('tmp.open')

    def test_anonymous_sees_nothing(self):
        class _Anon:
            is_authenticated = False
        self.assertEqual(for_user(_Anon()), [])
        self.assertEqual(for_user(None), [])


class InterrupteurCopiloteTest(TestCase):
    """COP-G1 — ``ASSISTANT_COPILOTE`` (aucun | admins | tous ; inconnu =
    aucun) : une action ``lot='copilote'`` n'est servie que si le copilote est
    allumé pour le compte, une action ``lot='herite'`` que s'il est éteint,
    une action sans lot toujours."""

    def setUp(self):
        company = Company.objects.create(nom='Copilote Co', slug='copilote-co')
        admin_role = Role.objects.create(
            company=company, nom='Administrateur',
            permissions=['roles_gerer', 'crm_voir'])
        sales_role = Role.objects.create(
            company=company, nom='Commercial', permissions=['crm_voir'])
        self.admin = User.objects.create_user(
            username='cop_admin', password='x', role=admin_role,
            company=company)
        self.commercial = User.objects.create_user(
            username='cop_sales', password='x', role=sales_role,
            company=company)
        for cle, lot in (('tmp.cop.copilote', 'copilote'),
                         ('tmp.cop.herite', 'herite'),
                         ('tmp.cop.sans_lot', None)):
            register(AgentAction(key=cle, label=cle, description='d',
                                 endpoint='/x/', lot=lot))
            self.addCleanup(unregister, cle)

    def _servies(self, user, valeur):
        with self.settings(ASSISTANT_COPILOTE=valeur):
            return {a.key for a in for_user(user)
                    if a.key.startswith('tmp.cop.')}

    def test_tous_allume_pour_admin_et_commercial(self):
        attendu = {'tmp.cop.copilote', 'tmp.cop.sans_lot'}
        self.assertEqual(self._servies(self.admin, 'tous'), attendu)
        self.assertEqual(self._servies(self.commercial, 'tous'), attendu)

    def test_admins_allume_seulement_pour_admin(self):
        self.assertEqual(self._servies(self.admin, 'admins'),
                         {'tmp.cop.copilote', 'tmp.cop.sans_lot'})
        self.assertEqual(self._servies(self.commercial, 'admins'),
                         {'tmp.cop.herite', 'tmp.cop.sans_lot'})

    def test_aucun_et_valeur_inconnue_eteignent_pour_tous(self):
        for valeur in ('aucun', 'TOUS_', 'oui', ''):
            for user in (self.admin, self.commercial):
                self.assertEqual(self._servies(user, valeur),
                                 {'tmp.cop.herite', 'tmp.cop.sans_lot'},
                                 (valeur, user.username))

    def test_valeur_insensible_a_la_casse_et_aux_blancs(self):
        self.assertIn('tmp.cop.copilote', self._servies(self.admin, ' Admins '))

    def test_defaut_du_reglage_est_admins(self):
        from django.conf import settings
        self.assertEqual(getattr(settings, 'ASSISTANT_COPILOTE', None), 'admins')

    def test_confirmation_suit_la_meme_regle(self):
        """Une action du lot ``copilote`` éteint pour le compte est refusée par
        l'endpoint de confirmation (403), comme absente du catalogue."""
        from rest_framework.test import APIClient

        from apps.agent.services import calculer_preuve_confirmation

        def confirmer(user):
            client = APIClient()
            client.force_authenticate(user)
            corps = {'action_key': 'tmp.cop.copilote', 'risk_level': 'internal',
                     'inputs': {}, 'preuve': calculer_preuve_confirmation(
                         secret='s', action_key='tmp.cop.copilote',
                         company_id=user.company_id, user_id=user.pk,
                         inputs={}, object_id=None)}
            return client.post('/api/django/agent/logs/confirmer/', corps,
                               format='json').status_code

        with self.settings(ASSISTANT_COPILOTE='admins', AGENT_HMAC_SECRET='s'):
            self.assertEqual(confirmer(self.commercial), 403)
            self.assertEqual(confirmer(self.admin), 201)


def _feuilles(garde):
    """Aplatit une garde composée DRF (``A | B`` : ``op1`` / ``op2``)."""
    if hasattr(garde, 'op1') and hasattr(garde, 'op2'):
        return _feuilles(garde.op1) + _feuilles(garde.op2)
    return [garde]


def _gardes_de_la_route(action):
    """Gardes RÉELLES de la route d'une action du catalogue, lues sur la vue
    qui la sert (résolution d'URL + ``get_permissions()``, rien n'est exécuté) :
    ``(codes, admin, modules)`` — codes de grille (``HasPermissionOrLegacy`` /
    ``HasPermission`` / ``DroitDeLaGrille``), garde palier administrateur,
    modules de droits des gardes « module » (``IsResponsableOrAdmin``,
    ``LectureDuModule``)."""
    import re

    from django.urls import resolve
    from rest_framework.test import APIRequestFactory

    from authentication.permissions import (
        IsAdminRole, IsResponsableOrAdmin, LectureDuModule, module_de_la_vue)

    chemin = re.sub(r'\{[a-z_]+\}', '1', action.endpoint)
    trouve = resolve(chemin)
    cls = getattr(trouve.func, 'cls', None)
    vue = cls(**getattr(trouve.func, 'initkwargs', {}))
    vue.request = APIRequestFactory().generic(action.method.upper(), chemin)
    vue.kwargs, vue.format_kwarg = trouve.kwargs, None
    actions = getattr(trouve.func, 'actions', None) or {}
    vue.action = actions.get(action.method.lower())
    codes, admin, modules = set(), False, set()
    for garde in (f for g in vue.get_permissions() for f in _feuilles(g)):
        for nom in (c.__name__ for c in type(garde).__mro__):
            for prefixe in ('HasPermissionOrLegacy_', 'HasPermission_'):
                if nom.startswith(prefixe):
                    codes.add(nom[len(prefixe):])
        admin = admin or isinstance(garde, IsAdminRole)
        if isinstance(garde, (IsResponsableOrAdmin, LectureDuModule)):
            modules.add(getattr(garde, 'module_fige', None)
                        or module_de_la_vue(vue))
    return codes, admin, modules - {None}


class PariteCataloguePermissionRouteTest(SimpleTestCase):
    """COP-G2 — la permission du CATALOGUE est la garde de la ROUTE : une action
    offerte à un compte qui reçoit 403 (``automation.rule.propose_draft``), ou
    cachée à un compte qui peut l'exécuter (``enregistrer_paiement`` :
    ``ventes_valider`` au catalogue, ``encaisser`` à la route), trompe le
    modèle. Périmètre : les actions de ventes et les actions propres de
    l'agent. Garde lue statiquement par :func:`_gardes_de_la_route` ; une garde
    qui n'est pas lisible ainsi est listée ICI avec sa raison (jamais ignorée
    en silence) et le test échoue si cette liste cesse d'être exacte."""

    PROPRES_A_L_AGENT = ('automation.rule.propose_draft', 'crm.client.create',
                         'crm.lead.list', 'ged.docqa.retrieve',
                         'reporting.assistant.diagnostic',
                         'stock.produit.delete')
    # clé -> raison pour laquelle la garde de la route n'est pas lisible.
    NON_LISIBLES = {
        'ged.docqa.retrieve': (
            "catalogue None (tout compte interne) ; la route est une garde de "
            "MODULE (LectureDuModule ged) + l'ACL coffre-fort lue dans la vue"),
    }

    def _perimetre(self):
        return [a for a in all_actions()
                if a.key.startswith('ventes.')
                or a.key in self.PROPRES_A_L_AGENT]

    def test_permission_du_catalogue_egale_garde_de_la_route(self):
        from authentication.permissions import codes_du_module

        ecarts, non_lisibles = [], set()
        for action in self._perimetre():
            codes, admin, modules = _gardes_de_la_route(action)
            attendu = action.required_permission
            if codes:
                ok = attendu in codes
            elif admin:
                ok = attendu == 'roles_gerer'
            elif modules:
                ok = any(attendu in codes_du_module(m) for m in modules)
            else:
                ok = False
            if not ok and action.key in self.NON_LISIBLES:
                non_lisibles.add(action.key)
            elif not ok:
                ecarts.append(
                    f'{action.key} : catalogue {attendu!r}, route '
                    f'codes={sorted(codes)} admin={admin} modules={sorted(modules)}')
        self.assertEqual(ecarts, [])
        self.assertEqual(non_lisibles, set(self.NON_LISIBLES))

    def test_le_perimetre_contient_les_actions_attendues(self):
        cles = {a.key for a in self._perimetre()}
        self.assertTrue({'ventes.devis.accepter',
                         'ventes.facture.enregistrer_paiement',
                         'automation.rule.propose_draft'} <= cles)
        self.assertGreaterEqual(len(cles), 12)

    def test_les_deux_ecarts_corriges_restent_alignes(self):
        par_cle = {a.key: a for a in all_actions()}
        self.assertEqual(
            par_cle['ventes.facture.enregistrer_paiement'].required_permission,
            'encaisser')
        self.assertEqual(
            par_cle['automation.rule.propose_draft'].required_permission,
            'roles_gerer')


class GuardedWriteActionsTest(TestCase):
    """FG351 — les écritures en langage naturel (Devis/Lead/Client) sont des
    actions GARDÉES : risk=outward (=> propose→confirm côté relais) et gatées
    par une permission ERP (jamais exécutées en lecture seule)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Write Co', slug='write-co')
        # Rôle « lecture seule » : crm_voir uniquement (aucun droit d'écriture).
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'])
        self.readonly = User.objects.create_user(
            username='wro', password='x', role=self.readonly_role,
            company=self.company)
        # Rôle « commercial » : crm_creer + ventes_creer → peut proposer toutes
        # les créations.
        self.writer_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_creer', 'ventes_creer'])
        self.writer = User.objects.create_user(
            username='wwr', password='x', role=self.writer_role,
            company=self.company)

    def _by_key(self):
        return {a.key: a for a in all_actions()}

    def test_builtin_write_actions_registered(self):
        catalogue = self._by_key()
        for key in ('crm.client.create', 'crm.lead.create'):
            self.assertIn(key, catalogue)
        # L'ancienne création de devis VIDE n'existe plus : le Copilote crée
        # toujours un devis dimensionné via l'auto-devis (ventes_creer).
        self.assertNotIn('ventes.devis.create', catalogue)
        self.assertNotIn('ventes.devis.creer', catalogue)

    def test_write_actions_are_guarded_outward(self):
        action = self._by_key()['crm.client.create']
        # outward => le relais renvoie une PROPOSITION à confirmer (jamais
        # une exécution immédiate).
        self.assertEqual(action.risk, RISK_OUTWARD)
        self.assertEqual(action.method.upper(), 'POST')
        self.assertTrue(action.confirm_summary)

    def test_crm_lead_create_declare_une_seule_fois_par_crm(self):
        """COP-G2 — plus de builtin doublon : la déclaration servie est celle
        de ``apps/crm/agent_actions.py`` (descriptions « Sert à : »). Son niveau
        de risque (outward) est gardé par les tests de l'app crm."""
        action = self._by_key()['crm.lead.create']
        self.assertTrue(action.description.startswith('Sert à'))
        self.assertEqual(action.method.upper(), 'POST')

    def test_actions_retirees_du_catalogue(self):
        """COP-G2 — ``ventes.devis.proposal_pdf`` doublonnait
        ``ventes.devis.generer_pdf`` (même route /proposal)."""
        self.assertNotIn('ventes.devis.proposal_pdf', self._by_key())
        self.assertIn('ventes.devis.generer_pdf', self._by_key())

    def test_write_actions_gated_by_permission(self):
        catalogue = self._by_key()
        self.assertEqual(
            catalogue['crm.client.create'].required_permission, 'crm_creer')
        self.assertEqual(
            catalogue['crm.lead.create'].required_permission, 'crm_creer')
        # L'auto-devis (déclaré par l'app ventes) reste gaté par ventes_creer.
        self.assertEqual(
            catalogue['ventes.devis.creer_auto'].required_permission,
            'ventes_creer')

    def test_readonly_cannot_propose_writes(self):
        keys = {a.key for a in for_user(self.readonly)}
        self.assertNotIn('crm.client.create', keys)
        self.assertNotIn('crm.lead.create', keys)
        self.assertNotIn('ventes.devis.creer_auto', keys)

    def test_writer_can_propose_writes(self):
        keys = {a.key for a in for_user(self.writer)}
        self.assertIn('crm.client.create', keys)
        self.assertIn('crm.lead.create', keys)
        self.assertIn('ventes.devis.creer_auto', keys)

    def test_client_and_lead_require_nom(self):
        catalogue = self._by_key()
        for key in ('crm.client.create', 'crm.lead.create'):
            self.assertIn('nom', catalogue[key].inputs.get('required', []), key)


# AANA63 — le guide des tables et les exemples SQL du prompt de l'agent SQL
# (`_AGENT_PREFIX` de backend/fastapi_ia/app/services/sql_agent_service.py)
# ne citent que des colonnes et des statuts des modèles Django. Prompt lu dans
# le VRAI source (ast, aucun import FastAPI) ; toute puce non analysable échoue.
_SOURCE = (Path(__file__).resolve().parents[4] / 'fastapi_ia' / 'app'
           / 'services' / 'sql_agent_service.py')

_IDENT = r'[a-z_][a-z0-9_]*'
_LISTE = re.compile(rf'^{_IDENT}(\s*[,/]\s*{_IDENT})*$')
_SEP = re.compile(r'\s+[=:]\s+')
_QUOTE = re.compile(r"'([^']*)'")
_POINTE = re.compile(rf'\b({_IDENT})\.({_IDENT})\b')
_MOTS_SQL = {
    'select', 'from', 'where', 'order', 'by', 'desc', 'asc', 'and', 'or',
    'not', 'in', 'between', 'interval', 'sum', 'count', 'current_date',
    'limit', 'is', 'null', 'as',
}


def _prefixe():
    arbre = ast.parse(_SOURCE.read_text(encoding='utf-8'))
    for noeud in arbre.body:
        if (isinstance(noeud, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == '_AGENT_PREFIX'
                        for t in noeud.targets)):
            return ast.literal_eval(noeud.value)
    raise AssertionError('_AGENT_PREFIX introuvable')


def _schema():
    """db_table -> {colonne: valeurs de choices (ensemble, vide si aucun)}."""
    out = {}
    for modele in apps.get_models():
        out[modele._meta.db_table] = {
            f.column: {str(c[0]) for c in (f.flatchoices or [])}
            for f in modele._meta.concrete_fields
        }
    return out


def _guide_et_exemples(texte):
    guide = texte.split('GUIDE DES TABLES', 1)[1]
    guide, exemples = guide.split('EXEMPLES DE REQUETES CORRECTES', 1)
    return guide, exemples


def _sections(guide):
    """[(tables, puces, lignes_libres)] ; une puce = '  - ' + ses lignes de
    continuation (indentées de 4 espaces)."""
    sections = []
    for ligne in guide.splitlines():
        if '→' in ligne and not ligne.startswith(' '):
            tete, queue = ligne.split('→', 1)
            tables = re.findall(r'\b[a-z]+_[a-z_]+\b', queue.split('(')[0])
            entete = re.search(r'\(([^)]*)\)', queue)
            sections.append((tables, [], []))
            if entete:
                sections[-1][1].append(entete.group(1).strip())
        elif not sections:
            continue
        elif ligne.startswith('  - '):
            sections[-1][1].append(ligne[4:].strip())
        elif ligne.startswith('    ') and sections[-1][1]:
            sections[-1][1][-1] += ' ' + ligne.strip()
        elif ligne.strip():
            sections[-1][2].append(ligne.strip())
    return sections


class PromptAgentSqlSchemaTests(SimpleTestCase):
    longMessage = False  # message court : la colonne fautive, pas le schéma

    def setUp(self):
        self.schema = _schema()
        self.texte = _prefixe()

    def _colonnes(self, tables):
        cols = {}
        for t in tables:
            self.assertIn(t, self.schema, f'table citée inexistante : {t}')
            for c, ch in self.schema[t].items():
                cols.setdefault(c, set()).update(ch)
        return cols

    def _verifier_pointes(self, texte):
        for table, col in _POINTE.findall(texte):
            if table in self.schema:
                self.assertIn(col, self.schema[table], f'{table}.{col}')

    def test_colonnes_citees_existent(self):
        guide, _ = _guide_et_exemples(self.texte)
        sections = _sections(guide)
        self.assertGreaterEqual(len(sections), 8)
        for tables, puces, libres in sections:
            cols = self._colonnes(tables)
            for puce in puces:
                for segment in (s.strip() for s in puce.split(' ; ')):
                    morceaux = _SEP.split(segment, 1)
                    gauche = morceaux[0].strip()
                    if not _LISTE.match(gauche):
                        self.fail(f'puce non analysable : {segment!r}')
                    noms = re.split(r'\s*[,/]\s*', gauche)
                    for nom in noms:
                        self.assertIn(nom, cols, f'{tables} : colonne {nom}')
                    droite = morceaux[1] if len(morceaux) > 1 else ''
                    for valeur in _QUOTE.findall(droite):
                        permis = set().union(*(cols[n] for n in noms))
                        self.assertIn(valeur, permis,
                                      f'{tables} : statut {nom}={valeur!r}')
            for libre in libres:
                self._verifier_pointes(libre)
        self._verifier_pointes(guide)

    def test_exemples_sql_sur_le_schema_reel(self):
        _, exemples = _guide_et_exemples(self.texte)
        lignes = [x[2:] for x in exemples.splitlines()
                  if x.startswith('- ')]
        self.assertGreaterEqual(len(lignes), 5)
        for ligne in lignes:
            sql = ligne.split(' : ', 1)[1]
            tables = re.findall(rf'\bFROM\s+({_IDENT})', sql)
            self.assertEqual(len(tables), 1, sql)
            cols = self._colonnes(tables)
            jetons = re.findall(rf"'[^']*'|{_IDENT}", sql.lower())
            derniere = None
            for i, jeton in enumerate(jetons):
                if jeton.startswith("'"):
                    if i and jetons[i - 1] == 'interval':
                        continue
                    self.assertIsNotNone(derniere, sql)
                    self.assertIn(jeton.strip("'"), cols[derniere],
                                  f'{sql} : statut {jeton}')
                elif jeton in _MOTS_SQL or jeton == tables[0]:
                    continue
                else:
                    self.assertIn(jeton, cols, f'{sql} : colonne {jeton}')
                    if cols[jeton]:
                        derniere = jeton

    def test_ca_facture_ht_et_devis_sans_montant_stocke(self):
        # AANA77 (D-AANA-6) : montant_ht/montant_ttc NULL sur une facture
        # classique — aucun exemple ne fait passer leur somme pour le CA.
        guide, exemples = _guide_et_exemples(self.texte)
        self.assertNotIn('SUM(montant_ht) FROM', self.texte)
        self.assertNotIn('SUM(montant_ttc) FROM', self.texte)
        self.assertIn('NULL sur une facture classique', guide)
        nb = [x for x in exemples.splitlines()
              if x.startswith('- Nombre de factures emises : ')]
        self.assertEqual(len(nb), 1, exemples)
        self.assertIn("statut IN ('emise','payee','en_retard')", nb[0])
        self.assertNotIn('ventes_devis.montant', self.texte)
        self.assertNotIn('statut_paiement', self.texte)
