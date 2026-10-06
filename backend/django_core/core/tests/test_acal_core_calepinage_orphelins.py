# -*- coding: utf-8 -*-
"""ACAL328 (C-ACAL-141) — aucun module ORPHELIN dans ``core/calepinage``.

Graphe d'imports par AST (aucun Django, aucune base) : chaque module du
paquet doit avoir au moins un importeur HORS TESTS dans
``backend/django_core`` (un autre module du paquet compte), ou figurer dans
l'allowliste ci-dessous avec sa raison. Le rendu matplotlib AO (``rendu/``),
``rives.py`` et ``etude.py`` — importés par les seuls tests — sont parqués
dans ``backend/parked/core_calepinage`` (D-ACAL-16 : parquer, pas supprimer).
Remettre l'un d'eux ici sans importeur rend ce test ROUGE.
"""

import ast
import os
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
PAQUET = os.path.join(RACINE, 'core', 'calepinage')

#: Modules SANS importeur de production dans ``backend/django_core``, gardés
#: SCIEMMENT. Toute entrée porte sa raison.
ALLOWLISTE = {
    # Importés par ``backend/parked/ao/calepinage_service.py`` (le module AO
    # parqué) — ACAL328 « Hors périmètre » : ils RESTENT.
    'core.calepinage.echelle': 'importé par backend/parked/ao',
    'core.calepinage.sensibilites': 'importé par backend/parked/ao',
    # ACAL292 a retiré les tiroirs AO de ``moteur/calculer`` ; le texte de
    # la tâche : « core/calepinage/tiroirs.py (noyau) reste intact car
    # parked/ao l'importe » (calepinage_service.py l.92 et l.439).
    'core.calepinage.tiroirs': 'importé par backend/parked/ao (ACAL292)',
    # Hors périmètre d'ACAL328 (le noyau CAL88 du champ au sol et le site) :
    # non parqués ici, à statuer par leur propre tâche.
    'core.calepinage.site': 'hors périmètre ACAL328 (à statuer)',
    'core.calepinage.surfaces.sol': 'hors périmètre ACAL328 (CAL88, à statuer)',
}


def _modules_du_paquet():
    modules = {}
    for racine, _dirs, fichiers in os.walk(PAQUET):
        if '__pycache__' in racine:
            continue
        for nom in fichiers:
            if not nom.endswith('.py'):
                continue
            chemin = os.path.join(racine, nom)
            module = os.path.relpath(chemin, RACINE)[:-3].replace(os.sep, '.')
            # Un paquet (``__init__``) est chargé implicitement par tout import
            # d'un de ses modules : il n'est jamais « orphelin ».
            if not module.endswith('.__init__'):
                modules[module] = chemin
    return modules


def _est_un_test(chemin):
    morceaux = chemin.split(os.sep)
    return ('tests' in morceaux or os.path.basename(chemin).startswith('test_')
            or 'migrations' in morceaux)


def _imports(chemin, module_courant):
    try:
        with open(chemin, encoding='utf-8') as fichier:
            arbre = ast.parse(fichier.read())
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    # ``a.b.c`` → paquet ``a.b`` ; ``a.b.__init__`` → paquet ``a.b``.
    paquet = module_courant.rsplit('.', 1)[0]
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            noms.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            base = noeud.module or ''
            if noeud.level:
                parties = paquet.split('.')
                if noeud.level > 1:
                    parties = parties[:len(parties) - (noeud.level - 1)]
                base = '.'.join(parties + ([base] if base else []))
            noms.add(base)
            noms.update('%s.%s' % (base, alias.name) for alias in noeud.names)
    return noms


def _importeurs():
    modules = _modules_du_paquet()
    importeurs = {module: set() for module in modules}
    for racine, _dirs, fichiers in os.walk(RACINE):
        if '__pycache__' in racine or 'node_modules' in racine:
            continue
        for nom in fichiers:
            if not nom.endswith('.py'):
                continue
            chemin = os.path.join(racine, nom)
            if _est_un_test(chemin):
                continue
            courant = os.path.relpath(chemin, RACINE)[:-3].replace(os.sep, '.')
            for importe in _imports(chemin, courant):
                if importe in importeurs and importe != courant:
                    importeurs[importe].add(courant)
    return importeurs


class ModulesOrphelins(unittest.TestCase):

    def test_chaque_module_de_core_calepinage_a_un_importeur_hors_tests_ou_est_allowliste(self):
        orphelins = sorted(
            module for module, sources in _importeurs().items()
            if not sources and module not in ALLOWLISTE)
        self.assertEqual(
            orphelins, [],
            'modules de core/calepinage sans importeur de production : %r — '
            'les parquer dans backend/parked/core_calepinage (D-ACAL-16) ou '
            'les allowlister avec leur raison.' % (orphelins,))

    def test_le_rendu_matplotlib_est_parque(self):
        for chemin in ('rendu', 'rives.py', 'etude.py'):
            self.assertFalse(os.path.exists(os.path.join(PAQUET, chemin)),
                             chemin)

    def test_l_allowliste_ne_garde_que_des_modules_existants(self):
        modules = _modules_du_paquet()
        for module in ALLOWLISTE:
            self.assertIn(module, modules, module)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
