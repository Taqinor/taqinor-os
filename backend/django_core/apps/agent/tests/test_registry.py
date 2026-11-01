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
        self.assertNotIn('ventes.devis.proposal_pdf', keys)
        self.assertNotIn('stock.produit.delete', keys)

    def test_sales_user_sees_sales_actions(self):
        keys = {a.key for a in for_user(self.sales)}
        self.assertIn('ventes.devis.creer_auto', keys)
        self.assertIn('ventes.devis.proposal_pdf', keys)
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
        catalogue = self._by_key()
        for key in ('crm.client.create', 'crm.lead.create'):
            action = catalogue[key]
            # outward => le relais renvoie une PROPOSITION à confirmer (jamais
            # une exécution immédiate).
            self.assertEqual(action.risk, RISK_OUTWARD, key)
            self.assertEqual(action.method.upper(), 'POST', key)
            self.assertTrue(action.confirm_summary, key)

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
        _, exemples = _guide_et_exemples(self.texte)
        ca = [x for x in exemples.splitlines()
              if x.startswith('- CA facturé HT : ')]
        self.assertEqual(len(ca), 1, exemples)
        self.assertIn('SUM(montant_ht) FROM ventes_facture', ca[0])
        self.assertIn("statut IN ('emise','payee','en_retard')", ca[0])
        self.assertNotIn('ventes_devis.montant', self.texte)
        self.assertNotIn('statut_paiement', self.texte)
