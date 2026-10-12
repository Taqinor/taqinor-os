# -*- coding: utf-8 -*-
"""VNT96 — golden des vues facture capturé sur le code FINAL des lots M1-M3,
AVANT la découpe de ``views/facture.py`` en mixins (VNT97-VNT100, patron
SPL130 ``test_golden_devis_viewset.py``).

Nouveau fichier car : golden de découpe (précédent SPL130
``test_golden_devis_viewset.py``, nom couvert par le glob J5
``test_golden_*_facturation.py``).

Ce que le golden fige (``fixtures/golden_vues_facturation.json``) :

* ``routes`` — chaque route de ``FactureViewSet.get_extra_actions()`` (nom,
  ``url_path``, ``url_name``, ``detail``, méthodes triées) ; le NOMBRE est
  celui capturé (``len(routes)`` du golden) ;
* ``noms_publics`` — ``dir(FactureViewSet)`` hors dunder et hors
  ``POSES_PAR_AS_VIEW`` : un mixin oublié dans les bases rougit ;
* ``permissions`` — ``type(p).__name__`` de ``get_permissions()`` pour
  chaque action (standard + ``@action``) ;
* ``corps`` — section ÉPHÉMÈRE : sha256 de ``ast.dump`` (DÉCORATEURS
  COMPRIS, ``ImportFrom.level`` ramené à 0) de chaque membre de
  ``FactureViewSet`` et de toute ``Facture\\w*ActionsMixin``, et de chaque
  symbole de niveau module de ``GROUPES`` ; prouvée identique à chaque
  déplacement puis retirée par VNT101. Capturée sous Python 3.11 (``ast.dump``
  diffère d'une version mineure à l'autre) : échec BRUYANT ailleurs.

``PLACE`` est rempli par chaque déplacement : ``groupe → fichier de views/``.
Un groupe absent de ``PLACE`` vit dans ``views/facture.py`` ; un symbole
présent deux fois (jumeau) est rouge. Le golden ne se régénère JAMAIS pour
faire passer un déplacement.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_golden_vues_facturation"
"""
import ast
import copy
import hashlib
import inspect
import json
import re
import sys
from pathlib import Path

from django.test import SimpleTestCase

VUES = Path(__file__).resolve().parent.parent / 'views'
FIXTURE = Path(__file__).resolve().parent / 'fixtures' / \
    'golden_vues_facturation.json'
MIXIN = re.compile(r'^Facture\w*ActionsMixin$')
DEFAUT = 'facture.py'
#: Version mineure de Python de la capture des ``corps`` (CI : 3.11).
PYTHON_CAPTURE = '3.11'

#: Les symboles que chaque tâche de la piste déplace (texte des tâches
#: VNT97-VNT100, se repérer par NOM).
GROUPES = {
    # VNT97 → views/facture_cycle.py
    'cycle': ['emettre', 'remettre_brouillon', 'marquer_payee', 'annuler',
              'montant_tranche'],
    # VNT98 → views/facture_encaissement.py
    'encaissement': ['paiements', 'arrondi_caisse', 'enregistrer_paiement',
                     'abandonner_solde', 'reprendre_abandon',
                     'liberer_retenue', 'lien_paiement',
                     'revoquer_lien_paiement', 'encaissement_groupe'],
    # VNT98 → views/facture_gardes.py (sert l'encaissement ET creer_avoir)
    'gardes': ['PeutEncaisser'],
    # VNT99 → views/facture_rectificatifs.py
    'rectificatifs': ['creer_avoir', 'creer_note_debit', 'retour_client',
                      'facturer_penalites', '_montants_ligne_corrective',
                      '_MAX_MONTANT_LIGNE'],
    # VNT100 → views/facture_documents.py
    'documents': ['generer_pdf', 'telecharger_pdf', 'ubl', 'dgi_export',
                  'dgi_conformite', 'dgi_transmettre', 'whatsapp',
                  'envoyer_email'],
    # VNT100 → views/facture_recouvrement.py
    'recouvrement': ['relancer', 'relance_apercu', 'exclure_relance',
                     'relances', 'emails', 'historique'],
    # VNT100 → views/facture_lot.py
    'lot': ['kpis', 'consolider', 'bulk'],
}

#: groupe → fichier de ``views/`` où il DOIT vivre ; rempli par chaque
#: déplacement (ex. VNT97 : ``PLACE['cycle'] = 'facture_cycle.py'``).
PLACE = {
    'cycle': 'facture_cycle.py',  # VNT97
    'encaissement': 'facture_encaissement.py',  # VNT98
    'gardes': 'facture_gardes.py',  # VNT98
    'rectificatifs': 'facture_rectificatifs.py',  # VNT99
}

#: Actions standard du ``ModelViewSet`` (non décorées).
ACTIONS_STANDARD = ('list', 'retrieve', 'create', 'update',
                    'partial_update', 'destroy')
#: Posés sur la CLASSE par ``ViewSetMixin.as_view()`` dès que l'URLconf est
#: chargée (DRF) : leur présence dépend de l'ordre des tests, pas du code.
POSES_PAR_AS_VIEW = {'basename', 'description', 'detail', 'name', 'suffix'}


def _fichiers_vues_facture():
    return [VUES / 'facture.py'] + sorted(VUES.glob('facture_*.py'))


def _noms_definis(noeud):
    if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
        return [noeud.name]
    if isinstance(noeud, ast.Assign):
        return [c.id for c in noeud.targets if isinstance(c, ast.Name)]
    if isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target,
                                                       ast.Name):
        return [noeud.target.id]
    return []


