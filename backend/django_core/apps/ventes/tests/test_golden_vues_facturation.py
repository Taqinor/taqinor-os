# -*- coding: utf-8 -*-
"""VNT96 — golden de ``FactureViewSet`` capturé sur le code FINAL des lots
M1-M3, AVANT la découpe de ``views/facture.py`` (piste VNT97-VNT101,
déplacements purs ; patron SPL130 ``test_golden_devis_viewset.py``).

Ce que le golden fige (``fixtures/golden_vues_facturation.json``) :

* ``routes`` — chaque route de ``FactureViewSet.get_extra_actions()`` (nom,
  ``url_path``, ``url_name``, ``detail``, méthodes triées) : 34 ``@action``
  + ``montant-tranche`` (VNT67) = ``NB_ROUTES``, nombre CAPTURÉ ;
* ``noms_publics`` — ``dir(FactureViewSet)`` hors dunder et hors
  ``POSES_PAR_AS_VIEW`` : un mixin oublié dans les bases rougit ;
* ``permissions`` — ``type(p).__name__`` de ``get_permissions()`` pour chaque
  action (CRUD + routes) : une garde perdue au déplacement rougit ;
* (``corps`` — sha256 de ``ast.dump`` de chaque membre déplacé, capturé sous
  Python 3.11 : section ÉPHÉMÈRE, prouvée identique à chaque déplacement
  VNT97-VNT100 puis retirée par VNT101, dernière tâche de la piste, pour ne
  pas verrouiller les corrections futures de ces corps.)

``PLACE`` : ``groupe → fichier de views/`` (classes ``Facture…Mixin``). Un
groupe qui vit ailleurs, ou un symbole présent deux fois (jumeau), rougit. Le
golden ne se régénère JAMAIS pour faire passer un déplacement : un golden rouge
est un bug du déplacement. Capture (rare, volontaire) : ``GOLDEN_CAPTURE=1``.
"""
import ast
import inspect
import json
import os
import re
from pathlib import Path

from django.test import SimpleTestCase

VUES = Path(__file__).resolve().parent.parent / 'views'
FIXTURE = Path(__file__).resolve().parent / 'fixtures' / \
    'golden_vues_facturation.json'

#: 34 ``@action`` de la classe + ``montant-tranche`` (VNT67).
NB_ROUTES = 35
MIXIN = re.compile(r'^Facture\w*Mixin$')
ACTIONS_CRUD = ['list', 'retrieve', 'create', 'update', 'partial_update',
                'destroy']

#: Les symboles que chaque tâche de la piste déplace (se repérer par NOM).
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
    'documents': 'facture_documents.py',  # VNT100
    'recouvrement': 'facture_recouvrement.py',  # VNT100
    'lot': 'facture_lot.py',  # VNT100
}

DEFAUT = 'facture.py'

#: Posés sur la CLASSE par ``ViewSetMixin.as_view()`` dès que l'URLconf est
#: chargée (DRF) : leur présence dépend de l'ordre des tests, pas du code.
POSES_PAR_AS_VIEW = {'basename', 'description', 'detail', 'name', 'suffix'}


def _attendu(groupe, nom):
    return PLACE.get(groupe, DEFAUT)


def _fichiers_vues_facture():
    return [VUES / 'facture.py'] + sorted(VUES.glob('facture_*.py'))


def _noms_affectes(noeud):
    if isinstance(noeud, ast.Assign):
        return [c.id for c in noeud.targets if isinstance(c, ast.Name)]
    return []


def _symboles():
    """{nom: [(fichier, noeud)]} : niveau module de ``views/facture*.py`` +
    corps de ``FactureViewSet`` et de toute ``Facture…Mixin``."""
    definitions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    trouves = {}
    for chemin in _fichiers_vues_facture():
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        for noeud in arbre.body:
            noms = [noeud.name] if isinstance(noeud, definitions) else \
                _noms_affectes(noeud)
            for nom in noms:
                trouves.setdefault(nom, []).append((chemin.name, noeud))
            if isinstance(noeud, ast.ClassDef) and (
                    noeud.name == 'FactureViewSet' or MIXIN.match(noeud.name)):
                for membre in noeud.body:
                    if isinstance(membre, definitions):
                        trouves.setdefault(membre.name, []).append(
                            (chemin.name, membre, noeud.name))
    return trouves


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
    actions = ACTIONS_CRUD + [r['nom'] for r in capturer_routes()]
    gardes = {}
    for action in actions:
        vue = FactureViewSet()
        vue.action = action
        vue.request = None
        vue.format_kwarg = None
        gardes[action] = [type(p).__name__ for p in vue.get_permissions()]
    return dict(sorted(gardes.items()))


def capturer():
    return {
        'routes': capturer_routes(),
        'noms_publics': capturer_noms_publics(),
        'permissions': capturer_permissions(),
    }


def _golden():
    if os.environ.get('GOLDEN_CAPTURE') == '1':
        FIXTURE.write_text(json.dumps(
            capturer(), indent=1, ensure_ascii=False, sort_keys=True) + '\n',
            encoding='utf-8')
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class GoldenVuesFacturation(SimpleTestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.golden = _golden()

    def test_routes_identiques(self):
        routes = capturer_routes()
        self.assertEqual(len(routes), NB_ROUTES)
        self.assertEqual(routes, self.golden['routes'])

    def test_chaque_route_appartient_a_un_groupe(self):
        groupes = {n for noms in GROUPES.values() for n in noms}
        self.assertEqual(
            [r['nom'] for r in capturer_routes() if r['nom'] not in groupes],
            [])

    def test_noms_publics_identiques(self):
        self.assertEqual(capturer_noms_publics(), self.golden['noms_publics'])

    def test_permissions_identiques(self):
        self.assertEqual(capturer_permissions(), self.golden['permissions'])

    def test_le_golden_ne_fige_plus_les_corps(self):
        """VNT101 — une retouche de corps ne rougit plus ; une permission,
        une route ou un nom public changés rougissent encore."""
        self.assertEqual(sorted(self.golden),
                         ['noms_publics', 'permissions', 'routes'])

    def test_chaque_groupe_vit_a_sa_place(self):
        from apps.ventes.views.facture import FactureViewSet
        trouves = _symboles()
        for groupe, noms in GROUPES.items():
            for nom in noms:
                attendu = _attendu(groupe, nom)
                with self.subTest(groupe=groupe, symbole=nom):
                    self.assertEqual(
                        [o[0] for o in trouves.get(nom, [])], [attendu],
                        'aucun jumeau : %s doit vivre UNE fois, dans '
                        'views/%s' % (nom, attendu))
                    membre = next((base.__dict__[nom]
                                   for base in FactureViewSet.__mro__
                                   if nom in base.__dict__), None)
                    if membre is None:
                        continue  # niveau module : l'AST fait foi
                    fn = inspect.unwrap(getattr(membre, '__func__', membre))
                    if callable(fn) and not isinstance(fn, type):
                        self.assertEqual(
                            Path(inspect.getsourcefile(fn)).name, attendu)
