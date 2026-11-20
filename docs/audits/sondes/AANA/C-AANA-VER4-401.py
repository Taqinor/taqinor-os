# flake8: noqa  (sonde d'audit — contre-visite AANA du 20/11, hôte, sans Django ni langchain)
"""AANA91 (jumeau) — les descriptions `_TABLE_DESCRIPTIONS` de `backend/fastapi_ia/app/services/sql_agent_service.py`
(servies telles quelles par `get_schema_summary` → écran Paramètres › IA, et classant les tables pour l'agent) citent-elles
des colonnes absentes des modèles ? On compare, par AST, les mots-colonnes des quatre tables ventes aux champs de
`apps/ventes/models.py::Devis/LigneDevis` et `apps/facturation/models.py::Facture/LigneFacture`."""
import ast
import os
import re

SONDE = {"constat": "C-AANA-VER4-401", "sha": "a923179a46",
         "attendu": "ventes_devis / ventes_lignedevis propres (AANA91) ; ventes_facture cite « numero » et ventes_lignefacture « montant », absents des modèles",
         "modeles": []}

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))


def _champs(path, classe):
    arbre = ast.parse(open(path, encoding='utf8').read())
    for n in arbre.body:
        if isinstance(n, ast.ClassDef) and n.name == classe:
            return {t.id for s in n.body if isinstance(s, ast.Assign) for t in s.targets
                    if isinstance(t, ast.Name) and isinstance(s.value, ast.Call)}
    raise LookupError(classe)


def sonde(ctx=None):
    svc = os.path.join(RACINE, 'backend', 'fastapi_ia', 'app', 'services', 'sql_agent_service.py')
    arbre = ast.parse(open(svc, encoding='utf8').read())
    desc = None
    for n in arbre.body:
        if isinstance(n, ast.AnnAssign) and getattr(n.target, 'id', None) == '_TABLE_DESCRIPTIONS':
            desc = ast.literal_eval(n.value)
    dj = os.path.join(RACINE, 'backend', 'django_core', 'apps')
    modeles = {
        'ventes_devis': _champs(os.path.join(dj, 'ventes', 'models.py'), 'Devis'),
        'ventes_lignedevis': _champs(os.path.join(dj, 'ventes', 'models.py'), 'LigneDevis'),
        'ventes_facture': _champs(os.path.join(dj, 'facturation', 'models.py'), 'Facture'),
        'ventes_lignefacture': _champs(os.path.join(dj, 'facturation', 'models.py'), 'LigneFacture'),
    }
    # mots-colonnes suspects : formes nues qui ne sont pas des champs (prose « montant HT » -> montant_ht tolérée)
    suspects = {}
    for t, champs in modeles.items():
        texte = desc[t].lower()
        mots = set(re.findall(r'[a-z_]+', texte.split(':', 1)[1]))
        inventes = []
        if 'numero' in mots and 'numero' not in champs:
            inventes.append('numero')
        if re.search(r'\bmontant\b(?!\s+(ht|ttc|tva))', texte) and 'montant' not in champs:
            inventes.append('montant')
        suspects[t] = inventes
    obs = {'descriptions': {t: desc[t] for t in modeles}, 'inventes': suspects}
    print(obs)
    return {'repro': bool(suspects['ventes_facture'] or suspects['ventes_lignefacture']),
            'devis_propres': not suspects['ventes_devis'] and not suspects['ventes_lignedevis'], **obs}


if __name__ == '__main__':
    print(sonde())
