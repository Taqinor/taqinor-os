# flake8: noqa  (sonde d'audit — contre-visite AANA du 20/11, hôte, sans Django ni langchain)
"""AANA81 — la garde du harnais d'évaluation (`backend/fastapi_ia/tests/eval/runner.py::_SOMME_LIGNES`) repère-t-elle
les formes équivalentes de la somme des lignes d'un devis ? On extrait le motif du source (AST) et on le joue sur des
SQL candidats ; on vérifie aussi que le prompt servi (`_AGENT_PREFIX`) ne prescrit plus la somme."""
import ast
import os
import re

SONDE = {"constat": "C-AANA-VER4-400", "sha": "a923179a46",
         "attendu": "forme canonique signalée ; formes à facteurs inversés ou remise en tête NON signalées (repro=True si une forme équivalente échappe)",
         "modeles": []}

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))


def _const(path, nom):
    arbre = ast.parse(open(path, encoding='utf8').read())
    for n in arbre.body:
        if isinstance(n, ast.Assign) and any(getattr(t, 'id', None) == nom for t in n.targets):
            return n.value
    raise LookupError(nom)


def sonde(ctx=None):
    runner = os.path.join(RACINE, 'backend', 'fastapi_ia', 'tests', 'eval', 'runner.py')
    v = _const(runner, '_SOMME_LIGNES')  # re.compile(r"...", re.I)
    motif = re.compile(v.args[0].value, re.I)
    candidats = {
        'canonique': "SELECT SUM(l.quantite * l.prix_unitaire) FROM ventes_lignedevis l JOIN ventes_devis d ON l.devis_id=d.id",
        'facteurs_inverses': "SELECT SUM(l.prix_unitaire * l.quantite) FROM ventes_lignedevis l JOIN ventes_devis d ON l.devis_id=d.id",
        'remise_en_tete': "SELECT SUM((1 - l.remise/100) * l.quantite * l.prix_unitaire) FROM ventes_lignedevis l",
        'remise_en_queue': "SELECT SUM(l.quantite * l.prix_unitaire * (1 - l.remise/100)) FROM ventes_lignedevis l",
        'cast_quantite': "SELECT SUM(CAST(l.quantite AS numeric) * l.prix_unitaire) FROM ventes_lignedevis l",
    }
    signale = {k: bool(motif.search(s)) for k, s in candidats.items()}
    svc = os.path.join(RACINE, 'backend', 'fastapi_ia', 'app', 'services', 'sql_agent_service.py')
    prefix = ast.literal_eval(_const(svc, '_AGENT_PREFIX'))
    obs = {'motif': motif.pattern, 'signale': signale,
           'prefix_prescrit_somme': 'SUM(ventes_lignedevis' in prefix or bool(motif.search(prefix)),
           'prefix_renvoie_fiche': 'fiche ERP' in prefix and 'total_ht_stocke' in prefix}
    print(obs)
    echappe = [k for k, ok in signale.items() if k != 'canonique' and not ok]
    return {'repro': bool(echappe), 'echappe': echappe, **obs}


if __name__ == '__main__':
    print(sonde())