def _symboles():
    """``{nom: [(fichier, noeud)]}`` des symboles de ``views/facture*.py`` :
    niveau module + membres de ``FactureViewSet`` et de toute
    ``Facture*ActionsMixin`` (un jumeau apparaît deux fois)."""
    trouves = {}
    for chemin in _fichiers_vues_facture():
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        for noeud in arbre.body:
            for nom in _noms_definis(noeud):
                trouves.setdefault(nom, []).append((chemin.name, noeud))
            if isinstance(noeud, ast.ClassDef) and (
                    noeud.name == 'FactureViewSet'
                    or MIXIN.match(noeud.name)):
                for membre in noeud.body:
                    for nom in _noms_definis(membre):
                        trouves.setdefault(nom, []).append(
                            (chemin.name, membre))
    return trouves


def _empreinte(noeud):
    """sha256 de ``ast.dump`` (décorateurs compris), imports relatifs
    ramenés au niveau 0 (un déplacement d'un module voisin à l'autre ne
    change rien)."""
    noeud = copy.deepcopy(noeud)
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.ImportFrom):
            sous.level = 0
    return hashlib.sha256(
        ast.dump(noeud, include_attributes=False).encode('utf-8')).hexdigest()


def _symboles_figes():
    """Les noms dont le ``corps`` est figé : membres du viewset et des
    mixins + symboles de niveau module des ``GROUPES``."""
    noms = set()
    for chemin in _fichiers_vues_facture():
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        for noeud in arbre.body:
            if isinstance(noeud, ast.ClassDef) and (
                    noeud.name == 'FactureViewSet'
                    or MIXIN.match(noeud.name)):
                for membre in noeud.body:
                    noms.update(_noms_definis(membre))
    for groupe in GROUPES.values():
        noms.update(groupe)
    return sorted(noms)


def capturer_corps():
    trouves = _symboles()
    return {nom: _empreinte(trouves[nom][0][1]) for nom in _symboles_figes()
            if len(trouves.get(nom, [])) == 1}


def capturer_routes():
    from apps.ventes.views.facture import FactureViewSet
    routes = [{
        'nom': fn.__name__,
        'url_path': fn.url_path,
        'url_name': fn.url_name,
        'detail': fn.detail,
        'methodes': sorted(fn.mapping),
    } for fn in FactureViewSet.get_extra_actions()]
    return sorted(routes, key=lambda r: r['nom'])


def capturer_noms_publics():
    from apps.ventes.views.facture import FactureViewSet
    return sorted(n for n in dir(FactureViewSet)
                  if not n.startswith('__') and n not in POSES_PAR_AS_VIEW)


def capturer_permissions():
    from apps.ventes.views.facture import FactureViewSet
    actions = list(ACTIONS_STANDARD) + [
        fn.__name__ for fn in FactureViewSet.get_extra_actions()]
    sortie = {}
    for action in sorted(actions):
        vue = FactureViewSet()
        vue.action = action
        vue.request = None
        vue.format_kwarg = None
        sortie[action] = [type(p).__name__ for p in vue.get_permissions()]
    return sortie


def _golden():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class GoldenVuesFacturation(SimpleTestCase):

    def test_routes_identiques(self):
        golden = _golden()['routes']
        routes = capturer_routes()
        self.assertEqual(len(routes), len(golden))
        self.assertEqual(routes, golden)

    def test_noms_publics_identiques(self):
        self.assertEqual(capturer_noms_publics(), _golden()['noms_publics'])

    def test_permissions_identiques(self):
        self.assertEqual(capturer_permissions(), _golden()['permissions'])

    def test_corps_identiques(self):
        golden = _golden()
        version = '%d.%d' % sys.version_info[:2]
        if version != golden['python']:
            self.fail(
                f"corps capturés sous Python {golden['python']}, exécutés "
                f'sous {version} : ast.dump diffère d\'une version mineure à '
                "l'autre — rejouer dans l'image (3.11), jamais régénérer ici.")
        trouves = _symboles()
        for nom, empreinte in sorted(golden['corps'].items()):
            with self.subTest(symbole=nom):
                occurrences = trouves.get(nom, [])
                self.assertEqual(len(occurrences), 1,
                                 f'{nom} : {len(occurrences)} définition(s)')
                self.assertEqual(_empreinte(occurrences[0][1]), empreinte,
                                 f'{nom} : corps changé pendant le déplacement')

    def test_chaque_groupe_vit_a_sa_place(self):
        from apps.ventes.views.facture import FactureViewSet
        trouves = _symboles()
        for groupe, noms in GROUPES.items():
            attendu = PLACE.get(groupe, DEFAUT)
            for nom in noms:
                with self.subTest(groupe=groupe, symbole=nom):
                    occurrences = trouves.get(nom, [])
                    self.assertEqual(
                        [f for f, _n in occurrences], [attendu],
                        'aucun jumeau : %s doit vivre UNE fois, dans '
                        'views/%s' % (nom, attendu))
                    membre = None
                    for base in FactureViewSet.__mro__:
                        if nom in base.__dict__:
                            membre = base.__dict__[nom]
                            break
                    if membre is None:
                        continue  # niveau module : l'AST fait foi
                    fn = inspect.unwrap(getattr(membre, '__func__', membre))
                    if not callable(fn) or isinstance(fn, type):
                        continue
                    self.assertEqual(Path(inspect.getsourcefile(fn)).name,
                                     attendu)
