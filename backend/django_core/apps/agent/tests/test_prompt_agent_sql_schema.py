"""AANA63 — le guide des tables et les exemples SQL du prompt de l'agent SQL
(`_AGENT_PREFIX` de `backend/fastapi_ia/app/services/sql_agent_service.py`)
ne citent que des colonnes et des statuts qui existent dans les modèles Django.

Nouveau fichier car : l'oracle (les modèles Django) n'est importable que côté
Django ; aucun module de test de l'app agent ne lit le prompt
FastAPI (précédent : `apps/publicapi/tests_aana_portees.py`, lecture du
source FastAPI).

Le prompt est lu dans le VRAI source (ast, aucun import FastAPI). sqlglot n'est
pas une dépendance de l'image Django : les exemples (requêtes mono-table) sont
découpés par un analyseur lexical strict ; toute puce du guide non analysable
fait échouer le test (pas de faux vert).

Run :
    python manage.py test apps.agent.tests.test_prompt_agent_sql_schema -v2
"""
import ast
import re
from pathlib import Path

from django.apps import apps
from django.test import SimpleTestCase

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
